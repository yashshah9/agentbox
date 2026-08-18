"""Tests for agentbox API."""

import shutil

import pytest
from fastapi.testclient import TestClient

from agentbox.api.app import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_run_python() -> None:
    resp = client.post("/v1/run", json={"code": "print('hello agentbox')"})
    assert resp.status_code == 200
    body = resp.json()
    assert "hello agentbox" in body["stdout"]
    assert body["exit_code"] == 0


def test_run_rejects_unknown_language() -> None:
    resp = client.post("/v1/run", json={"code": "print(1)", "language": "ruby"})
    assert resp.status_code == 400


def test_run_timeout_limit() -> None:
    resp = client.post(
        "/v1/run",
        json={
            "code": "import time; time.sleep(5)",
            "limits": {"timeout_seconds": 1},
        },
    )
    assert resp.status_code == 408


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_run_javascript() -> None:
    resp = client.post(
        "/v1/run",
        json={"code": "console.log('hello node')", "language": "javascript"},
    )
    assert resp.status_code == 200
    assert "hello node" in resp.json()["stdout"]
    assert resp.json()["exit_code"] == 0
