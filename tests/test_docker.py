"""Tests for Docker sandbox backend."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentbox.api.app import create_sandbox
from agentbox.config import Settings
from agentbox.sandbox.docker import (
    DEFAULT_NODE_IMAGE,
    DEFAULT_PYTHON_IMAGE,
    DockerSandbox,
    build_docker_argv,
    docker_available,
)
from agentbox.sandbox.runner import SubprocessSandbox


def test_build_docker_argv_python_defaults(tmp_path: Path) -> None:
    argv = build_docker_argv(
        docker_binary="docker",
        workspace=tmp_path,
        language="python",
        image=DEFAULT_PYTHON_IMAGE,
    )
    assert argv[0] == "docker"
    assert argv[1:3] == ["run", "--rm"]
    assert "--network=none" in argv
    assert "-v" in argv
    vol = argv[argv.index("-v") + 1]
    assert vol.endswith(":/work")
    assert str(tmp_path.resolve()) in vol
    assert argv[argv.index("-w") + 1] == "/work"
    assert DEFAULT_PYTHON_IMAGE in argv
    assert argv[-2:] == ["python", "/work/main.py"]
    assert "--memory" not in argv
    assert "--name" not in argv


def test_build_docker_argv_javascript_with_memory_and_name(tmp_path: Path) -> None:
    argv = build_docker_argv(
        docker_binary="/usr/bin/docker",
        workspace=tmp_path,
        language="javascript",
        image=DEFAULT_NODE_IMAGE,
        memory_mb=256,
        network_none=True,
        container_name="agentbox-test",
    )
    assert argv[0] == "/usr/bin/docker"
    assert "--name" in argv
    assert argv[argv.index("--name") + 1] == "agentbox-test"
    assert "--network=none" in argv
    assert "--memory" in argv
    assert argv[argv.index("--memory") + 1] == "256m"
    assert argv[-2:] == ["node", "/work/main.js"]


def test_build_docker_argv_allows_network_when_not_deny(tmp_path: Path) -> None:
    argv = build_docker_argv(
        docker_binary="docker",
        workspace=tmp_path,
        language="python",
        image="python:3.12-slim",
        network_none=False,
    )
    assert "--network=none" not in argv


def test_build_docker_argv_extra_env(tmp_path: Path) -> None:
    argv = build_docker_argv(
        docker_binary="docker",
        workspace=tmp_path,
        language="python",
        image="python:3.12-slim",
        network_none=False,
        extra_env={"PYTHONPATH": "/work/.agentbox_egress"},
    )
    assert "--network=none" not in argv
    assert "-e" in argv
    assert "PYTHONPATH=/work/.agentbox_egress" in argv


def test_docker_sandbox_allowlist_skips_network_none(tmp_path: Path) -> None:
    box = DockerSandbox(
        snapshot_dir=tmp_path,
        timeout_seconds=10,
        egress_allowlist=["example.com"],
    )
    fake_proc = MagicMock()
    fake_proc.stdout = "ok\n"
    fake_proc.stderr = ""
    fake_proc.returncode = 0

    with (
        patch("agentbox.sandbox.docker.shutil.which", return_value="/usr/bin/docker"),
        patch("agentbox.sandbox.docker.subprocess.run", return_value=fake_proc) as run_mock,
    ):
        result = box.run("print(1)", language="python")

    assert result.network_isolated is False
    assert result.egress_allowlist == ["example.com"]
    argv = run_mock.call_args.args[0]
    assert "--network=none" not in argv
    assert any(a.startswith("PYTHONPATH=") for a in argv)


def test_build_docker_argv_rejects_unknown_language(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported language"):
        build_docker_argv(
            docker_binary="docker",
            workspace=tmp_path,
            language="ruby",
            image="python:3.12-slim",
        )


def test_docker_sandbox_missing_binary_clear_error(tmp_path: Path) -> None:
    box = DockerSandbox(snapshot_dir=tmp_path, docker_binary="docker-not-installed-xyz")
    with pytest.raises(ValueError, match="Docker backend requires the docker CLI"):
        box.run("print(1)")


def test_docker_sandbox_run_mocked(tmp_path: Path) -> None:
    box = DockerSandbox(snapshot_dir=tmp_path, timeout_seconds=10)
    fake_proc = MagicMock()
    fake_proc.stdout = "hi\n"
    fake_proc.stderr = ""
    fake_proc.returncode = 0

    with (
        patch("agentbox.sandbox.docker.shutil.which", return_value="/usr/bin/docker"),
        patch("agentbox.sandbox.docker.subprocess.run", return_value=fake_proc) as run_mock,
    ):
        result = box.run("print('hi')", language="python", memory_mb=128)

    assert result.stdout == "hi\n"
    assert result.exit_code == 0
    assert result.network_isolated is True
    assert result.oom_killed is False
    argv = run_mock.call_args.args[0]
    assert argv[0] == "/usr/bin/docker"
    assert "--network=none" in argv
    assert "--memory" in argv
    assert "128m" in argv
    assert "python" in argv
    assert "/work/main.py" in argv


def test_create_sandbox_selects_backends() -> None:
    sub = create_sandbox(Settings(sandbox_backend="subprocess"))
    assert isinstance(sub, SubprocessSandbox)
    assert sub.deny_egress is True

    unr = create_sandbox(Settings(sandbox_backend="unrestricted"))
    assert isinstance(unr, SubprocessSandbox)
    assert unr.deny_egress is False

    dock = create_sandbox(
        Settings(
            sandbox_backend="docker",
            docker_image="python:3.12-slim",
            docker_node_image="node:20-slim",
        )
    )
    assert isinstance(dock, DockerSandbox)
    assert dock.deny_egress is True
    assert dock.docker_image == "python:3.12-slim"
    assert dock.docker_node_image == "node:20-slim"


@pytest.mark.skipif(not docker_available(), reason="docker CLI not available")
def test_docker_live_python(tmp_path: Path) -> None:
    """Optional integration check when Docker is installed and daemon reachable."""
    # Probe daemon; skip if CLI exists but daemon is down.
    probe = shutil.which("docker")
    assert probe
    import subprocess

    ping = subprocess.run(
        [probe, "info"],
        capture_output=True,
        timeout=15,
        check=False,
    )
    if ping.returncode != 0:
        pytest.skip("docker daemon not reachable")

    box = DockerSandbox(snapshot_dir=tmp_path, timeout_seconds=60)
    result = box.run("print('docker-ok')", language="python")
    assert result.exit_code == 0
    assert "docker-ok" in result.stdout
    assert result.network_isolated is True
