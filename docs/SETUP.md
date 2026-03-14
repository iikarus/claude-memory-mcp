# Setup Guide — Claude Memory MCP

> **Goal**: Go from a fresh machine to a fully working Claude Memory system. Written for both human developers and AI agents (Claude Code, Antigravity, etc.) to follow with minimal intervention.

---

## Prerequisites Checklist

Before starting, ensure these are installed. An AI agent should verify each one.

| Requirement | Version | Check Command | Install Guide |
|-------------|---------|---------------|---------------|
| **Git** | any | `git --version` | [git-scm.com](https://git-scm.com) |
| **Python** | 3.12+ | `python --version` | [python.org](https://python.org) |
| **pip** | 23+ | `pip --version` | Ships with Python |
| **Docker** | 24+ | `docker --version` | [docker.com](https://docs.docker.com/get-docker/) |
| **Docker Compose** | v2+ | `docker compose version` | Ships with Docker Desktop |

### Platform Notes

<details>
<summary><strong>Windows</strong></summary>

- Install **Docker Desktop** and enable WSL2 backend.
- Use **PowerShell 7+** (`pwsh`) for all commands.
- Python: install via [python.org](https://python.org) or `winget install Python.Python.3.12`.
- Ensure Docker Desktop is **running** before proceeding (check system tray icon).

</details>

<details>
<summary><strong>macOS</strong></summary>

- Install **Docker Desktop** from [docker.com](https://docs.docker.com/desktop/install/mac-install/).
- Python: `brew install python@3.12`.
- GPU acceleration is **not available** on macOS — CPU mode works fine.

</details>

<details>
<summary><strong>Linux</strong></summary>

- Install Docker Engine: `sudo apt install docker.io docker-compose-v2` (Ubuntu/Debian).
- Python: `sudo apt install python3.12 python3.12-venv`.
- GPU: install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) for GPU acceleration.

</details>

---

## Step 1: Clone and Install

```bash
# Clone the repository
git clone https://github.com/iikarus/claude-memory-mcp.git
cd claude-memory-mcp

# Create a virtual environment (recommended)
python -m venv .venv

# Activate it
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

# Install the project and dev dependencies
pip install -e ".[dev]"
```

**Verification**: `python -c "import claude_memory; print('OK')"` should print `OK`.

### Updating to the Latest Version

Already installed? Pull the latest code and re-install:

```bash
# From inside the claude-memory-mcp directory
git pull origin master
pip install -e ".[dev]"
```

If Docker images have changed (check the release notes), also run:

```bash
docker compose pull
docker compose up -d
```

---

## Step 2: Start Docker Services

```bash
# CPU mode (works everywhere, ~2GB download on first run)
docker compose up -d

# OR: GPU mode (requires NVIDIA GPU + nvidia-docker)
docker compose --profile gpu up -d
```

This starts 4 containers:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `graphdb` | FalkorDB v4.14.11 | 6379 | Knowledge graph (Cypher queries) |
| `qdrant` | Qdrant v1.16.3 | 6333 | Vector similarity search |
| `embeddings` | Custom (BGE-M3) | 8001 | Text → 1024-dim embeddings (CPU by default) |
| `dashboard` | Custom (Streamlit) | 8501 | Visual graph explorer |

**Wait for health checks** (takes 30-90 seconds on first run):

```bash
# Watch until all show "healthy"
docker compose ps

# Or use the healthcheck script (Windows PowerShell):
powershell -File scripts/healthcheck.ps1
```

**Verification**: All 4 services show `(healthy)` in `docker compose ps`.

> **First-run note**: The embeddings container downloads the BGE-M3 model (~2GB) on first start. This is cached in the Docker image layer for subsequent runs.

---

## Step 3: Configure Your MCP Client

Choose your Claude client below. You only need ONE of these.

### Option A: Claude Desktop

1. Find your config file:
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/claude/claude_desktop_config.json`

2. Add the `claude-memory` server block. Replace `PROJECT_ROOT` with the absolute path to your clone:

```json
{
  "mcpServers": {
    "claude-memory": {
      "command": "powershell.exe",
      "args": ["-ExecutionPolicy", "Bypass", "-File", "PROJECT_ROOT/scripts/run_mcp_server.ps1"],
      "env": {
        "PYTHONPATH": "PROJECT_ROOT/src",
        "FALKORDB_HOST": "localhost",
        "FALKORDB_PORT": "6379",
        "QDRANT_HOST": "localhost",
        "QDRANT_PORT": "6333",
        "EMBEDDING_API_URL": "http://localhost:8001"
      }
    }
  }
}
```

> **macOS/Linux**: Replace `"command": "powershell.exe"` with `"command": "python"` and `"args"` with `["-m", "claude_memory.server"]`.

3. **Restart Claude Desktop** to pick up the new config.

A working template is provided at `mcp_config.example.json` in the repo root.

### Option B: Claude Code CLI

```bash
# Register the MCP server
claude mcp add claude-memory -- python -m claude_memory.server

# Set required environment variables
# Option 1: Export in your shell profile (~/.bashrc, ~/.zshrc, $PROFILE)
export FALKORDB_HOST=localhost
export FALKORDB_PORT=6379
export QDRANT_HOST=localhost
export QDRANT_PORT=6333
export EMBEDDING_API_URL=http://localhost:8001

# Option 2: Create a .env file in the project root
cat > .env << 'EOF'
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
QDRANT_HOST=localhost
QDRANT_PORT=6333
EMBEDDING_API_URL=http://localhost:8001
EOF
```

### Option C: Other MCP Clients (VS Code, Cursor, etc.)

The MCP server runs via stdio transport. Any MCP-compatible client can connect:

```bash
# The server command is always:
python -m claude_memory.server

# With PYTHONPATH set to the src/ directory:
PYTHONPATH=./src python -m claude_memory.server
```

Environment variables listed in the table below must be set.

---

## Environment Variables Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `FALKORDB_HOST` | `localhost` | Yes | FalkorDB hostname |
| `FALKORDB_PORT` | `6379` | Yes | FalkorDB port |
| `FALKORDB_PASSWORD` | *(empty)* | No | FalkorDB password (none by default in docker-compose) |
| `QDRANT_HOST` | `localhost` | Yes | Qdrant hostname |
| `QDRANT_PORT` | `6333` | Yes | Qdrant port |
| `EMBEDDING_API_URL` | `http://localhost:8001` | Yes | Embedding service URL |
| `PYTHONPATH` | — | Yes* | Must include `src/` dir (*unless installed via pip*) |
| `EXOCORTEX_BACKUP_DIR` | *(none)* | No | Custom backup destination path |
| `EXOCORTEX_STRICT_CONSISTENCY` | `true` | No | Fail on Qdrant write errors (vs. warn) |

---

## Step 4: Verify Everything Works

### Quick Smoke Test

Once your MCP client is connected, try these commands in a Claude conversation:

```
"Create an entity called 'Setup Test' of type 'Concept'"
"Search for 'Setup Test'"
"Run system diagnostics"
```

If all three work, you're fully operational.

### Programmatic Verification

```bash
# Run the health check (Windows)
powershell -File scripts/healthcheck.ps1

# Run the test suite
tox -e pulse

# Run the E2E smoke test (requires Docker running)
python scripts/e2e_test.py
```

Expected output from `healthcheck.ps1`:
```
[CHECK] FalkorDB at localhost:6379... OK
[CHECK] Qdrant at http://localhost:6333/healthz... OK
[CHECK] Embedding at http://localhost:8001/health... OK
[CHECK] Backup status file... MISSING (no status file)
[CHECK] MCP server process... NOT RUNNING
[RESULT] FAILING: Backup(no_status_file), MCP_Server(not_running)
```

> The backup and MCP server warnings are expected on a fresh install. Backups are configured separately (see Step 5), and the MCP server runs on-demand via your Claude client.

---

## Step 5: Optional Setup

### Scheduled Backups (Windows)

```powershell
# Set up daily backup task in Windows Task Scheduler
powershell -File scripts/setup_scheduled_tasks.ps1
```

This creates a daily backup job that exports graph data and vector snapshots. Set `EXOCORTEX_BACKUP_DIR` to customize the destination.

### Dashboard Access

The Streamlit dashboard is available at **http://localhost:8501** when Docker is running. It provides:
- Graph visualization
- Entity browser
- Search interface
- System diagnostics

### Running Tests

```bash
# Quick lint + test + coverage
tox -e pulse

# Full quality gates
tox -e gate      # Hypothesis property tests + diff-cover
tox -e hammer    # Security (bandit, pip-audit, detect-secrets)
tox -e polish    # Documentation coverage + spell check
```

---

## Troubleshooting

### Docker containers won't start

```bash
# Check logs for the failing service
docker compose logs embeddings
docker compose logs graphdb

# Common fix: restart Docker Desktop, then:
docker compose down
docker compose up -d
```

### "Connection refused" errors

The MCP server can't reach the Docker services. Verify:
1. Docker containers are running: `docker compose ps`
2. Ports aren't blocked: `curl http://localhost:8001/health`
3. Environment variables are set correctly

### Embedding service takes forever to start

First-run downloads the BGE-M3 model (~2GB). Check progress:
```bash
docker compose logs -f embeddings
```

Subsequent starts use the cached model and should be fast (~10s).

### MCP server crashes or hangs

The `run_mcp_server.ps1` wrapper auto-restarts up to 5 times. Check logs at:
```
logs/mcp_server_restarts.log
```

Common causes:
- Docker not running → start Docker Desktop
- Port conflict → check `netstat -an | findstr "6379 6333 8001"`
- Python import error → ensure `pip install -e ".[dev]"` completed

### "Unexpected non-whitespace character after JSON"

This means stdout is contaminated. The MCP server uses stdio transport — all logging MUST go to stderr. Check that no `print()` statements exist in server code.

---

## Architecture Summary

```
┌──────────────────────┐     stdio      ┌──────────────────┐
│ Claude Desktop/CLI   │◄──────────────►│ MCP Server       │
│ (MCP client)         │                │ (Python process)  │
└──────────────────────┘                └────────┬─────────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        │                        │                        │
                        ▼                        ▼                        ▼
               ┌────────────────┐     ┌──────────────────┐     ┌─────────────────┐
               │ FalkorDB       │     │ Qdrant           │     │ Embedding API   │
               │ (Knowledge     │     │ (Vector Search)  │     │ (BGE-M3 model)  │
               │  Graph)        │     │                  │     │                 │
               │ Port 6379      │     │ Port 6333        │     │ Port 8001       │
               └────────────────┘     └──────────────────┘     └─────────────────┘
```

The MCP server is a **separate process** from the Docker containers. Docker runs the storage backends (FalkorDB, Qdrant) and the embedding service. The MCP server runs locally as a Python process spawned by your Claude client.

---

## For AI Agents: Automated Setup Sequence

If you're an AI agent setting this up, here's the exact command sequence. Run each step and verify before proceeding.

```bash
# 1. Prerequisites (verify these exist)
git --version          # must succeed
python --version       # must be 3.12+
docker --version       # must succeed
docker compose version # must be v2+

# 2. Clone and install
git clone https://github.com/iikarus/claude-memory-mcp.git
cd claude-memory-mcp
python -m venv .venv
# Activate venv (platform-dependent)
pip install -e ".[dev]"

# 3. Start services
docker compose up -d
# Wait for healthy (poll every 10s, timeout 120s)
# CHECK: docker compose ps | all show (healthy)

# 4. Verify services
curl -s http://localhost:8001/health   # expect {"status":"ok"}
curl -s http://localhost:6333/healthz  # expect "ok" or HTTP 200

# 5. Register MCP server (Claude Code CLI)
claude mcp add claude-memory -- python -m claude_memory.server
# Set env vars in shell profile or .env

# 6. Smoke test (in a Claude conversation)
# "Run system diagnostics" → should return tool counts, graph stats
```

**Human intervention required for**:
- Installing Docker Desktop (OS-level installer)
- Approving the Claude Desktop config file edit (requires app restart)
- Providing GPU driver setup if GPU acceleration is desired
