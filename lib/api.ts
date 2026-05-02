/**
 * Centralised fetch helper for the Next.js → FastAPI secure proxy.
 *
 * All browser-side API calls go through /api/backend/[...path] which:
 *   1. Validates the Auth.js session server-side
 *   2. Injects X-Org-ID and X-User-ID headers from the JWT
 *   3. Forwards the request to FastAPI
 *
 * Usage:
 *   import { apiFetch } from "@/lib/api"
 *   const data = await apiFetch("/analytics/dashboard")
 */

const PROXY_BASE = "/api/backend";

export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit
): Promise<T> {
  // Strip leading slash and /api/v1 prefix if accidentally included
  const cleanPath = path.replace(/^\/?(api\/v1\/)?/, "");
  const url = `${PROXY_BASE}/${cleanPath}`;

  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }

  return res.json() as Promise<T>;
}
