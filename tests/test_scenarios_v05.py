"""Scenario tests for agentbox 0.5 API behavior."""

from __future__ import annotations

import inspect
import shutil
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from agentbox import __version__
from agentbox.api.app import app
from agentbox.sdk.client import AgentboxClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def test_health_version_060(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.6.0"
    assert __version__ == "0.6.0"


def test_python_success(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "print('hello agentbox')"})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello agentbox" in body["stdout"]
    assert body["exit_code"] == 0
    assert body["language"] == "python"
    assert body["oom_killed"] is False


def test_javascript_success(client: TestClient) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    resp = client.post(
        "/v1/run",
        json={"code": "console.log('hello node')", "language": "javascript"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "hello node" in body["stdout"]
    assert body["exit_code"] == 0


def test_reject_unknown_language(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "puts 1", "language": "ruby"})
    assert resp.status_code == 400
    assert "Unsupported language" in resp.json()["detail"]


def test_reject_language_rust(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "fn main() {}", "language": "rust"})
    assert resp.status_code == 400


def test_timeout_returns_408(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "import time; time.sleep(5)",
            "limits": {"timeout_seconds": 1},
        },
    )
    assert resp.status_code == 408


def test_memory_oom_killed_true(client: TestClient) -> None:
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


def test_limits_applied_present(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "print('ok')",
            "limits": {"memory_mb": 128, "timeout_seconds": 7},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limits_applied"] == {"timeout_seconds": 7, "memory_mb": 128}
    assert "ok" in body["stdout"]


def test_max_memory_clamp(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("agentbox.api.app.settings.max_memory_mb", 64)
    resp = client.post(
        "/v1/run",
        json={
            "code": "print('clamped')",
            "limits": {"memory_mb": 512, "timeout_seconds": 10},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["limits_applied"]["memory_mb"] == 64
    assert body["limits_applied"]["timeout_seconds"] == 10
    assert "clamped" in body["stdout"]


def test_snapshot_restore(client: TestClient) -> None:
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


def test_stderr_nonzero_exit(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={"code": "import sys; print('err', file=sys.stderr); sys.exit(3)"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_code"] == 3
    assert "err" in body["stderr"]


def test_stderr_exception_exit(client: TestClient) -> None:
    resp = client.post(
        "/v1/run",
        json={"code": "raise RuntimeError('boom')"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_code"] != 0
    assert "boom" in body["stderr"] or "RuntimeError" in body["stderr"]


def test_empty_code_rejected(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": ""})
    assert resp.status_code == 422


def test_syntax_error_nonzero(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "def ("})
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_code"] != 0
    assert body["stderr"] != ""


def test_sdk_client_fields_signature() -> None:
    sig = inspect.signature(AgentboxClient.run)
    for name in ("code", "language", "timeout_seconds", "snapshot", "snapshot_id", "memory_mb"):
        assert name in sig.parameters
    client = AgentboxClient(base_url="http://localhost:8080")
    assert client.base_url == "http://localhost:8080"
    assert hasattr(client, "health")
    client.close()


def test_sdk_client_run_response_fields(client: TestClient) -> None:
    """SDK documents limits_applied + oom_killed; exercise via TestClient + payload shape."""
    api = client.post(
        "/v1/run",
        json={"code": "print(42)", "limits": {"memory_mb": 64, "timeout_seconds": 10}},
    )
    assert api.status_code == 200
    body = api.json()
    assert "limits_applied" in body
    assert body["limits_applied"]["memory_mb"] == 64
    assert body["limits_applied"]["timeout_seconds"] == 10
    assert "oom_killed" in body
    assert "network_isolated" in body

    captured: dict[str, object] = {}

    class _Resp:
        status_code = 200

        @staticmethod
        def json() -> dict[str, object]:
            return body

    sdk = AgentboxClient(base_url="http://test")

    def _post(_url: str, json: dict[str, object] | None = None) -> _Resp:
        captured["payload"] = json
        return _Resp()

    sdk._client.post = _post  # type: ignore[method-assign]
    try:
        result = sdk.run("print(42)", memory_mb=64, timeout_seconds=10, snapshot=True)
        assert captured["payload"] == {
            "code": "print(42)",
            "language": "python",
            "limits": {"timeout_seconds": 10, "memory_mb": 64},
            "snapshot": True,
        }
        assert result["limits_applied"]["memory_mb"] == 64
        assert "oom_killed" in result
        assert "network_isolated" in result
    finally:
        sdk.close()


def test_node_language_alias(client: TestClient) -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed")
    resp = client.post(
        "/v1/run",
        json={"code": "console.log('via node')", "language": "node"},
    )
    assert resp.status_code == 200
    assert "via node" in resp.json()["stdout"]
