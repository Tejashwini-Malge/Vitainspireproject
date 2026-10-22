// Session token handling. The token is kept in sessionStorage (per-tab, cleared when the tab closes).
// This is a foundation-slice choice; production needs HttpOnly cookies. See ADR-0002 in docs/decisions.

const TOKEN_KEY = "vita.access_token";

// The nav (and anything else outside the component that called setToken/clearToken) needs to
// know sign-in state changed. sessionStorage's own "storage" event only fires in *other* tabs,
// so same-tab listeners need this instead.
const AUTH_CHANGED_EVENT = "vita:auth-changed";

export function onAuthChanged(listener: () => void): () => void {
  window.addEventListener(AUTH_CHANGED_EVENT, listener);
  return () => window.removeEventListener(AUTH_CHANGED_EVENT, listener);
}

function notifyAuthChanged(): void {
  window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

// Requests go to the same origin and are forwarded to the backend by the Next rewrite in
// next.config.mjs. Calling the backend origin directly would make every authorized request
// cross-origin and need a CORS preflight the API does not answer.
const API_PREFIX = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    /** Reasons a conflicting action was refused (for example, why a profile cannot be published yet). */
    public blockers: string[] = [],
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    // Storage can be blocked (private mode, strict settings). The caller then sees "signed out".
    return null;
  }
}

export function setToken(token: string): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    throw new Error("This browser is blocking session storage, so sign-in cannot be kept. Enable site storage and try again.");
  }
  notifyAuthChanged();
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Nothing to clear if storage is unavailable.
  }
  notifyAuthChanged();
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  // FormData sets its own multipart boundary; forcing JSON here would break uploads.
  const isForm = init.body instanceof FormData;
  if (init.body !== undefined && !isForm && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_PREFIX}${path}`, { ...init, headers });
  if (res.status === 204) return undefined as T;

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw toApiError(res.status, body);
  }
  return body as T;
}

function toApiError(status: number, body: unknown): ApiError {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return new ApiError(status, detail);
  // Validation errors arrive as a list of objects. Each one names the field it came from in `loc`;
  // without it the reader only sees "String should have at least 10 characters" and has to guess
  // which input is wrong. Every failing field is listed, since a form usually has more than one.
  // Checked before the generic-object branch below, since arrays are also objects.
  if (Array.isArray(detail) && detail.length > 0) {
    const messages = detail
      .map((e) => fieldMessage(e as { loc?: unknown; msg?: unknown }))
      .filter((m): m is string => m !== null);
    if (messages.length > 0) return new ApiError(status, messages.join("; "));
  }
  if (detail && typeof detail === "object") {
    const d = detail as { message?: unknown; blockers?: unknown };
    const message = typeof d.message === "string" ? d.message : `Request failed (${status})`;
    const blockers = Array.isArray(d.blockers) ? d.blockers.filter((b): b is string => typeof b === "string") : [];
    return new ApiError(status, message, blockers);
  }
  return new ApiError(status, `Request failed (${status})`);
}

/** "Description: String should have at least 10 characters" from one FastAPI validation entry. */
function fieldMessage(entry: { loc?: unknown; msg?: unknown }): string | null {
  if (typeof entry.msg !== "string") return null;
  // loc is a path like ["body", "description"] or ["body", "ngo_ids", 0]. The leading "body"
  // (or "query"/"path") says where the value came from, which the reader does not need.
  const path = Array.isArray(entry.loc) ? entry.loc.slice(1).filter((p): p is string => typeof p === "string") : [];
  const field = path[path.length - 1];
  if (!field) return entry.msg;
  const label = field.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
  return `${label}: ${entry.msg}`;
}

/** Fetch an authorized file and save it. The token is sent in a header, never in the URL. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_PREFIX}${path}`, { headers });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw toApiError(res.status, body);
  }
  const blob = await res.blob();
  const name = filenameFrom(res.headers.get("content-disposition")) ?? fallbackName;
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    // Release the object URL after the browser has had a chance to start the save.
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

function filenameFrom(disposition: string | null): string | null {
  if (!disposition) return null;
  const match = /filename\*=UTF-8''([^;]+)/i.exec(disposition);
  return match ? decodeURIComponent(match[1]) : null;
}
