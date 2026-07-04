"""
tests/test_vector_store.py — Phase 2 (RAG memory) unit tests

Focus areas:
  1. index_entry() writes documents with the required metadata shape
     and is idempotent when given the same entry_id.
  2. retrieve_relevant() returns relevant matches, ranked, and never
     leaks another project's history into the results.
  3. Empty-store / no-history / blank-query edge cases return
     {"ok": True, "matches": []}, not errors.

Every test uses a fake, deterministic embedding function (bag-of-words
hashing into a fixed-size vector) instead of chromadb's real default
embedding model — that model downloads weights over the network on
first use, which is slow, flaky in CI, and unnecessary for testing our
own indexing/retrieval/scoping logic. Each test also points `configure()`
at a throwaway tmp_path directory so no test touches the real
workspace/.chroma/.
"""

import sys
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings  # noqa: E402

from hub.memory import vector_store as V  # noqa: E402


class FakeEmbeddingFunction(EmbeddingFunction):
    """Deterministic, offline bag-of-words embedding: each doc becomes a
    fixed-size vector where dimension i accumulates a hit for every
    token that hashes to i. Documents sharing more words end up with
    more similar (closer) vectors — good enough to meaningfully test
    ranking/relevance without a real model.

    Uses zlib.crc32 (not Python's built-in hash(), which is randomized
    per-process) so results are stable and reproducible run to run.

    Subclasses chromadb's EmbeddingFunction (rather than just duck-typing
    __call__) so it correctly inherits embed_query() — chromadb's query
    path calls embed_query() separately from __call__(), and the default
    implementation (which just forwards to __call__) only exists via
    that base class."""

    def __init__(self, dim: int = 32):
        self.dim = dim

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - chromadb's param name
        vectors = []
        for doc in input:
            vec = [0.0] * self.dim
            for token in doc.lower().split():
                vec[zlib.crc32(token.encode("utf-8")) % self.dim] += 1.0
            vectors.append(vec)
        return vectors

    @staticmethod
    def name() -> str:
        return "fake-bow-embedding"

    def get_config(self) -> dict:
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config: dict) -> "FakeEmbeddingFunction":
        return FakeEmbeddingFunction(dim=config.get("dim", 32))


@pytest.fixture(autouse=True)
def isolated_vector_store(tmp_path):
    """Point every test at a fresh, throwaway Chroma directory with the
    fake embedding function, and reset cached client/collection state
    before and after so tests never share a live handle or touch the
    real workspace/.chroma/."""
    V.reset_for_tests()
    V.configure(embedding_function=FakeEmbeddingFunction(), persist_directory=tmp_path / ".chroma")
    yield
    V.reset_for_tests()


# ── index_entry ──────────────────────────────────────────────────────────

class TestIndexEntry:
    def test_index_entry_returns_ok_with_metadata(self):
        result = V.index_entry(
            project_id="proj-a",
            kind="task_spec",
            text="Implement the login endpoint with JWT auth.",
            task_id="T01",
            role="coder",
        )
        assert result["ok"] is True
        assert result["metadata"]["project_id"] == "proj-a"
        assert result["metadata"]["kind"] == "task_spec"
        assert result["metadata"]["task_id"] == "T01"
        assert result["metadata"]["role"] == "coder"
        assert result["metadata"]["timestamp"]  # auto-filled, non-empty

    def test_index_entry_requires_project_id(self):
        result = V.index_entry(project_id="", kind="task_spec", text="something")
        assert result["ok"] is False
        assert "project_id" in result["error"].lower()

    def test_index_entry_requires_nonempty_text(self):
        result = V.index_entry(project_id="proj-a", kind="task_spec", text="   ")
        assert result["ok"] is False
        assert "text" in result["error"].lower()

    def test_index_entry_with_same_entry_id_overwrites_not_duplicates(self):
        V.index_entry(project_id="proj-a", kind="task_spec", text="first version", entry_id="proj-a:T01:task_spec")
        V.index_entry(project_id="proj-a", kind="task_spec", text="second version", entry_id="proj-a:T01:task_spec")

        result = V.retrieve_relevant("proj-a", "version", top_k=5)
        matching = [m for m in result["matches"] if m["id"] == "proj-a:T01:task_spec"]
        assert len(matching) == 1
        assert matching[0]["text"] == "second version"

    def test_index_entry_without_entry_id_generates_unique_ids(self):
        r1 = V.index_entry(project_id="proj-a", kind="review_feedback", text="looks good")
        r2 = V.index_entry(project_id="proj-a", kind="review_feedback", text="looks good")
        assert r1["id"] != r2["id"]


# ── retrieve_relevant ────────────────────────────────────────────────────

class TestRetrieveRelevant:
    def test_retrieve_finds_relevant_entry(self):
        V.index_entry(project_id="proj-a", kind="task_spec", text="Build a REST API for user authentication.")
        V.index_entry(project_id="proj-a", kind="task_spec", text="Add a dark mode toggle to the settings page.")

        result = V.retrieve_relevant("proj-a", "user authentication REST API", top_k=5)
        assert result["ok"] is True
        assert result["count"] >= 1
        # The authentication doc should be the closer (lower-distance) match.
        top = result["matches"][0]
        assert "authentication" in top["text"].lower()

    def test_retrieve_respects_top_k(self):
        for i in range(10):
            V.index_entry(project_id="proj-a", kind="task_spec", text=f"task number {i} about widgets and gadgets")

        result = V.retrieve_relevant("proj-a", "widgets and gadgets", top_k=3)
        assert result["ok"] is True
        assert len(result["matches"]) == 3

    def test_retrieve_does_not_leak_across_projects(self):
        V.index_entry(project_id="proj-a", kind="task_spec", text="secret project A payment integration details")
        V.index_entry(project_id="proj-b", kind="task_spec", text="unrelated project B shopping cart feature")

        result = V.retrieve_relevant("proj-b", "payment integration details", top_k=5)
        assert result["ok"] is True
        texts = [m["text"] for m in result["matches"]]
        assert all("project a" not in t.lower() for t in texts)
        assert all("payment integration" not in t.lower() for t in texts)

    def test_retrieve_on_empty_store_returns_empty_not_error(self):
        result = V.retrieve_relevant("proj-a", "anything at all", top_k=5)
        assert result["ok"] is True
        assert result["matches"] == []
        assert result["count"] == 0

    def test_retrieve_on_project_with_no_history_returns_empty(self):
        V.index_entry(project_id="proj-a", kind="task_spec", text="some content for project a")
        result = V.retrieve_relevant("proj-never-seen", "some content", top_k=5)
        assert result["ok"] is True
        assert result["matches"] == []

    def test_retrieve_requires_project_id(self):
        result = V.retrieve_relevant("", "a query", top_k=5)
        assert result["ok"] is False
        assert "project_id" in result["error"].lower()

    def test_retrieve_with_blank_query_returns_empty_not_error(self):
        V.index_entry(project_id="proj-a", kind="task_spec", text="some content")
        result = V.retrieve_relevant("proj-a", "   ", top_k=5)
        assert result["ok"] is True
        assert result["matches"] == []

    def test_retrieve_matches_include_metadata(self):
        V.index_entry(project_id="proj-a", kind="review_feedback", text="fix the null check", task_id="T02", role="reviewer")
        result = V.retrieve_relevant("proj-a", "null check", top_k=5)
        assert result["ok"] is True
        top = result["matches"][0]
        assert top["metadata"]["task_id"] == "T02"
        assert top["metadata"]["role"] == "reviewer"
        assert top["metadata"]["kind"] == "review_feedback"
        assert "distance" in top
