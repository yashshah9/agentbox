"""Docker sandbox: ephemeral containers for stronger isolation than subprocess."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from agentbox.sandbox.egress import install_node_hook, install_python_hook, resolve_allowlist
from agentbox.sandbox.runner import RunResult, _likely_oom
from agentbox.sandbox.snapshots import restore_snapshot, save_snapshot

DEFAULT_PYTHON_IMAGE = "python:3.12-slim"
DEFAULT_NODE_IMAGE = "node:20-slim"


class DockerSandbox:
    """Run code in an ephemeral ``docker run --rm`` container.

    Workspace is bind-mounted at ``/work``. With ``deny_egress`` and an empty
    allowlist, networking is ``--network=none``. A non-empty allowlist uses the
    default bridge plus a userspace soft filter (see ``egress`` module).
    """

    def __init__(
        self,
        timeout_seconds: int = 30,
        max_output_bytes: int = 1_048_576,
        deny_egress: bool = True,
        snapshot_dir: str | Path | None = None,
        default_memory_mb: int | None = None,
        docker_image: str = DEFAULT_PYTHON_IMAGE,
        docker_node_image: str = DEFAULT_NODE_IMAGE,
        docker_binary: str | None = None,
        egress_allowlist: list[str] | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes
        self.deny_egress = deny_egress
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else Path("/tmp/agentbox-snapshots")
        self.default_memory_mb = default_memory_mb
        self.docker_image = docker_image
        self.docker_node_image = docker_node_image
        self.docker_binary = docker_binary or "docker"
        self.egress_allowlist = list(egress_allowlist or [])

    def run(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int | None = None,
        snapshot_id: str | None = None,
        persist_snapshot: bool = False,
        memory_mb: int | None = None,
        egress_allowlist: list[str] | None = None,
    ) -> RunResult:
        docker = self._resolve_docker()
        timeout = timeout_seconds or self.timeout_seconds
        mem = memory_mb if memory_mb is not None else self.default_memory_mb
        effective = (
            resolve_allowlist(self.egress_allowlist, egress_allowlist)
            if self.deny_egress
            else []
        )
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="agentbox-docker-") as tmp:
            workspace = Path(tmp)
            if snapshot_id:
                try:
                    restore_snapshot(snapshot_id, workspace, self.snapshot_dir)
                except FileNotFoundError as exc:
                    raise ValueError(str(exc)) from exc
            lang = language.lower()
            extra_env: dict[str, str] = {}
            if lang == "python":
                (workspace / "main.py").write_text(code, encoding="utf-8")
                image = self.docker_image
                if self.deny_egress and effective:
                    # Hook paths must be container paths (/work/...), not host paths.
                    host_env = install_python_hook(workspace, effective)
                    extra_env["PYTHONPATH"] = "/work/.agentbox_egress"
                    _ = host_env
            elif lang in {"javascript", "node"}:
                (workspace / "main.js").write_text(code, encoding="utf-8")
                image = self.docker_node_image
                if self.deny_egress and effective:
                    install_node_hook(workspace, effective)
                    extra_env["NODE_OPTIONS"] = "--require /work/.agentbox_egress_preload.js"
            else:
                raise ValueError(f"Unsupported language: {language}")

            name = f"agentbox-{uuid.uuid4().hex[:12]}"
            network_none = self.deny_egress and not effective
            argv = build_docker_argv(
                docker_binary=docker,
                workspace=workspace,
                language=lang,
                image=image,
                memory_mb=mem,
                network_none=network_none,
                container_name=name,
                extra_env=extra_env,
            )
            network_isolated = self.deny_egress
            try:
                proc = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                _force_remove_container(docker, name)
                raise
            except FileNotFoundError as exc:
                raise ValueError(
                    "Docker backend requires the docker CLI; "
                    "install Docker or set AGENTBOX_SANDBOX_BACKEND=subprocess"
                ) from exc

            new_snapshot = save_snapshot(workspace, self.snapshot_dir) if persist_snapshot else None
            stdout = proc.stdout[: self.max_output_bytes]
            stderr = proc.stderr[: self.max_output_bytes]
            exit_code = proc.returncode
        duration = int((time.monotonic() - start) * 1000)
        return RunResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            duration_ms=duration,
            snapshot_id=new_snapshot,
            oom_killed=_likely_oom(exit_code, stdout, stderr, mem),
            network_isolated=network_isolated,
            egress_allowlist=effective if self.deny_egress else [],
        )

    def run_python(self, code: str) -> RunResult:
        return self.run(code, "python")

    def _resolve_docker(self) -> str:
        binary = self.docker_binary
        path = shutil.which(binary) if not Path(binary).is_file() else binary
        if not path:
            raise ValueError(
                "Docker backend requires the docker CLI; "
                "install Docker or set AGENTBOX_SANDBOX_BACKEND=subprocess"
            )
        return path


def build_docker_argv(
    *,
    docker_binary: str,
    workspace: Path,
    language: str,
    image: str,
    memory_mb: int | None = None,
    network_none: bool = True,
    container_name: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> list[str]:
    """Build ``docker run`` argv for a language workspace (unit-testable)."""
    argv = [docker_binary, "run", "--rm"]
    if container_name:
        argv.extend(["--name", container_name])
    if network_none:
        argv.append("--network=none")
    if memory_mb is not None:
        argv.extend(["--memory", f"{max(1, memory_mb)}m"])
    for key, value in (extra_env or {}).items():
        argv.extend(["-e", f"{key}={value}"])
    argv.extend(
        [
            "-v",
            f"{workspace.resolve()}:/work",
            "-w",
            "/work",
            image,
        ]
    )
    lang = language.lower()
    if lang == "python":
        argv.extend(["python", "/work/main.py"])
    elif lang in {"javascript", "node"}:
        argv.extend(["node", "/work/main.js"])
    else:
        raise ValueError(f"Unsupported language: {language}")
    return argv


def _force_remove_container(docker: str, name: str) -> None:
    subprocess.run(
        [docker, "rm", "-f", name],
        capture_output=True,
        timeout=10,
        check=False,
    )


def docker_available(docker_binary: str = "docker") -> bool:
    return shutil.which(docker_binary) is not None
