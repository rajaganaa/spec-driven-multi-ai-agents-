# AgentForge — Industry Grade Upgrade

This implements the 7-part upgrade (vLLM primary + Gemini fallback,
FastAPI backend, React dashboard, AWS + GCP deploy) against the real
`my-agent-hub` code. All 98 original tests still pass, plus 7 new ones
covering the router and the API. Hub internals (tools, memory,
spec_loader, orchestrator, feature_lead, specialists, task_runner)
were not rewritten — only wrapped/extended, per the original ask.

**Read this before deploying anything** — a few things in the original
plan didn't match the real codebase or had rough edges; they're fixed
here, and called out below so nothing's a surprise later.

## What changed vs. the original instructions

- **`api.py`'s draft imports were wrong.** `from cli.main import _new`
  doesn't exist — `cli/main.py` uses Click commands, not bare
  functions. Fixed by extracting `create_project_meta()` as a real
  shared function both the CLI and the API call.
- **`/api/plan` would have crashed.** Calling the synchronous
  `run_orchestrator()` / `run_feature_lead()` wrappers from inside
  FastAPI's already-running event loop raises `asyncio.run() cannot be
  called from a running event loop`. Fixed by awaiting
  `run_orchestrator_async()` / `run_feature_lead_async()` directly —
  caught this with an actual integration test, not just by reading the
  code.
- **Eager `LiteLlm` import would have broken everything, even with
  vLLM untouched.** `litellm` is an optional extra of `google-adk`, not
  a base dependency. Importing it at the top of `config.py` (which
  *every* agent module imports) would crash the whole hub for anyone
  who hasn't installed it — including before you ever touch vLLM.
  Fixed with a lazy import inside `resolve_model()`, only when
  `VLLM_BASE_URL` is actually set and healthy.
- **vLLM health checks are cached (30s TTL)**, not hit on every single
  agent build — the original draft's `httpx.get(..., timeout=3)` on
  every call would add latency to every specialist invocation,
  multiplied by however many tasks run.
- **`/api/run` runs in the background**, not inline. `run_pending_tasks`
  sleeps 30s between tasks on purpose (rate-limit avoidance) — a real
  run can take many minutes, too long for one HTTP request/proxy
  timeout. The endpoint now returns immediately; poll `GET /api/status`
  to watch tasks flip pending → in_progress → done in real time
  (`status/board.json` is updated per-task, so this actually works).
- **No hardcoded secrets.** `agentforge-key-2026` is gone — `VLLM_API_KEY`
  has no default and the setup script refuses to start without one.
  CORS is no longer `allow_origins=["*"]` unconditionally — set
  `FRONTEND_ORIGIN` (a loud warning prints if you don't).
- **The GCP credential path from the original prompt
  (`E:\password\...json`) is not reproduced anywhere in this codebase.**
  If that path/key has ever been shared outside your machine, rotate
  the key. Deploy scripts use the Cloud Run service's own runtime
  service account (Application Default Credentials) instead of a
  mounted JSON key.
- **Frontend is Vite, not Create React App.** CRA has been
  unmaintained since 2023; Vite is the standard React tool now. Same
  React 18, no extra UI libraries, exactly as asked.
- **GitHub Pages workflow** uses GitHub's current first-party Pages
  actions (`configure-pages`/`upload-pages-artifact`/`deploy-pages`).
  I don't have access to the `anbu-health-ai` repo the original
  instructions referenced, so this is the standard modern pattern, not
  a copy of that repo's workflow.
- **Statelessness gap on Cloud Run, flagged rather than hidden:** this
  hub keeps all state (`project.meta.json`, `status/board.json`,
  `specs/`, `workspace/projects/`, git history) on local disk. A bare
  Cloud Run deploy can run multiple non-shared instances — instance #2
  wouldn't see what instance #1 created. `deploy/gcp/deploy.sh` pins
  `--min-instances 1 --max-instances 1` so there's always exactly one,
  which makes this work for a personal/demo setup — but a redeploy or
  instance recycle still wipes the workspace, since that's still not
  persistent storage. See the comment block at the top of that script
  for the two real fixes (GCS volume mount, or move off Cloud Run onto
  a small persistent VM) if this needs to survive that.

## Repo additions

```
hub/agents/config.py          + resolve_model() / is_vllm_healthy() / get_model_router_status()
hub/agents/orchestrator.py    1-line change: route default model through resolve_model()
hub/agents/feature_lead.py    same
hub/agents/specialists/*.py   same, x4 (coder, explorer, tester, reviewer)
cli/main.py                   extracted create_project_meta() (reused by api.py)
api.py                        NEW — FastAPI backend (Part 4)
requirements.txt              + fastapi, uvicorn, httpx, litellm
.env.example                  NEW — template only, no real secrets
.gitignore                    NEW — didn't exist before; now ignores .env, keys, node_modules, generated workspace
tests/test_model_router.py    NEW — 6 tests for the router
tests/test_api.py             NEW — full new→plan→run→status→files cycle through the real FastAPI app
deploy/aws/01_launch_ec2.sh   NEW — Part 1: provisions the EC2 box
deploy/aws/02_setup_vllm.sh   NEW — Part 1: installs vLLM as a systemd service
Dockerfile                    NEW — Part 7
deploy/gcp/deploy.sh          NEW — Part 7
frontend/                     NEW — Part 5: Vite + React dashboard
.github/workflows/deploy-frontend.yml   NEW — Part 5: GitHub Pages deploy
```

## End-to-end setup order

### 1. Local sanity check (no AWS/GCP needed yet)

```bash
pip install -r requirements.txt --break-system-packages
python -m pytest tests/ -q          # should show all passing
uvicorn api:app --reload --port 8080
```

`VLLM_BASE_URL` is unset, so the router is a no-op and this behaves
exactly like the hub did before — Gemini only, no vLLM involved.

### 2. Frontend, pointed at your local API

```bash
cd frontend
cp .env.example .env        # VITE_API_URL=http://localhost:8080 by default
npm install
npm run dev
```

Open the printed localhost URL — Build tab creates a project, Plan
decomposes it, Run kicks off tasks in the background, Status tab polls
and shows them go pending → running → done, Files tab lets you read
what got generated. The pill in the header shows `gemini · no vllm
configured` until you do step 3.

### 3. Stand up the vLLM box (Part 1, optional — skip if Gemini-only is fine for now)

```bash
chmod +x deploy/aws/*.sh
KEY_NAME=your-ec2-keypair-name ./deploy/aws/01_launch_ec2.sh
# follow the printed scp/ssh instructions, then on the box:
VLLM_API_KEY=$(openssl rand -hex 24) ./02_setup_vllm.sh
```

Put the printed IP and the key you chose into your local `.env`
(see `.env.example`), restart `uvicorn`, and the header pill should
flip to `vllm · Qwen2.5-Coder-7B-Instruct`. Kill the vLLM service on
the box (or stop the instance) and it falls back to `gemini` within
~30s (the health-check cache TTL) — that's the whole point of this
upgrade.

**Cost reminder:** g4dn.xlarge is ~$0.526/hr on-demand. Stop the
instance (`aws ec2 stop-instances --instance-ids <id>`) when you're not
using it — your $106 credit goes fast left running continuously.

### 4. Deploy the API to Cloud Run (Part 7)

```bash
GCP_PROJECT=your-project FRONTEND_ORIGIN=https://you.github.io \
  VLLM_BASE_URL=http://<ec2-ip>:8000/v1 \
  ./deploy/gcp/deploy.sh
```

Read the script's top comment block first — the statelessness note
above is real, not boilerplate.

### 5. Deploy the frontend to GitHub Pages (Part 5)

In the repo's GitHub Settings → Secrets and variables → Actions, add a
secret `VITE_API_URL` set to the Cloud Run URL from step 4. Push to
`main` (or run the workflow manually) — `.github/workflows/deploy-frontend.yml`
builds and deploys `frontend/` automatically. Also enable GitHub Pages
in Settings → Pages → Source: GitHub Actions (one-time, if not already
on).

## Endpoint reference (`api.py`)

| Method | Path                  | Notes |
|--------|-----------------------|-------|
| POST   | `/api/new`            | `{goal, stack?, constraints?}` — instant, no LLM call |
| POST   | `/api/plan`           | `{model?}` — Orchestrator + Feature Leads, awaited inline |
| POST   | `/api/run`            | `{task_id?, model?, max_retries?}` — **backgrounded**, returns immediately |
| GET    | `/api/status`         | project + task board + whether a run is currently in flight |
| GET    | `/api/files`          | list of generated files for the active project |
| GET    | `/api/files/content?path=...` | one file's content (path-traversal guarded) |
| GET    | `/api/model-status`   | which backend (vLLM/Gemini) is actually serving right now |
| GET    | `/health`             | liveness probe |
