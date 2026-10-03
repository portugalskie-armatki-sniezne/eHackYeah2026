export type User = {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  role: "user" | "office" | "admin";
  google_linked: boolean;
  edited_at: string;
  created_at: string;
};

export type Registration = {
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  password: string;
};

export type Session = {
  token: string;
  user: User;
};

export class AuthApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "AuthApiError";
  }
}

function errorMessage(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const detail = body.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail.flatMap((item: unknown) =>
        item && typeof item === "object" && "msg" in item
          ? [String(item.msg)]
          : [],
      );
      if (messages.length) return messages.join("; ");
    }
  }
  return `Authentication request failed (${status}).`;
}

export function createAuthApi(baseUrl: string) {
  const base = baseUrl.replace(/\/+$/, "");

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const response = await fetch(`${base}${path}`, options);
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new AuthApiError(
        response.status,
        errorMessage(body, response.status),
      );
    }
    return response.json() as Promise<T>;
  }

  return {
    // the login holds an email or a phone number
    async login(login: string, password: string): Promise<string> {
      const { access_token: token } = await request<{ access_token: string }>(
        "/auth/login",
        {
          method: "POST",
          body: new URLSearchParams({ username: login, password }),
        },
      );
      return token;
    },

    me(token: string, signal?: AbortSignal): Promise<User> {
      return request("/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
        signal,
      });
    },

    register(body: Registration): Promise<User> {
      return request("/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    },
  };
}

export const authApi = createAuthApi("/api");

const TOKEN_KEY = "ehackyeah.token";

export function loadToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // storage can be blocked; the session then lasts until the page reloads
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // nothing was stored
  }
}

export async function signIn(login: string, password: string) {
  const token = await authApi.login(login, password);
  return { token, user: await authApi.me(token) } satisfies Session;
}
