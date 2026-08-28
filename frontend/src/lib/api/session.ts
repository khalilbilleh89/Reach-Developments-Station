"use client";

/**
 * Client-side session state.
 *
 * This is a convenience for rendering, not a security boundary: the API
 * enforces every protected action regardless of what the UI believes. Nothing
 * is persisted — the session lives in an HttpOnly cookie the browser sends
 * automatically, so there is nothing to keep in localStorage.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError, auth } from "./index";
import type { CurrentUser } from "./types";

export type SessionState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: CurrentUser };

export function useSession(): {
  state: SessionState;
  refresh: () => Promise<void>;
  signOut: () => Promise<void>;
} {
  const [state, setState] = useState<SessionState>({ status: "loading" });

  const refresh = useCallback(async () => {
    try {
      const user = await auth.me();
      setState({ status: "authenticated", user });
    } catch (error) {
      if (error instanceof ApiError && error.isUnauthenticated) {
        setState({ status: "anonymous" });
        return;
      }
      throw error;
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await auth.logout();
    } finally {
      setState({ status: "anonymous" });
    }
  }, []);

  useEffect(() => {
    // Wrapped rather than called directly: the effect body must not invoke a
    // state-setting function synchronously (react-hooks/set-state-in-effect).
    void (async () => {
      await refresh();
    })();
  }, [refresh]);

  return { state, refresh, signOut };
}
