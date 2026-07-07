# my-agent-hub

[![CI](https://github.com/rajaganaa/spec-driven-multi-ai-agents-/actions/workflows/ci.yml/badge.svg)](https://github.com/rajaganaa/spec-driven-multi-ai-agents-/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**A spec-driven, autonomous multi-agent coding system** -- similar in spirit to Cursor Agent or Codex, but self-hosted and built on Google ADK + Gemini.

You give it a single goal in plain English. A hierarchy of agents plans it, breaks it into specs and tasks, writes the code, tests it, and commits it -- end to end, with no manual coding required.

## How it works

    You (plain English goal)
            |
            v
    Level 0 - Orchestrator          (gemini-2.5-pro)
            |   writes project plan + feature specs
            v
    Level 1 - Feature Leads         (gemini-2.5-pro, one per feature)
            |   break features into task specs
            v
    Level 2 - Specialists           (gemini-2.5-flash)
      Explorer . Coder . Tester . Reviewer
            |   execute tasks via tools
            v
    Tools Layer
      read_file . write_file . apply_patch . list_dir
      search_code . run_terminal . git_status . git_commit
            |
            v
    workspace/projects/project_id/   (all file ops sandboxed here)

Each agent only ever sees its own spec file plus a handful of relevant files (max ~15k tokens) -- never the full chat history.

## Folder structure

    my-agent-hub/
    - cli/main.py               CLI entry point (new / plan / run / status)
    - config/agents.yaml        Agent config (models, tool allowlists)
    - hub/agents/                Orchestrator, Feature Lead, Specialists
    - hub/memory/spec_loader.py  Loads specs, builds agent context
    - hub/runner/task_runner.py  Picks agent, runs ADK loop, git commit
    - hub/tools/tools.py         All tool functions, path-sandboxed
    - hub/eval/                  Golden tasks + LLM-as-judge eval suite
    - specs/features/            F01-auth.md, F02-api.md, etc
    - specs/tasks/                F01/T01-models.md, etc
    - frontend/                   React dashboard (Vite)
    - status/board.json           Task progress tracker
    - workspace/projects/         project_id/ - all generated code lives here

## Setup

### Prerequisites
- Python 3.11
- Either a Google AI Studio API key at aistudio.google.com, or a GCP project with Vertex AI enabled plus a service account

### 1. Clone

    git clone https://github.com/rajaganaa/spec-driven-multi-ai-agents-.git
    cd spec-driven-multi-ai-agents-

### 2. Create a virtual environment

    python3.11 -m venv .venv
    source .venv/bin/activate

On Windows use: .venv\Scripts\activate

### 3. Install dependencies

    pip install -r requirements.txt

### 4. Configure environment

    cp .env.example .env

Then edit .env and set one of:
- GOOGLE_API_KEY (simplest, Google AI Studio), or
- GOOGLE_GENAI_USE_VERTEXAI=true plus GOOGLE_CLOUD_PROJECT and credentials (Vertex AI)

Never commit your real .env or a service-account key file. It is already gitignored.

### 5. Verify install

    python -c "import google.adk; print('ADK OK')"
    python cli/main.py --help

## Usage

    python cli/main.py new "Build a hello world FastAPI app"
    python cli/main.py plan
    python cli/main.py run
    python cli/main.py run --task T01
    python cli/main.py status

Generated code appears under workspace/projects/project_id/, git-committed after every completed task.

## Running the eval suite

    pytest tests/ -v
    python -m hub.eval.runner

## Key design rules

- Specs are memory -- agents read only their task spec, never full chat history
- Sandboxed workspace -- all file ops stay inside workspace/projects/id/
- Git checkpoints -- auto-commit after every completed task
- Fresh context per agent -- spec plus up to 5 relevant files, ~15k token cap
- Human gate -- approval required before destructive shell commands

## Contributing

Each hub/ sub-package has a STUB comment at the top indicating which part implements it. See CONTRIBUTING.md for module ownership and workflow.

## License

MIT