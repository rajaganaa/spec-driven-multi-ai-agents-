"""
hub/memory/vector_store.py — Phase 2: Long-term memory via RAG
================================================================

Thin wrapper around a local, on-disk ChromaDB collection used as the
hub's long-term memory: completed feature specs, completed task specs
+ their final code diff, and Reviewer/Tester feedback text. Specialists
retrieve from this before starting a new task (see
hub/agents/specialists/common.py's run_specialist_task) so they can see
relevant past work instead of only the current task's spec.

No external server, no new infra/cost: chromadb.PersistentClient writes
to a local directory (CHROMA_DIR, workspace/.chroma/ by default) — same
"local files only" model as everything else in this hub. It lives
alongside workspace/projects/ (not inside any single project) because
it's hub-level memory, the same tier as specs/ — see the module
docstring note in hub/memory/spec_loader.py for the same distinction
applied to specs/.

SCOPING: every entry is tagged with project_id in its metadata, and
retrieve_relevant() always filters on it, so one project's history can
never leak into another project's retrieval results — the same
sandboxing principle as hub/tools/tools.py's per-project file sandbox,
just applied to memory instead of files.

INDEXING GRANULARITY / IDEMPOTENCY: callers control document identity
via `entry_id`. Passing a stable, deterministic id (e.g.
f"{project_id}:{task_id}:task_spec") makes re-indexing the same logical
entry an overwrite (via Chroma's upsert) rather than a duplicate — used
for task/feature specs and code diffs, which only need one live copy.
Leaving entry_id unset generates a random id, appropriate for entries
that should accumulate over time (e.g. one row per attempt's Reviewer
feedback).

TESTING: pass a fake `embedding_function` via configure() before using
this module in tests. tests/test_vector_store.py does this with its own
FakeEmbeddingFunction, per the project's testing constraints (no real
embedding APIs / network calls in the test suite).

DEFAULT EMBEDDING: unless overridden via configure(), this module uses
its own local, offline _HashingEmbeddingFunction — NOT chromadb's
built-in default (which downloads an ONNX sentence-transformers model
from the internet on first use). That keeps "no external server, no
new infra/cost" honest in the strongest sense: no network dependency,
no extra ML dependency beyond chromadb itself, and no surprise
multi-second/multi-megabyte download the first time a task runs. The
tradeoff is weaker semantic matching than a real sentence-embedding
model (it's a word-hashing/bag-of-words vector, so it's strong on
shared identifiers/keywords, weaker on paraphrase-level similarity). A
stronger embedding_function can be swapped in later via configure()
without changing anything else in this module or its callers.

RETURN CONTRACT: every public function here returns the same shape
used throughout this hub:

    {"ok": True,  "error": None, ...data...}
    {"ok": False, "error": "<message>", ...partial data...}
"""

from __future__ import annotations

import math
import re
import uuid
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

# ── Paths ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent  # .../my-agent-hub
CHROMA_DIR = ROOT / "workspace" / ".chroma"
COLLECTION_NAME = "hub_memory"

# Recognized `kind` values (informational — index_entry doesn't enforce
# this; an unrecognized kind still indexes fine, it just won't be what
# any caller's hardcoded filter expects).
VALID_KINDS = {"feature_spec", "task_spec", "code_diff", "review_feedback", "test_feedback"}


# ── Result helpers (same shape as hub/tools/tools.py) ──────────────────────

def _ok(**kwargs) -> dict:
    return {"ok": True, "error": None, **kwargs}


def _err(message: str, **kwargs) -> dict:
    return {"ok": False, "error": message, **kwargs}


# ── Default embedding function (local, offline, deterministic) ─────────────

class _HashingEmbeddingFunction(EmbeddingFunction):
    """Local word-hashing ("hashing trick") embedding: each document
    becomes a fixed-size, L2-normalized vector where dimension i
    accumulates a hit for every token that hashes to i. Two documents
    sharing more words end up with more similar (closer) vectors.

    Uses zlib.crc32 rather than Python's built-in hash() deliberately:
    hash() is randomized per-process (PYTHONHASHSEED) unless explicitly
    fixed, so the same token would hash to a different dimension in
    every new process. Since ChromaDB persists these vectors to disk
    and this hub is invoked as a fresh process per CLI/task run,
    hash()-based dimensions would silently drift across runs and slowly
    corrupt retrieval quality. crc32 is stable across processes,
    platforms, and Python versions."""

    _DIM = 256

    def __init__(self) -> None:
        pass

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - chromadb's param name
        vectors: List[List[float]] = []
        for doc in input:
            vec = [0.0] * self._DIM
            for token in re.findall(r"[a-zA-Z0-9_]+", (doc or "").lower()):
                vec[zlib.crc32(token.encode("utf-8")) % self._DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vectors.append([v / norm for v in vec])
        return vectors

    @staticmethod
    def name() -> str:
        return "hub-hashing-embedding-v1"

    def get_config(self) -> Dict[str, Any]:
        return {"dim": self._DIM}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "_HashingEmbeddingFunction":
        return _HashingEmbeddingFunction()


# ── Module state (lazy client/collection, overridable via configure()) ─────

_embedding_function: EmbeddingFunction = _HashingEmbeddingFunction()
_client = None
_collection = None


def configure(
    embedding_function: Optional[EmbeddingFunction] = None,
    persist_directory: Optional[Path] = None,
) -> None:
    """Override the embedding function and/or on-disk location.

    Used by tests to inject a fake, deterministic embedding function and
    a throwaway tmp_path directory instead of the real default — see
    tests/test_vector_store.py. Can also be used to swap in a stronger,
    real embedding model later without changing any other code.

    Resets any cached client/collection so the next call picks up the
    change rather than reusing a handle built with the old settings."""
    global _embedding_function, CHROMA_DIR, _client, _collection
    if embedding_function is not None:
        _embedding_function = embedding_function
    if persist_directory is not None:
        CHROMA_DIR = Path(persist_directory)
    _client = None
    _collection = None


def reset_for_tests() -> None:
    """Drop cached client/collection state (not any on-disk data) so a
    fresh configure() in the next test doesn't reuse a stale handle."""
    global _client, _collection
    _client = None
    _collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = _client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=_embedding_function)
    return _collection


# ── index_entry ──────────────────────────────────────────────────────────

def index_entry(
    project_id: str,
    kind: str,
    text: str,
    task_id: Optional[str] = None,
    role: Optional[str] = None,
    entry_id: Optional[str] = None,
    timestamp: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> dict:
    """Add (or, if entry_id already exists, overwrite) one piece of
    memory. Metadata is always {project_id, task_id, role, kind,
    timestamp}, plus anything in extra_metadata.

    project_id and non-empty text are required — everything else is
    optional. A missing/empty task_id or role is stored as "" rather
    than None, since Chroma metadata values must be str/int/float/bool,
    not None."""
    if not project_id:
        return _err("project_id is required")
    if not text or not text.strip():
        return _err("text is required and must be non-empty")

    doc_id = entry_id or f"{project_id}:{kind}:{uuid.uuid4().hex}"
    metadata: Dict[str, Any] = {
        "project_id": project_id,
        "kind": kind,
        "task_id": task_id or "",
        "role": role or "",
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
    }
    if extra_metadata:
        metadata.update(extra_metadata)

    try:
        collection = _get_collection()
        collection.upsert(ids=[doc_id], documents=[text], metadatas=[metadata])
    except Exception as e:
        return _err(f"Could not index entry: {e}")

    return _ok(id=doc_id, metadata=metadata)


# ── retrieve_relevant ────────────────────────────────────────────────────

def retrieve_relevant(project_id: str, query_text: str, top_k: int = 5) -> dict:
    """Top-k most relevant past entries for this project only — the
    `where={"project_id": project_id}` filter means a query never
    returns another project's history, no matter how similar the text.

    Safe to call against an empty store, or a project with no indexed
    history yet: returns {"ok": True, "matches": [], "count": 0}, not an
    error — "nothing relevant yet" is an expected, common case, not a
    failure."""
    if not project_id:
        return _err("project_id is required")
    if not query_text or not query_text.strip():
        return _ok(matches=[], count=0)

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return _ok(matches=[], count=0)
        results = collection.query(
            query_texts=[query_text],
            n_results=max(1, top_k),
            where={"project_id": project_id},
        )
    except Exception as e:
        return _err(f"Retrieval failed: {e}")

    ids = (results.get("ids") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]

    matches: List[dict] = [
        {
            "id": ids[i],
            "text": documents[i],
            "metadata": metadatas[i],
            "distance": distances[i] if i < len(distances) else None,
        }
        for i in range(len(ids))
    ]
    return _ok(matches=matches, count=len(matches))
