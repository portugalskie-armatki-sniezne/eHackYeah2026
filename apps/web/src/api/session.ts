import { useSyncExternalStore } from "react";
import { authApi, type User } from "./auth";
import { getToken, onTokenChange, setToken } from "./client";

export type SessionState =
  | { status: "checking" }
  | { status: "signed-out" }
  | { status: "signed-in"; user: User };

let state: SessionState = getToken()
  ? { status: "checking" }
  : { status: "signed-out" };
const listeners = new Set<() => void>();

function setState(next: SessionState) {
  state = next;
  for (const listener of listeners) listener();
}

// signing out and a 401 on any request both clear the token
onTokenChange(() => {
  if (!getToken() && state.status !== "signed-out") {
    setState({ status: "signed-out" });
  }
});

// An expired or revoked token is dropped by the client; a network failure
// keeps it for the next visit.
if (state.status === "checking") {
  authApi.me().then(
    (user) => {
      if (state.status === "checking") setState({ status: "signed-in", user });
    },
    () => {
      if (state.status === "checking") setState({ status: "signed-out" });
    },
  );
}

export async function signIn(login: string, password: string) {
  setToken(await authApi.login(login, password));
  try {
    setState({ status: "signed-in", user: await authApi.me() });
  } catch (error) {
    setToken(null);
    throw error;
  }
}

export function signOut() {
  setToken(null);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * The signed-in user, restored from the stored token on load. Every component
 * that calls it shares one session.
 */
export function useSession(): SessionState {
  return useSyncExternalStore(subscribe, () => state);
}
