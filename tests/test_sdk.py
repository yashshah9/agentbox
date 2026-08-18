"""Tests for SDK client."""

from agentbox.sdk.client import AgentboxClient


def test_client_instantiation() -> None:
    client = AgentboxClient(base_url="http://localhost:8080")
    assert client.base_url == "http://localhost:8080"
    client.close()
