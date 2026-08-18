"""Sandbox execution backends."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class SubprocessSandbox:
    """MVP sandbox: isolated temp directory + subprocess timeout.

    ponytail: not production isolation — upgrade path is gVisor/docker backend.
    """

    def __init__(self, timeout_seconds: int = 30, max_output_bytes: int = 1_048_576) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def run_python(self, code: str) -> RunResult:
        import time

        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="agentbox-") as tmp:
            script = Path(tmp) / "main.py"
            script.write_text(code, encoding="utf-8")
            proc = subprocess.run(
                ["python3", str(script)],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                cwd=tmp,
            )
        duration = int((time.monotonic() - start) * 1000)
        stdout = proc.stdout[: self.max_output_bytes]
        stderr = proc.stderr[: self.max_output_bytes]
        return RunResult(stdout=stdout, stderr=stderr, exit_code=proc.returncode, duration_ms=duration)
