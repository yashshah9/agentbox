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

    def run(
        self,
        code: str,
        language: str = "python",
        timeout_seconds: int | None = None,
        snapshot: bool = False,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {"code": code, "language": language}
        if timeout_seconds is not None:
            payload["limits"] = {"timeout_seconds": timeout_seconds}
        if snapshot:
            payload["snapshot"] = True
        if snapshot_id:
            payload["snapshot_id"] = snapshot_id
        resp = self._client.post("/v1/run", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()
