# Quick Start — Full System

The Feature Agent system has three independent repos:

1. **feature-agent-core** — agent backend (this is the brain)
2. **feature-agent-client** — web UI (this is the face)
3. **projectflow-api** — sample target codebase (this is the canvas)

## Order to set up

### 1. Clone all three repos

```bash
git clone https://github.com/feature-agent/feature-agent-core
git clone https://github.com/feature-agent/feature-agent-client
# (projectflow-api: only the agent will clone this on demand —
#  but fork it on GitHub so you have a target repo to point at)
```

### 2. Fork projectflow-api on GitHub

Go to https://github.com/feature-agent/projectflow-api and click
**Fork** so it lives at `YOUR_USERNAME/projectflow-api`. The agent
will open PRs against your fork, not the original.

### 3. Generate API keys

- Claude API key: https://console.anthropic.com → API Keys
- GitHub Personal Access Token: github.com → Settings →
  Developer settings → Personal access tokens (classic) with
  `repo` scope

### 4. Start the agent backend

```bash
cd feature-agent-core
cp .env.example .env  # no edits needed
docker compose up
```

Wait for "Server is ready" and "Subscribed to stream".

### 5. Start the web client

In a new terminal:

```bash
cd feature-agent-client
cp config.example.js config.local.js
# Edit config.local.js — paste in your Claude key and GitHub token
docker compose up -d
```

### 6. Open the dashboard

http://localhost:8080

Submit your first feature request against
`YOUR_USERNAME/projectflow-api`.

## Tear down

```bash
cd feature-agent-core   && docker compose down -v
cd feature-agent-client && docker compose down -v
```
