"""FastAPI HTTP API."""

import subprocess

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agentbox import __version__
from agentbox.config import Settings
from agentbox.sandbox.docker import DockerSandbox
from agentbox.sandbox.runner import SubprocessSandbox


def create_sandbox(settings: Settings) -> SubprocessSandbox | DockerSandbox:
    """Select execution backend from settings."""
    backend = settings.sandbox_backend.lower().strip()
    if backend == "docker":
        return DockerSandbox(
            timeout_seconds=settings.default_timeout_seconds,
            max_output_bytes=settings.max_output_bytes,
            snapshot_dir=settings.snapshot_dir,
            default_memory_mb=settings.default_memory_mb,
            deny_egress=True,
            docker_image=settings.docker_image,
            docker_node_image=settings.docker_node_image,
        )
    if backend == "unrestricted":
        return SubprocessSandbox(
            timeout_seconds=settings.default_timeout_seconds,
            max_output_bytes=settings.max_output_bytes,
            snapshot_dir=settings.snapshot_dir,
            default_memory_mb=settings.default_memory_mb,
            deny_egress=False,
        )
    # Default: subprocess (easy local tests; not production isolation)
    return SubprocessSandbox(
        timeout_seconds=settings.default_timeout_seconds,
        max_output_bytes=settings.max_output_bytes,
        snapshot_dir=settings.snapshot_dir,
        default_memory_mb=settings.default_memory_mb,
        deny_egress=True,
    )


settings = Settings()
sandbox = create_sandbox(settings)

app = FastAPI(title="agentbox", version=__version__)


class ResourceLimits(BaseModel):
    timeout_seconds: int | None = Field(default=None, ge=1, le=300)
    max_output_bytes: int | None = Field(default=None, ge=1024)
    memory_mb: int | None = Field(default=None, ge=16, le=8192)


class RunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = "python"
    limits: ResourceLimits | None = None
    snapshot: bool = False
    snapshot_id: str | None = None


class LimitsApplied(BaseModel):
    timeout_seconds: int
    memory_mb: int | None = None


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    language: str
    backend: str
    snapshot_id: str | None = None
    limits_applied: LimitsApplied
    oom_killed: bool = False
    network_isolated: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "backend": settings.sandbox_backend}


@app.post("/v1/run", response_model=RunResponse)
def run_code(req: RunRequest) -> RunResponse:
    language = req.language.lower()
    if language not in {"python", "javascript", "node"}:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {req.language}")
    timeout = (
        req.limits.timeout_seconds
        if req.limits and req.limits.timeout_seconds
        else settings.default_timeout_seconds
    )
    memory_mb = (
        req.limits.memory_mb
        if req.limits and req.limits.memory_mb is not None
        else settings.default_memory_mb
    )
    if memory_mb is not None:
        memory_mb = min(memory_mb, settings.max_memory_mb)
    try:
        result = sandbox.run(
            req.code,
            language=language,
            timeout_seconds=timeout,
            snapshot_id=req.snapshot_id,
            persist_snapshot=req.snapshot,
            memory_mb=memory_mb,
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Execution timed out") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
        language=language,
        backend=settings.sandbox_backend,
        snapshot_id=result.snapshot_id,
        limits_applied=LimitsApplied(timeout_seconds=timeout, memory_mb=memory_mb),
        oom_killed=result.oom_killed,
        network_isolated=result.network_isolated,
    )
