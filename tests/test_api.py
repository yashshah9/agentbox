"""Tests for agentbox API."""

import shutil
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
    assert resp.json()["status"] == "ok"


def test_run_python(client: TestClient) -> None:
    resp = client.post("/v1/run", json={"code": "print('hello agentbox')"})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello agentbox" in body["stdout"]
    assert body["exit_code"] == 0


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
