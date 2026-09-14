# agentbox

Self-hosted **code execution sandbox** for AI agents — one `docker compose up` gives you an HTTP API for running untrusted code in isolated environments.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yashshah9/agentbox/actions/workflows/ci.yml/badge.svg)](https://github.com/yashshah9/agentbox/actions/workflows/ci.yml)

> **Status:** v0.5 — Python + Node subprocess sandbox, timeouts, `limits.memory_mb` / `oom_killed` / `limits_applied`, TypeScript client, workspace snapshots.

## 60-second try

```bash
docker compose up agentbox        # API on :8080
# in another shell:
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"code":"print(sum(range(10)))"}'
docker compose run --rm test      # pytest
```

## Why this vs alternatives

| Approach | Strength | Gap |
|----------|----------|-----|
| **agentbox** | Self-hosted HTTP API + SDK, one compose file | Subprocess isolation today, not gVisor |
| Hosted sandboxes (E2B, etc.) | Strong isolation, managed | Per-second cost; data leaves your network |
| Raw `docker exec` | Familiar | No agent-oriented API / snapshots / limits |
| YOLO in the agent process | Zero infra | Full host compromise risk |

## Problem

Every agent that writes and runs code needs a safe execution environment. Teams either YOLO in shared containers or pay per-second for hosted sandboxes. Self-hosting gVisor/Firecracker is weeks of work.

## Key features (v0.4)

- HTTP API: `POST /v1/run` executes Python or JavaScript
- Per-request `limits.timeout_seconds` (HTTP 408 on timeout)
- Per-request `limits.memory_mb` (sets `RLIMIT_AS`; 16–8192); response includes `limits_applied` + `oom_killed`
- Workspace snapshots: `"snapshot": true` then `"snapshot_id"`
- Python SDK + TypeScript client (`sdk/ts/client.ts`)
- Docker image includes Node.js for the JS runtime
- Credential stripping when the backend is not `unrestricted`

## Architecture

```
Agent / SDK
    └── POST /v1/run
            └── SubprocessSandbox (MVP)
                    └── (next) gVisor / Docker backend
```

| Component | Technology | Why |
|-----------|------------|-----|
| API | FastAPI | Async-ready, OpenAPI docs, widely adopted |
| Server | uvicorn | Standard ASGI server |
| Config | pydantic-settings | Typed env config |
| Tests | pytest + httpx TestClient | Fast API testing |

## Installation

```bash
pip install agentbox-sandbox
pip install -e ".[dev]"
```

## Usage

### Start server

```bash
agentbox serve
# or
docker compose up agentbox
```

### Run code

```bash
curl -X POST http://localhost:8080/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"code": "print(sum(range(10)))"}'

curl -X POST http://localhost:8080/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"code": "x = bytearray(10**9)", "limits": {"memory_mb": 64, "timeout_seconds": 5}}'
```

### Python SDK

```python
from agentbox.sdk.client import AgentboxClient

client = AgentboxClient("http://localhost:8080")
print(client.health())
print(client.run("print('hello')"))
print(client.run("console.log('hello')", language="javascript", timeout_seconds=5))
print(client.run("x = bytearray(10**8)", memory_mb=64))
snap = client.run("open('memo.txt','w').write('kept')", snapshot=True)
print(client.run("print(open('memo.txt').read())", snapshot_id=snap["snapshot_id"]))
client.close()
```

## Docker

```bash
docker compose up agentbox        # start API on :8080
docker compose run --rm test    # run unit tests
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTBOX_HOST` | `0.0.0.0` | Bind host |
| `AGENTBOX_PORT` | `8080` | Bind port |
| `AGENTBOX_DEFAULT_TIMEOUT_SECONDS` | `30` | Execution timeout |
| `AGENTBOX_DEFAULT_MEMORY_MB` | unset | Optional default `RLIMIT_AS` cap |
| `AGENTBOX_MAX_MEMORY_MB` | unset | Clamp requested `memory_mb` to this max |
| `AGENTBOX_SANDBOX_BACKEND` | `subprocess` | Backend selector |
| `AGENTBOX_SNAPSHOT_DIR` | `/tmp/agentbox-snapshots` | Workspace snapshot store |

## Running tests

```bash
pytest tests/ -v
```

## Roadmap

- [x] Node.js runtime + TypeScript client + per-run timeout
- [x] Filesystem snapshot/restore (tar workspaces)
- [x] `limits.memory_mb` via `RLIMIT_AS`
- [ ] gVisor runsc backend with warm pool
- [ ] Default-deny egress with allowlists (kernel netns)

## License

MIT

## Known limitations (v0.4)

- Subprocess sandbox only — **not production-grade isolation**
- `RLIMIT_AS` is a soft address-space cap, not a cgroup memory controller
- Credential stripping is not a network namespace
- Single-node, no warm pool
- TypeScript client is source-only (not published to npm)
