# Changelog

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
