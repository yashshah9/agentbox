# agentbox

Self-hosted **code execution sandbox** for AI agents — one `docker compose up` gives you an HTTP API for running untrusted code in isolated environments.

> **Status:** v0.2 — Python + Node subprocess sandbox, per-run timeouts, TypeScript client. gVisor isolation is next.

## Problem

Every agent that writes and runs code needs a safe execution environment. Teams either YOLO in shared containers or pay per-second for hosted sandboxes. Self-hosting gVisor/Firecracker is weeks of work.

## Key features (v0.2)

- HTTP API: `POST /v1/run` executes Python or JavaScript
- Per-request `limits.timeout_seconds` (HTTP 408 on timeout)
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
pip install agentbox
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
```

### Python SDK

```python
from agentbox.sdk.client import AgentboxClient

client = AgentboxClient("http://localhost:8080")
print(client.health())
print(client.run("print('hello')"))
print(client.run("console.log('hello')", language="javascript", timeout_seconds=5))
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
| `AGENTBOX_SANDBOX_BACKEND` | `subprocess` | Backend selector |

## Running tests

```bash
pytest tests/ -v
```

## Roadmap

- [x] Node.js runtime + TypeScript client + per-run timeout
- [ ] gVisor runsc backend with warm pool
- [ ] Filesystem snapshot/restore
- [ ] Default-deny egress with allowlists (kernel netns)

## License

MIT

## Known limitations (v0.2)

- Subprocess sandbox only — **not production-grade isolation**
- Credential stripping is not a network namespace
- Single-node, no warm pool
- TypeScript client is source-only (not published to npm)
