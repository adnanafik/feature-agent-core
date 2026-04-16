# Feature Agent Core

The backend brain of an autonomous AI coding agent. Accepts feature requests, explores a target codebase, writes code and tests, and opens GitHub PRs — autonomously.

Built for the "Building Agentic AI Systems" course by Adnan Khan.

## Setup

1. Clone this repo
2. `cp .env.example .env` and fill in your API keys
3. `docker compose up`
4. Open http://localhost:8000/docs

## Running Tests

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

## Architecture

See [CLAUDE.md](CLAUDE.md) for full architecture documentation.
