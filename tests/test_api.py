"""Tests for agentbox API."""

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
