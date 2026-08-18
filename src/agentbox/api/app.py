"""FastAPI HTTP API."""

import subprocess

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from agentbox import __version__
from agentbox.config import Settings
from agentbox.sandbox.runner import SubprocessSandbox

settings = Settings()
sandbox = SubprocessSandbox(
    timeout_seconds=settings.default_timeout_seconds,
    max_output_bytes=settings.max_output_bytes,
)

app = FastAPI(title="agentbox", version=__version__)


class RunRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = "python"


class RunResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__, "backend": settings.sandbox_backend}


@app.post("/v1/run", response_model=RunResponse)
def run_code(req: RunRequest) -> RunResponse:
    if req.language != "python":
        raise HTTPException(status_code=400, detail=f"Unsupported language: {req.language}")
    try:
        result = sandbox.run_python(req.code)
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=408, detail="Execution timed out") from exc
    return RunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        duration_ms=result.duration_ms,
    )
