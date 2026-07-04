# my-agent-hub

A **spec-driven multi-agent coding system** built on Google ADK and Gemini.

You describe a goal in plain English → the Orchestrator decomposes it into spec files →
Feature Lead agents break specs into tasks → Specialist agents execute with tools →
git checkpoints after every completed task.

---

## Architecture

```
You (plain English goal)
        │
        ▼
Level 0 — Orchestrator          (gemini-2.5-pro)
        │   writes project plan + feature specs
        ▼
Level 1 — Feature Leads         (gemini-2.5-pro, one per feature)
        │   break features into task specs
        ▼
Level 2 — Specialists           (gemini-2.5-flash)
  Explorer · Coder · Tester · Reviewer
        │   execute tasks via tools
        ▼
Tools Layer
  read_file · write_file · apply_patch · list_dir
  search_code · run_terminal · git_status · git_commit
        │
        ▼
workspace/projects/<project_id>/   ← ALL file ops sandboxed here
```

---

## Folder Structure

```
my-agent-hub/
├── cli/
│   └── main.py               # CLI entry point (new / plan / run / status)
├── config/
│   └── agents.yaml           # Agent config (models, tool allowlists)
├── hub/
│   ├── agents/
│   │   ├── orchestrator.py   # Level 0 — Orchestrator (Part D)
│   │   ├── feature_lead.py   # Level 1 — Feature Lead  (Part D)
│   │   └── specialists/      # Level 2 — Explorer, Coder, Tester, Reviewer (Part E)
│   ├── memory/
│   │   └── spec_loader.py    # Load specs + build agent context (Part C)
│   ├── runner/
│   │   └── task_runner.py    # Pick agent, run ADK loop, git commit (Part E)
│   ├── tools/
│   │   └── tools.py          # All tool functions, path-sandboxed (Part B)
│   └── eval/                 # Golden tasks + LLM-as-judge (Part I)
├── specs/
│   ├── features/             # F01-auth.md, F02-api.md, …
│   └── tasks/                # F01/T01-models.md, …
├── status/
│   └── board.json            # Task progress tracker
├── workspace/
│   └── projects/             # <project_id>/ — all generated code lives here
├── project.meta.json         # Active project metadata
└── requirements.txt
```

---

## Setup

### Prerequisites
- Python 3.11
- A Google AI Studio API key → [aistudio.google.com](https://aistudio.google.com)
- (Optional) Docker — required for sandboxed terminal tool in Part B

### 1. Clone / download

```bash
git clone <your-repo-url>
cd my-agent-hub
```

### 2. Create virtual environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set your Gemini API key

```bash
# Option A — environment variable (recommended)
export GOOGLE_API_KEY="your-api-key-here"

# Option B — .env file (create in project root)
echo 'GOOGLE_API_KEY=your-api-key-here' > .env
```

### 5. Verify install

```bash
python -c "import google.adk; print('ADK OK')"
python cli/main.py --help
```

---

## Usage

### Start a new project

```bash
python cli/main.py new "Build a HIPAA-aware medical FAQ chatbot with FastAPI and React"
```

### Plan features (runs Orchestrator)

```bash
python cli/main.py plan
```

This writes `specs/features/F*.md` files.

### Run all pending tasks

```bash
python cli/main.py run
```

### Run a specific task

```bash
python cli/main.py run --task T01
```

### Check status board

```bash
python cli/main.py status
```

---

## Build Order (5-Part Split)

| Part | Who builds | What |
|------|-----------|------|
| A (this) | Claude 1 | Folder scaffold, CLI stub, config |
| B | Claude 2 | `hub/tools/tools.py` — all tool functions |
| C | Claude 3 | `hub/memory/spec_loader.py` — spec system |
| D | Claude 4 | Orchestrator + Feature Lead agents |
| E | Claude 5 | Specialist agents + TaskRunner + wire CLI |

When all parts are ready:

```bash
pip install -r requirements.txt
python cli/main.py new "build a hello world FastAPI app"
python cli/main.py plan
python cli/main.py run
python cli/main.py status
```

---

## Key Design Rules

- **Specs = memory** — agents read only their task spec, never full chat history
- **Sandboxed workspace** — all file ops stay inside `workspace/projects/<id>/`
- **Git checkpoints** — auto-commit after every completed task spec
- **Fresh context per agent** — spec + up to 5 relevant files, max ~15k tokens
- **Human gate** — approval required before destructive shell commands

---

## Contributing

Each `hub/` sub-package has a `STUB` comment at the top indicating which Part implements it.
Add your code there and remove the `raise NotImplementedError` line.
