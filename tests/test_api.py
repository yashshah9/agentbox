"""Tests for agentbox API."""

import shutil
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentbox.api.app import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["backend"] == "subprocess"


def test_run_python(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "print('hello agentbox')"})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello agentbox" in body["stdout"]
    assert body["exit_code"] == 0
    assert body["limits_applied"]["timeout_seconds"] >= 1
    assert "memory_mb" in body["limits_applied"]
    assert body["oom_killed"] is False
    assert "network_isolated" in body
    assert isinstance(body["network_isolated"], bool)
    assert body["backend"] == "subprocess"


def test_run_rejects_unknown_language(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "print(1)", "language": "ruby"})
    assert resp.status_code == 400


def test_run_timeout_limit(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "import time; time.sleep(5)",
            "limits": {"timeout_seconds": 1},
        },
    )
    assert resp.status_code == 408


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_run_javascript(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={"code": "console.log('hello node')", "language": "javascript"},
    )
    assert resp.status_code == 200
    assert "hello node" in resp.json()["stdout"]
    assert resp.json()["exit_code"] == 0


def test_snapshot_restore_keeps_workspace_file(client: TestClient) -> None:
    first = client.post(
        "/v1/run",
        json={"code": "open('memo.txt','w').write('kept')", "snapshot": True},
    )
    assert first.status_code == 200
    snapshot_id = first.json()["snapshot_id"]
    assert snapshot_id
    second = client.post(
        "/v1/run",
        json={
            "code": "print(open('memo.txt').read())",
            "snapshot_id": snapshot_id,
        },
    )
    assert second.status_code == 200
    assert "kept" in second.json()["stdout"]


def test_unknown_snapshot_returns_400(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={"code": "print(1)", "snapshot_id": "does-not-exist"},
    )
    assert resp.status_code == 400


@pytest.mark.skipif(sys.platform == "darwin", reason="RLIMIT_AS not enforceable on macOS")
def test_memory_limit_kills_huge_allocation(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "x = bytearray(200 * 1024 * 1024); print(len(x))",
            "limits": {"memory_mb": 32, "timeout_seconds": 5},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # RLIMIT_AS should prevent the allocation from succeeding.
    assert body["exit_code"] != 0 or "MemoryError" in body["stderr"] or body["stdout"] == ""
    assert "209715200" not in body.get("stdout", "")
    assert body["limits_applied"] == {"timeout_seconds": 5, "memory_mb": 32}
    assert body["oom_killed"] is True


def test_oom_killed_on_memory_error(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "raise MemoryError('simulated')",
            "limits": {"memory_mb": 64, "timeout_seconds": 5},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_code"] != 0
    assert body["oom_killed"] is True
    assert body["limits_applied"]["memory_mb"] == 64


def test_memory_clamped_to_max(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agentbox.api.app.settings.max_memory_mb", 64)
    resp = client.post(
        "/v1/run",
        json={
            "code": "print('ok')",
            "limits": {"memory_mb": 256, "timeout_seconds": 10},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limits_applied"]["memory_mb"] == 64
    assert body["limits_applied"]["timeout_seconds"] == 10
    assert "ok" in body["stdout"]
