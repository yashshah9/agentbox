"""Sandbox execution backends."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int


class Sandbox(Protocol):
    def run(self, code: str, language: str, timeout_seconds: int | None = None) -> RunResult:
        ...


class SubprocessSandbox:
    """MVP sandbox: isolated temp directory + subprocess timeout.

    ponytail: not production isolation — upgrade path is gVisor/docker backend.
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_bytes: int = 1_048_576,
        deny_egress: bool = False,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.deny_egress = deny_egress

    def run(self, code: str, language: str = "python", timeout_seconds: int | None = None) -> RunResult:
        timeout = timeout_seconds or self.timeout_seconds
        start = time.monotonic()
        env = self._env()
        with tempfile.TemporaryDirectory(prefix="agentbox-") as tmp:
            if language == "python":
                script = Path(tmp) / "main.py"
                script.write_text(code, encoding="utf-8")
                argv = ["python3", str(script)]
            elif language in {"javascript", "node"}:
                script = Path(tmp) / "main.js"
                script.write_text(code, encoding="utf-8")
                node = shutil.which("node") or "node"
                argv = [node, str(script)]
            else:
                raise ValueError(f"Unsupported language: {language}")
            try:
                proc = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    cwd=tmp,
                    env=env,
                )
            except FileNotFoundError as exc:
                return RunResult("", str(exc), 127, int((time.monotonic() - start) * 1000))
        duration = int((time.monotonic() - start) * 1000)
        return RunResult(
            stdout=proc.stdout[: self.max_output_bytes],
            stderr=proc.stderr[: self.max_output_bytes],
            exit_code=proc.returncode,
            duration_ms=duration,
        )

    def run_python(self, code: str) -> RunResult:
        return self.run(code, "python")

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        if not self.deny_egress:
            return env
        # Strip credentials; full network namespace isolation is the gVisor milestone.
        for key in list(env):
            upper = key.upper()
            if any(token in upper for token in ("TOKEN", "SECRET", "PASSWORD", "API_KEY")):
                env.pop(key, None)
        env.pop("AWS_SECRET_ACCESS_KEY", None)
        env.pop("OPENAI_API_KEY", None)
        return env
