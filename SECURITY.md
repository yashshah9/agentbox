# Security Policy

## Reporting a vulnerability

Email **yash376351@gmail.com** with the repo name, a short description, and steps to reproduce. Please do not open a public issue for exploitable findings until we have had a reasonable chance to respond.

## Threat model (honest)

agentbox executes **untrusted code** on your machine via a configurable sandbox backend.

- **Recommended:** `AGENTBOX_SANDBOX_BACKEND=docker` — ephemeral containers (`--rm`, `--network=none`, optional `--memory`). Still not gVisor/Firecracker; do **not** expose it to the public internet without additional hardening/auth.
- **Default:** `subprocess` + optional `RLIMIT_AS` — convenient for local tests, **not** production-grade isolation.
- Credential stripping and timeouts reduce accidents; they are **not** a full kernel isolation story.
- `limits.memory_mb` uses Docker `--memory` (docker backend) or `RLIMIT_AS` (subprocess); behavior differs by OS/backend.
- Snapshots persist workspace files on disk under `AGENTBOX_SNAPSHOT_DIR`.
- Prefer running the API only on trusted networks, behind auth you add yourself.
