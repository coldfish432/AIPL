import { getBaseUrl } from "./config";

export class ApiClient {
  constructor(private readonly baseUrl: string = getBaseUrl()) {}

  async getJson<T>(path: string): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`);
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json() as Promise<T>;
  }

  async postJson<T>(path: string, body: unknown): Promise<T> {
    const resp = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      throw new Error(`HTTP ${resp.status}`);
    }
    return resp.json() as Promise<T>;
  }
}
