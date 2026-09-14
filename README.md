# agentbox

Self-hosted **code execution sandbox** for AI agents — one `docker compose up` gives you an HTTP API for running untrusted code in isolated environments.

[![PyPI](https://img.shields.io/pypi/v/agentbox-sandbox.svg)](https://pypi.org/project/agentbox-sandbox/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/yashshah9/agentbox/actions/workflows/ci.yml/badge.svg)](https://github.com/yashshah9/agentbox/actions/workflows/ci.yml)

> **Status:** v0.7 — Python + Node execution, **Docker sandbox backend** (recommended isolation), subprocess default for local tests, timeouts, memory limits, Linux netns egress deny, TypeScript client, workspace snapshots.

## 60-second try

```bash
pip install agentbox-sandbox
agentbox serve   # API on :8080
# or: docker compose up agentbox
curl -s http://localhost:8080/health
curl -s -X POST http://localhost:8080/v1/run \
  -H 'Content-Type: application/json' \
  -d '{"code":"print(sum(range(10)))"}'
```

## Why this vs alternatives

| Approach | Strength | Gap |
|----------|----------|-----|
| **agentbox** | Self-hosted HTTP API + SDK; Docker or subprocess backends | Not gVisor/Firecracker (yet) |
| Hosted sandboxes (E2B, etc.) | Strong isolation, managed | Per-second cost; data leaves your network |
| Raw `docker exec` | Familiar | No agent-oriented API / snapshots / limits |
| YOLO in the agent process | Zero infra | Full host compromise risk |

## Problem

Every agent that writes and runs code needs a safe execution environment. Teams either YOLO in shared containers or pay per-second for hosted sandboxes. Self-hosting gVisor/Firecracker is weeks of work.

## Key features (v0.7)

- HTTP API: `POST /v1/run` executes Python or JavaScript
- **Docker backend** (`AGENTBOX_SANDBOX_BACKEND=docker`): ephemeral `docker run --rm`, `--network=none`, optional `--memory`, workspace at `/work`
- Subprocess backend remains the **default** for easy local tests
- Per-request `limits.timeout_seconds` (HTTP 408 on timeout)
- Per-request `limits.memory_mb` (Docker `--memory` or subprocess `RLIMIT_AS`); response includes `limits_applied` + `oom_killed`
- `AGENTBOX_MAX_MEMORY_MB` clamps requested memory
- Default-deny egress: Docker uses `--network=none`; subprocess uses Linux `unshare`/`bwrap` when available (`network_isolated` in response)
- Workspace snapshots: `"snapshot": true` then `"snapshot_id"`
- Python SDK + TypeScript client (`sdk/ts/client.ts`)
- Credential stripping when the backend is not `unrestricted`

## Architecture

```
Agent / SDK
    └── POST /v1/run
            ├── SubprocessSandbox (default — easy tests)
            └── DockerSandbox (recommended — stronger isolation)
```

| Component | Technology | Why |
|-----------|------------|-----|
| API | FastAPI | Async-ready, OpenAPI docs, widely adopted |
| Server | uvicorn | Standard ASGI server |
| Config | pydantic-settings | Typed env config |
| Isolation | Docker / subprocess | Docker for production; subprocess for CI/dev |
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

### Recommended: Docker sandbox backend

Requires the Docker CLI (and a reachable daemon) on the host running agentbox:

```bash
export AGENTBOX_SANDBOX_BACKEND=docker
# optional:
# export AGENTBOX_DOCKER_IMAGE=python:3.12-slim
# export AGENTBOX_DOCKER_NODE_IMAGE=node:20-slim
agentbox serve
```

Each `/v1/run` starts an ephemeral container, mounts a temp workspace at `/work`, applies timeout on `docker run`, and removes the container (`--rm`). Health and run responses report `backend: "docker"`.

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

Note: using `AGENTBOX_SANDBOX_BACKEND=docker` from inside a container needs Docker socket access (DinD / mounted socket). Prefer running the API on the host with the Docker backend, or keep the compose service on `subprocess`.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTBOX_HOST` | `0.0.0.0` | Bind host |
| `AGENTBOX_PORT` | `8080` | Bind port |
| `AGENTBOX_DEFAULT_TIMEOUT_SECONDS` | `30` | Execution timeout |
| `AGENTBOX_DEFAULT_MEMORY_MB` | unset | Optional default memory cap |
| `AGENTBOX_MAX_MEMORY_MB` | `8192` | Clamp requested `memory_mb` to this max |
| `AGENTBOX_SANDBOX_BACKEND` | `subprocess` | `subprocess` \| `docker` \| `unrestricted` |
| `AGENTBOX_DOCKER_IMAGE` | `python:3.12-slim` | Image for Python runs (docker backend) |
| `AGENTBOX_DOCKER_NODE_IMAGE` | `node:20-slim` | Image for JavaScript runs (docker backend) |
| `AGENTBOX_SNAPSHOT_DIR` | `/tmp/agentbox-snapshots` | Workspace snapshot store |

## Running tests

```bash
pytest tests/ -v
# Docker unit tests mock the CLI; live Docker run is skipped if docker is unavailable
pytest tests/test_docker.py -v
```

## Roadmap

- [x] Node.js runtime + TypeScript client + per-run timeout
- [x] Filesystem snapshot/restore (tar workspaces)
- [x] `limits.memory_mb` via `RLIMIT_AS` / Docker `--memory`
- [x] Default-deny egress via Linux netns (`unshare`/`bwrap`) when available
- [x] Docker ephemeral-container backend
- [ ] gVisor runsc backend with warm pool
- [ ] Egress allowlists (beyond all-or-nothing netns)

## License

MIT

## Known limitations (v0.7)

- **Subprocess** default is convenient for tests — **not production-grade isolation**; use `AGENTBOX_SANDBOX_BACKEND=docker` for stronger isolation
- Docker backend needs a local Docker CLI/daemon; missing CLI returns a clear 400
- Subprocess `RLIMIT_AS` is a soft address-space cap, not a cgroup memory controller (Docker uses `--memory`)
- Subprocess default-deny egress uses Linux `unshare`/`bwrap` when present; **macOS stays credential-scrub only** (`network_isolated: false`)
- Single-node, no warm pool
- TypeScript client is source-only (not published to npm)
