"""Python SDK client."""

import httpx


class AgentboxClient:
    def __init__(self, base_url: str = "http://localhost:8080") -> None:
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=60.0)

    def health(self) -> dict[str, str]:
        resp = self._client.get("/health")
        resp.raise_for_status()
        return resp.json()

    def run(self, code: str, language: str = "python") -> dict[str, object]:
        resp = self._client.post("/v1/run", json={"code": code, "language": language})
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
