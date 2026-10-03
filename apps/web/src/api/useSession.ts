import { useCallback, useEffect, useState } from "react";
import {
  AuthApiError,
  authApi,
  clearToken,
  loadToken,
  saveToken,
  type Session,
} from "./auth";

export type SessionState =
  | { status: "checking" }
  | { status: "signed-out" }
  | { status: "signed-in"; session: Session };

/**
 * The signed-in user, restored from the stored token on load. An expired or
 * revoked token is dropped; a network failure keeps it for the next visit.
 */
export function useSession() {
  const [state, setState] = useState<SessionState>(() =>
    loadToken() ? { status: "checking" } : { status: "signed-out" },
  );

  useEffect(() => {
    const token = loadToken();
    if (!token) return;
    const controller = new AbortController();
    authApi
      .me(token, controller.signal)
      .then((user) =>
        setState({ status: "signed-in", session: { token, user } }),
      )
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (error instanceof AuthApiError && error.status === 401) clearToken();
        setState({ status: "signed-out" });
      });
    return () => controller.abort();
  }, []);

  const signIn = useCallback((session: Session) => {
    saveToken(session.token);
    setState({ status: "signed-in", session });
  }, []);

  const signOut = useCallback(() => {
    clearToken();
    setState({ status: "signed-out" });
  }, []);

  return { state, signIn, signOut };
}
