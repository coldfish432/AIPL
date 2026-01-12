/**
 * API 基础请求封装
 */

import { API_BASE_URL } from "@/config/settings";

const BASE_URL = API_BASE_URL || "http://127.0.0.1:18088";

// ============================================================
// Types
// ============================================================

type ApiEnvelope<T> = {
  ok?: boolean;
  data?: T;
  error?: string;
};

export interface ApiError {
  error?: string;
  code?: string;
  message?: string;
}

// ============================================================
// Error Class
// ============================================================

export class AiplError extends Error {
  code: string;
  details?: Record<string, unknown>;

  constructor(message: string, code = "UNKNOWN", details?: Record<string, unknown>) {
    super(message);
    this.name = "AiplError";
    this.code = code;
    this.details = details;
  }

  static fromApiError(err: ApiError): AiplError {
    return new AiplError(
      err.error || err.message || "API Error",
      err.code || "API_ERROR"
    );
  }
}

// ============================================================
// Request Function
// ============================================================

/**
 * 通用请求函数
 */
export async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const hasBody = Boolean(options?.body);
  const headers: HeadersInit = {
    ...(hasBody ? { "Content-Type": "application/json" } : {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });

  const body = (await res.json().catch(() => null)) as ApiEnvelope<T> | T | null;

  // HTTP 错误
  if (!res.ok) {
    if (body && typeof body === "object" && "error" in (body as ApiError)) {
      throw AiplError.fromApiError(body as ApiError);
    }
    throw new AiplError(`HTTP ${res.status}`, "HTTP_ERROR", { status: res.status });
  }

  // API 逻辑错误
  if (body && typeof body === "object" && "ok" in body && (body as ApiEnvelope<T>).ok === false) {
    const envelope = body as ApiEnvelope<T>;
    throw new AiplError(envelope.error || "Request failed", "API_ERROR");
  }

  // 解包 data 字段
  if (body && typeof body === "object" && "data" in (body as ApiEnvelope<T>)) {
    return (body as ApiEnvelope<T>).data as T;
  }

  return body as T;
}

// ============================================================
// Utilities
// ============================================================

/**
 * 解包 Engine 响应格式
 */
export function unwrapEngineEnvelope<T>(payload: T): T {
  if (payload && typeof payload === "object") {
    const obj = payload as Record<string, unknown>;

    // 解包 data 字段
    if ("data" in obj && obj.data !== undefined) {
      return obj.data as T;
    }

    // 解包 response 字段
    if ("response" in obj && typeof obj.response === "object" && obj.response !== null) {
      const resp = obj.response as Record<string, unknown>;
      if ("data" in resp && resp.data !== undefined) {
        return resp.data as T;
      }
      return resp as T;
    }
  }
  return payload;
}

/**
 * 构建查询参数
 */
export function buildQueryString(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params)
    .filter(([, v]) => v !== undefined)
    .map(([k, v]) => [k, String(v)]);

  if (entries.length === 0) return "";
  return "?" + new URLSearchParams(entries as [string, string][]).toString();
}

/**
 * 创建 EventSource 连接
 */
export function createEventSource(path: string): EventSource {
  return new EventSource(`${BASE_URL}${path}`);
}

/**
 * 获取基础 URL
 */
export function getBaseUrl(): string {
  return BASE_URL;
}