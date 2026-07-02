/**
 * API client — calls NestJS API. Uses NEXT_PUBLIC_API_URL when set; otherwise
 * same-origin requests are proxied to the API via next.config.mjs rewrites.
 */
const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");
const TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    ...(init?.headers as Record<string, string> | undefined),
  };
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers });
  } catch {
    const hint = BASE
      ? `Could not reach API at ${BASE}. Is the API service running?`
      : "Could not reach API. Is the API service running?";
    throw new Error(hint);
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    const message =
      Array.isArray(err.details) && err.details.length
        ? err.details.join(" ")
        : err.error ?? `HTTP ${res.status}`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => apiFetch<T>(path),
  post: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    apiFetch<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => apiFetch<T>(path, { method: "DELETE" }),
};
