import "server-only";

import { getViewerId } from "./viewer";

const API_URL =
  process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly path: string,
    /** The parsed JSON error body (FastAPI's `{detail: ...}`), or null if there was none. */
    readonly body: unknown = null,
  ) {
    super(`API ${path} responded ${status}`);
  }
}

type ApiFetchOptions = RequestInit & {
  /** Send the current viewer as `X-Viewer-Id`. Defaults to true. */
  asViewer?: boolean;
};

/**
 * Server-side JSON fetch against the API. Throws `ApiError` on non-2xx.
 * Reads the viewer cookie, so callers must render inside a `<Suspense>` boundary.
 */
export async function apiFetch<T>(
  path: string,
  { asViewer = true, headers, ...init }: ApiFetchOptions = {},
): Promise<T> {
  const requestHeaders = new Headers(headers);
  if (asViewer) {
    const viewerId = await getViewerId();
    if (viewerId !== null) requestHeaders.set("X-Viewer-Id", String(viewerId));
  }
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: requestHeaders });
  if (!res.ok) throw new ApiError(res.status, path, await res.json().catch(() => null));
  return (await res.json()) as T;
}
