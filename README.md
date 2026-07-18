# AgentForge — Spec-Driven Autonomous Multi-AI-Agent System

[![CI](https://github.com/rajaganaa/spec-driven-multi-ai-agents-/actions/workflows/ci.yml/badge.svg)](https://github.com/rajaganaa/spec-driven-multi-ai-agents-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

> Give it a goal in plain English. A hierarchy of AI agents plans it, writes the code, tests it, and commits it — end to end, no manual coding required.

---

## Overview

**AgentForge** (internally `my-agent-hub`) is a self-hosted, spec-driven autonomous coding system built on [Google ADK](https://github.com/google/adk-python) and Gemini. It mirrors the architecture of Cursor Agent and Codex — but runs entirely on your own infrastructure, with support for both a **self-hosted vLLM backend** and **Google Vertex AI / Gemini** as a fallback.

You interact with it via a **CLI**, a **FastAPI REST API** (`api.py`), or a **React dashboard** (`frontend/`). The agents plan your project, break it into specs, execute tasks using a sandboxed tool layer, and auto-commit results with git.

---

## How It Works

```
You (plain English goal)
        │
        ▼
Level 0 — Orchestrator          (gemini-2.5-pro)
        │   Writes project plan + feature specs
        ▼
Level 1 — Feature Leads         (gemini-2.5-pro, one per feature)
        │   Break features into individual task specs
        ▼
Level 2 — Specialists           (gemini-2.5-flash)
  Explorer · Coder · Tester · Reviewer
        │   Execute tasks via tool calls
        ▼
Tools Layer
  read_file · write_file · apply_patch · list_dir
  search_code · run_terminal · git_status · git_commit
        │
        ▼
workspace/projects/<project_id>/   ← all file ops sandboxed here
```

Each agent only ever sees its **own spec file** plus a small set of relevant files (max ~15k tokens) — never the full chat history. This keeps every agent focused and context-efficient.

---

## Features

- ✅ **3-level agent hierarchy** — Orchestrator → Feature Leads → Specialists
- ✅ **Spec-driven execution** — every feature and task has a dedicated spec file before any code is written
- ✅ **Dual model backend** — primary vLLM (self-hosted), automatic fallback to Gemini via Vertex AI
- ✅ **Cached health checks** — vLLM health is checked with a 30s TTL to avoid per-request latency
- ✅ **Background task execution** — `/api/run` returns immediately; poll `/api/status` for live updates
- ✅ **Sandboxed file operations** — all writes are restricted to `workspace/projects/<id>/`
- ✅ **Auto git commit** — specialists commit on every successful task completion
- ✅ **FastAPI REST backend** — full async API wrapping the same hub internals as the CLI
- ✅ **React + Vite dashboard** — frontend for creating projects, watching status, browsing generated files
- ✅ **Docker + Cloud Run ready** — Dockerfile and GCP deploy scripts included
- ✅ **CI via GitHub Actions** — automated test runs on every push

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Required (specified in `requirements.txt`) |
| Node.js 18+ | For the React frontend only |
| Google Cloud account | For Vertex AI / Gemini fallback |
| vLLM instance (optional) | Self-hosted GPU; e.g. AWS EC2 `g4dn.xlarge` with `Qwen/Qwen2.5-Coder-7B-Instruct` |
| git | Installed and configured (agents auto-commit) |

---

## Project Structure

```
spec-driven-multi-ai-agents-/
├── api.py                      # FastAPI REST backend (AgentForge API v2.0)
├── register_tasks.py           # Utility: bulk-register task specs into the board
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker image for Cloud Run deployment
├── DEPLOYMENT.md               # Full deployment guide (AWS + GCP)
├── .env.example                # Environment variable template — copy to .env
│
├── cli/
│   └── main.py                 # Click CLI (new / plan / run / status commands)
│
├── hub/
│   ├── agents/
│   │   ├── config.py           # Model router: vLLM primary → Gemini fallback
│   │   ├── orchestrator.py     # Level 0 — writes project plan + feature specs
│   │   ├── feature_lead.py     # Level 1 — breaks features into task specs
│   │   └── specialists/        # Level 2 — Explorer, Coder, Tester, Reviewer
│   ├── memory/
│   │   └── spec_loader.py      # Loads specs, builds agent context, tracks board
│   ├── runner/
│   │   └── task_runner.py      # Picks agent per task, runs ADK loop, git commit
│   ├── tools/
│   │   └── tools.py            # All sandboxed tool functions (file, terminal, git)
│   └── eval/                   # Evaluation utilities
│
├── frontend/                   # Vite + React 18 dashboard
│   ├── src/                    # React components and pages
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
│
├── config/
│   └── agents.yaml             # Agent config (models, tool allowlists)
│
├── specs/                      # Auto-generated spec files (project plan, features, tasks)
├── tests/                      # Test suite (98+ tests)
├── deploy/                     # GCP Cloud Run and AWS deploy scripts
└── workspace/
    └── projects/               # Sandboxed output — all generated code lands here
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/rajaganaa/spec-driven-multi-ai-agents-.git
cd spec-driven-multi-ai-agents-
```

### 2. Set up Python environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your real values (see Configuration section below)
```

### 4. (Optional) Set up the frontend

```bash
cd frontend
npm install
cp .env.example .env            # Set VITE_API_URL to point at your backend
```

---

## Configuration

Copy `.env.example` to `.env` and fill in the values:

```env
# ── Option A: Self-hosted vLLM (primary backend, optional) ──────────────
VLLM_BASE_URL=http://<your-ec2-ip>:8001     # Leave blank to skip vLLM
VLLM_API_KEY=your-vllm-api-key
VLLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct

# ── Option B: Google Vertex AI / Gemini (fallback, always available) ────
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# ── Frontend CORS (set in production) ───────────────────────────────────
FRONTEND_ORIGIN=https://your-frontend-domain.com
```

**Model routing logic:**
- If `VLLM_BASE_URL` is set and the vLLM health check passes → requests go to **vLLM**
- If vLLM is unavailable or not configured → falls back to **Gemini via Vertex AI**
- Health checks are **cached for 30 seconds** to avoid per-request overhead

---

## Usage

### CLI

```bash
# 1. Create a new project with a plain-English goal
python cli/main.py new "Build a REST API for a todo app with FastAPI and SQLite"

# 2. Plan: Orchestrator writes feature specs, Feature Leads write task specs
python cli/main.py plan

# 3. Run all pending tasks (agents write, test, and commit code)
python cli/main.py run

# 4. Check project status and task board
python cli/main.py status
```

### REST API (FastAPI backend)

Start the backend server:

```bash
uvicorn api:app --reload --port 8080
```

Then use the API (see full reference below):

```bash
# Create a project
curl -X POST http://localhost:8080/api/new \
  -H "Content-Type: application/json" \
  -d '{"goal": "Build a REST API for a todo app", "stack": ["python", "fastapi"]}'

# Run the planning phase
curl -X POST http://localhost:8080/api/plan

# Start task execution (runs in background — returns immediately)
curl -X POST http://localhost:8080/api/run

# Poll for live status
curl http://localhost:8080/api/status
```

### React Dashboard

```bash
cd frontend
npm run dev       # Dev server at http://localhost:5173
npm run build     # Production build
```

---

## API Reference

All endpoints are served at `http://localhost:8080` by default.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/new` | Create a new project (`goal`, `stack`, `constraints`) |
| `POST` | `/api/plan` | Run Orchestrator + Feature Leads — generates all specs |
| `POST` | `/api/run` | Start task execution in background (`task_id?`, `model?`, `max_retries?`) |
| `GET` | `/api/status` | Project metadata + task board + current run state |
| `GET` | `/api/files` | List all generated files in the active project's workspace |
| `GET` | `/api/files/content?path=...` | Read a generated file's contents (path-traversal protected) |
| `GET` | `/api/model-status` | Which backend is live — vLLM or Gemini |
| `GET` | `/health` | Liveness probe (used by Cloud Run) |

### Example: Full workflow via API

```bash
# Step 1 — create project
curl -X POST http://localhost:8080/api/new \
  -d '{"goal":"Todo API","stack":["python","fastapi"],"constraints":["use SQLite"]}'

# Step 2 — plan (blocking — finishes within request timeout)
curl -X POST http://localhost:8080/api/plan

# Step 3 — run (non-blocking — poll /api/status to watch progress)
curl -X POST http://localhost:8080/api/run

# Step 4 — poll until all tasks are done
watch -n 5 'curl -s http://localhost:8080/api/status | python -m json.tool'
```

### `/api/run` response notes

`/api/run` **returns immediately** and runs agents in the background. This is intentional — a full run can take several minutes (each specialist runs a tool-calling loop, plus a 30-second pause between tasks to respect upstream rate limits). Poll `/api/status` to see tasks flip `pending → in_progress → done` in real time.

---

## Deployment

### Docker (local)

```bash
docker build -t agentforge .
docker run -p 8080:8080 --env-file .env agentforge
```

### Google Cloud Run

See [`DEPLOYMENT.md`](DEPLOYMENT.md) and the scripts in `deploy/gcp/` for the full GCP setup.

> **Statelessness note:** This hub keeps all state on the local filesystem (`project.meta.json`, `status/board.json`, `specs/`, `workspace/projects/`). The Cloud Run deploy is pinned to `--min-instances 1 --max-instances 1` so state survives between requests — but a redeploy or instance recycle will reset the workspace. See `DEPLOYMENT.md` for the GCS-backed persistent alternative.

### AWS EC2 (for self-hosted vLLM)

1. Launch a GPU instance (e.g. `g4dn.xlarge`) with the PyTorch Deep Learning AMI
2. Start vLLM on a private port: `python -m vllm.entrypoints.openai.api_server --host 0.0.0.0 --port 8001 --model Qwen/Qwen2.5-Coder-7B-Instruct`
3. Set `VLLM_BASE_URL=http://<ec2-ip>:8001` in your `.env`
4. Run `uvicorn api:app --host 0.0.0.0 --port 8080` on the same or a separate host

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite includes 98+ tests covering the hub internals, the model router, and the API endpoints.

---

## Dependencies

| Package | Purpose |
|---|---|
| `google-adk>=0.3.0` | Core agent framework (ADK loop, tool calling) |
| `click>=8.1.7` | CLI framework |
| `pyyaml>=6.0.1` | Agent config parsing (`config/agents.yaml`) |
| `pydantic>=2.7.0` | Request/response validation |
| `python-dotenv>=1.0.1` | `.env` file loading |
| `rich>=13.7.1` | Pretty terminal output |
| `httpx>=0.27,<1` | Async HTTP client (vLLM health checks, model router) |
| `fastapi` | REST API backend |
| `uvicorn` | ASGI server |

---

## License

[MIT](LICENSE) © rajaganaa
