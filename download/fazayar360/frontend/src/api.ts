/** کلاینت API با مدیریت خطای ساختاریافته، شناسه رهگیری و Idempotency-Key */

export type ApiError = { code: string; message: string; details?: any[] };
export class HttpError extends Error {
  code: string;
  details: any[];
  status: number;
  requestId?: string;
  constructor(status: number, err: ApiError, requestId?: string) {
    super(err.message);
    this.code = err.code;
    this.details = err.details || [];
    this.status = status;
    this.requestId = requestId;
  }
}

const BASE = "/api/v1";

export function token(): string | null {
  return localStorage.getItem("fazayar.token");
}

export function setToken(t: string | null) {
  if (t) localStorage.setItem("fazayar.token", t);
  else localStorage.removeItem("fazayar.token");
}

async function request<T>(method: string, path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) headers["Authorization"] = `Bearer ${t}`;
  if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;
  const res = await fetch(BASE + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data && (data as any).error) as ApiError | undefined;
    throw new HttpError(res.status, err || { code: "UNKNOWN", message: "خطای نامشخص" }, (data as any)?.request_id);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown, idempotencyKey?: string) =>
    request<T>("POST", path, body, idempotencyKey),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
};
