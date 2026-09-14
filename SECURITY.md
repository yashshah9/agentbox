# Security Policy

## Reporting a vulnerability

Email **yash376351@gmail.com** with the repo name, a short description, and steps to reproduce. Please do not open a public issue for exploitable findings until we have had a reasonable chance to respond.

## Threat model (honest)

agentbox executes **untrusted code** on your machine via a subprocess sandbox.

- The current backend is **subprocess + optional `RLIMIT_AS`**, not gVisor/Firecracker. Do **not** expose it to the public internet as-is.
- Credential stripping and timeouts reduce accidents; they are **not** a kernel isolation story.
- `limits.memory_mb` caps address space via `RLIMIT_AS` — it is not a cgroup memory controller and behavior differs by OS.
- Snapshots persist workspace files on disk under `AGENTBOX_SNAPSHOT_DIR`.
- Prefer running the API only on trusted networks, behind auth you add yourself.
