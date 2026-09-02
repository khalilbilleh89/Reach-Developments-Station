"use client";

import { useEffect, useState } from "react";

import { ApiError } from "./api";

/**
 * How one request answered a screen.
 *
 * Five answers, kept apart because they mean different things on screen: the
 * request was never made (the reader's role could not have been answered, or
 * the record has nothing to ask about), it is still loading, it answered, it
 * refused this reader, or it failed. A refusal is drawn as "not available to
 * your role" or not at all — the reader was never entitled to the figures —
 * and a failure is said in words, never rendered as a row of zeros.
 */
export type Answer<T> =
  | { status: "off" }
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "denied" }
  | { status: "failed"; message: string };

/**
 * Ask once, and only when the reader is entitled to an answer.
 *
 * `enabled` is decided from the person's roles before the request is made, so
 * a role that may not read a module never fetches it and hides it with CSS —
 * the figures never reach the browser at all. The server checks again
 * regardless, and a 403 it still returns is reported as a refusal rather than
 * as a fault.
 */
export function useAnswer<T>(enabled: boolean, load: () => Promise<T>, deps: unknown[]): Answer<T> {
  const [answer, setAnswer] = useState<Answer<T>>(enabled ? { status: "loading" } : { status: "off" });
  useEffect(() => {
    let live = true;
    void (async () => {
      if (!enabled) {
        await Promise.resolve();
        if (live) setAnswer({ status: "off" });
        return;
      }
      await Promise.resolve();
      if (live) setAnswer({ status: "loading" });
      try {
        const data = await load();
        if (live) setAnswer({ status: "ready", data });
      } catch (caught) {
        if (!live) return;
        setAnswer(toAnswer(caught));
      }
    })();
    return () => {
      live = false;
    };
    // The loader is rebuilt on every render; the deps name what actually changes it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, ...deps]);
  return answer;
}

/** The answer a caught error amounts to: a refusal, or a fault in words. */
export function toAnswer<T>(caught: unknown): Answer<T> {
  if (caught instanceof ApiError && caught.isForbidden) return { status: "denied" };
  return {
    status: "failed",
    message: caught instanceof ApiError ? caught.message : "Could not load this section.",
  };
}
