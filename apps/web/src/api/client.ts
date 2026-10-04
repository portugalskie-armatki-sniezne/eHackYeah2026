// Vite inlines the address at build time; without one, requests go to /api,
// which the development server proxies to the local API
const API_URL = (
  (import.meta.env.VITE_API_URL as string | undefined) || "/api"
).replace(/\/+$/, "");

const TOKEN_KEY = "ehackyeah.token";

function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

let token = loadToken();
const tokenListeners = new Set<() => void>();

export function getToken(): string | null {
  return token;
}

export function setToken(next: string | null) {
  token = next;
  try {
    if (next) localStorage.setItem(TOKEN_KEY, next);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    // storage can be blocked; the session then lasts until the page reloads
  }
  for (const listener of tokenListeners) listener();
}

export function onTokenChange(listener: () => void) {
  tokenListeners.add(listener);
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item: unknown) => {
        if (!item || typeof item !== "object" || !("msg" in item)) return [];
        if (typeof item.msg !== "string") return [];
        const field =
          "loc" in item && Array.isArray(item.loc)
            ? item.loc.slice(1).join(".")
            : "";
        return [field ? `${field}: ${item.msg}` : item.msg];
      });
      if (messages.length) return messages.join("; ");
    }
  }
  return `Request failed (${status}).`;
}

type RequestOptions = {
  method?: string;
  /** sent as JSON */
  json?: unknown;
  /** sent as is, for forms and files */
  body?: BodyInit;
  query?: Record<string, string | number | undefined>;
  /**
   * False leaves the token out, for sign-in requests: their 401 means wrong
   * credentials, not an expired session.
   */
  auth?: boolean;
  responseType?: "json" | "blob";
  signal?: AbortSignal;
};

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

/** The only place that calls the API: every request and error goes through it. */
export async function apiFetch<T>(
  path: string,
  {
    method,
    json,
    body,
    query,
    auth = true,
    responseType = "json",
    signal,
  }: RequestOptions = {},
): Promise<T> {
  const headers = new Headers();
  const sentToken = auth ? token : null;
  if (sentToken) headers.set("Authorization", `Bearer ${sentToken}`);
  if (json !== undefined) headers.set("Content-Type", "application/json");
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) search.set(key, String(value));
  }
  const queryString = search.toString();

  const response = await fetch(
    apiUrl(path) + (queryString ? `?${queryString}` : ""),
    {
      method,
      headers,
      body: json !== undefined ? JSON.stringify(json) : body,
      signal,
    },
  );
  if (!response.ok) {
    // the token expired or its user is gone; a newer sign-in is left alone
    if (response.status === 401 && sentToken && sentToken === token) {
      setToken(null);
    }
    const errorBody: unknown = await response.json().catch(() => null);
    throw new ApiError(
      response.status,
      errorMessage(errorBody, response.status),
    );
  }
  if (response.status === 204) return undefined as T;
  if (responseType === "blob") return response.blob() as Promise<T>;
  return response.json() as Promise<T>;
}
