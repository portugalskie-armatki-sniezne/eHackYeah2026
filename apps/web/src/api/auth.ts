import { apiFetch } from "./client";

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

export const authApi = {
  // the login holds an email or a phone number
  async login(login: string, password: string): Promise<string> {
    const { access_token: token } = await apiFetch<{ access_token: string }>(
      "/auth/login",
      {
        method: "POST",
        body: new URLSearchParams({ username: login, password }),
        auth: false,
      },
    );
    return token;
  },

  me(signal?: AbortSignal): Promise<User> {
    return apiFetch("/auth/me", { signal });
  },

  register(body: Registration): Promise<User> {
    return apiFetch("/users", { method: "POST", json: body, auth: false });
  },
};
