/**
 * Minimal TypeScript client for agentbox.
 * Usage: const box = new AgentboxClient("http://localhost:8080")
 */
export type RunResult = {
  stdout: string;
  stderr: string;
  exit_code: number;
  duration_ms: number;
  language: string;
  backend: string;
};

export class AgentboxClient {
  constructor(private readonly baseUrl: string = "http://localhost:8080") {}

  async health(): Promise<{ status: string; version: string; backend: string }> {
    const res = await fetch(`${this.baseUrl}/health`);
    if (!res.ok) throw new Error(`health failed: ${res.status}`);
    return res.json();
  }

  async run(code: string, language = "python", timeoutSeconds?: number): Promise<RunResult> {
    const body: Record<string, unknown> = { code, language };
    if (timeoutSeconds) body.limits = { timeout_seconds: timeoutSeconds };
    const res = await fetch(`${this.baseUrl}/v1/run`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`run failed: ${res.status} ${await res.text()}`);
    return res.json();
  }
}
