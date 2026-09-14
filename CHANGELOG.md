# Changelog

## [0.6.0] - 2026-09-14

### Added
- Real default-deny egress on Linux when possible: wrap runs with `unshare --net` (preferred) or `bwrap --unshare-net`
- Run response includes `network_isolated` so callers know whether netns wrapping applied

### Notes
- macOS and hosts without `unshare`/`bwrap` still scrub credentials only (`network_isolated: false`)

## [0.5.0] - 2026-09-14

### Added
- Run response includes `limits_applied: {timeout_seconds, memory_mb}` (values after defaults/clamping)
- Run response includes `oom_killed` heuristic for memory-limit failures
- `AGENTBOX_MAX_MEMORY_MB` clamps requested `memory_mb` (reports clamped value in `limits_applied`)

## [0.4.0] - 2026-09-14

### Added
- `limits.memory_mb` on `POST /v1/run` — applies `RLIMIT_AS` in the child process (16–8192 MB)
- Optional `AGENTBOX_DEFAULT_MEMORY_MB` and SDK `memory_mb=` passthrough

## [0.3.0] - 2026-08-19

### Added
- Workspace snapshot/restore (`snapshot: true` / `snapshot_id`) so agents can keep files across runs

## [0.2.0] - 2026-08-19

### Added
- JavaScript/Node runtime (`language: javascript|node`)
- Per-request `limits.timeout_seconds` (408 on timeout)
- TypeScript client at `sdk/ts/client.ts`
- Credential stripping when backend is not `unrestricted`

### Notes
- Isolation is still subprocess, not gVisor

## [0.1.0] - 2026-08-18

### Added
- FastAPI service with /health and /v1/run
- Subprocess sandbox backend (MVP)
- Python SDK client skeleton
