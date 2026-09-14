"""Tests for deny_egress network-namespace wrapping."""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentbox.api.app import app
from agentbox.sandbox.runner import SubprocessSandbox, wrap_deny_egress


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_wrap_prefers_unshare(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(name: str) -> str | None:
        return {"unshare": "/usr/bin/unshare", "bwrap": "/usr/bin/bwrap"}.get(name)

    monkeypatch.setattr(shutil, "which", fake_which)
    monkeypatch.setattr(
        "agentbox.sandbox.runner._can_isolate", lambda cmd: cmd[0].endswith("unshare")
    )
    argv, isolated = wrap_deny_egress(["python3", "main.py"])
    assert isolated is True
    assert argv == ["/usr/bin/unshare", "--net", "--", "python3", "main.py"]


def test_wrap_falls_back_to_bwrap(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_which(name: str) -> str | None:
        return {"bwrap": "/usr/bin/bwrap"}.get(name)

    monkeypatch.setattr(shutil, "which", fake_which)
    monkeypatch.setattr("agentbox.sandbox.runner._can_isolate", lambda cmd: True)
    argv, isolated = wrap_deny_egress(["python3", "main.py"])
    assert isolated is True
    assert argv[:3] == ["/usr/bin/bwrap", "--unshare-net", "--bind"]
    assert argv[-3:] == ["--", "python3", "main.py"]


def test_wrap_skips_when_probe_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/unshare")
    monkeypatch.setattr("agentbox.sandbox.runner._can_isolate", lambda cmd: False)
    argv, isolated = wrap_deny_egress(["python3", "main.py"])
    assert isolated is False
    assert argv == ["python3", "main.py"]


def test_wrap_noop_without_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    cmd = ["python3", "main.py"]
    argv, isolated = wrap_deny_egress(cmd)
    assert isolated is False
    assert argv == cmd


def test_run_reports_network_isolated_false_without_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda name: "python3" if name == "python3" else None)
    box = SubprocessSandbox(deny_egress=True, timeout_seconds=5)
    result = box.run("print('ok')")
    assert result.exit_code == 0
    assert result.network_isolated is False
    assert "ok" in result.stdout


def test_api_includes_network_isolated(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "print(1)"})
    assert resp.status_code == 200
    body = resp.json()
    assert "network_isolated" in body
    assert isinstance(body["network_isolated"], bool)


@pytest.mark.skipif(sys.platform != "linux", reason="netns isolation is Linux-only")
@pytest.mark.skipif(
    shutil.which("unshare") is None and shutil.which("bwrap") is None,
    reason="unshare/bwrap not installed",
)
def test_live_network_isolation_blocks_egress() -> None:
    """Optional: real isolation when running on Linux with unshare/bwrap privileges."""
    from agentbox.sandbox.runner import wrap_deny_egress

    _, can = wrap_deny_egress(["true"])
    if not can:
        pytest.skip("unshare/bwrap present but cannot create netns (need privileges)")
    box = SubprocessSandbox(deny_egress=True, timeout_seconds=10)
    code = (
        "import socket\n"
        "s = socket.socket()\n"
        "try:\n"
        "    s.settimeout(2)\n"
        "    s.connect(('1.1.1.1', 80))\n"
        "    print('CONNECTED')\n"
        "except OSError as e:\n"
        "    print('BLOCKED')\n"
        "    print(type(e).__name__)\n"
        "finally:\n"
        "    s.close()\n"
    )
    result = box.run(code)
    assert result.network_isolated is True
    assert "CONNECTED" not in result.stdout
    assert "BLOCKED" in result.stdout or result.exit_code != 0
