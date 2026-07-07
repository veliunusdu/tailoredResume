/**
 * Authenticated API client for TailoredResume.
 *
 * Automatically attaches the Clerk JWT Bearer token to all requests.
 * Use this instead of raw `fetch()` for any call to the FastAPI backend.
 *
 * Usage (inside a React component or server action):
 *   import { apiFetch } from "@/lib/api";
 *   const jobs = await apiFetch("/jobs");
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Fetch with automatic Clerk JWT attachment.
 * `getToken` is obtained from `useAuth()` in client components or
 * `auth()` in server components.
 */
export async function apiFetch(
  path: string,
  options: RequestInit = {},
  getToken: (() => Promise<string | null>) | null = null
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (getToken) {
    const token = await getToken();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  return fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
}

/**
 * Convenience wrapper that returns parsed JSON.
 */
export async function apiGet<T>(
  path: string,
  getToken: () => Promise<string | null>
): Promise<T> {
  const res = await apiFetch(path, { method: "GET" }, getToken);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`GET ${path} failed (${res.status}): ${err}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  getToken: () => Promise<string | null>
): Promise<T> {
  const res = await apiFetch(
    path,
    { method: "POST", body: JSON.stringify(body) },
    getToken
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`POST ${path} failed (${res.status}): ${err}`);
  }
  return res.json() as Promise<T>;
}

export async function apiPut<T>(
  path: string,
  body: unknown,
  getToken: () => Promise<string | null>
): Promise<T> {
  const res = await apiFetch(
    path,
    { method: "PUT", body: JSON.stringify(body) },
    getToken
  );
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`PUT ${path} failed (${res.status}): ${err}`);
  }
  return res.json() as Promise<T>;
}

export async function apiDelete<T>(
  path: string,
  getToken: () => Promise<string | null>
): Promise<T> {
  const res = await apiFetch(path, { method: "DELETE" }, getToken);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`DELETE ${path} failed (${res.status}): ${err}`);
  }
  return res.json() as Promise<T>;
}
