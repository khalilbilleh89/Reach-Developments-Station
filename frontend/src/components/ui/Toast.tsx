"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

import { Icon } from "./Icon";
import { useDialogHost } from "./DialogPortal";

type ToastTone = "success" | "error" | "info";

export interface ToastOptions {
  /** One line: what just happened. */
  title: string;
  /** A second, quieter line: the record or amount it happened to. */
  detail?: string;
  tone?: ToastTone;
  /** Shown as an Undo button; the toast stays longer while it is offered. */
  undo?: () => void | Promise<void>;
}

interface ToastRecord extends ToastOptions {
  id: number;
  leaving: boolean;
}

interface ToastApi {
  toast: (options: ToastOptions) => void;
  dismiss: (id: number) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** How long a toast stays: long enough to read, longer when it offers a way back. */
const STAY_MS = 3200;
const STAY_WITH_UNDO_MS = 6000;
const LEAVE_MS = 220;
const MAX_VISIBLE = 3;

const TONE_ICON = { success: "check", error: "alert", info: "info" } as const;

/**
 * Brief confirmation that something happened, in the corner, out of the way.
 *
 * A toast is for an outcome a person expected: "Saved", "Receipt recorded",
 * "Buyer deleted" with an Undo. It is not for a failure that blocks the next
 * step — that stays a `Notice` beside the thing that failed, where the
 * server's own reason can be read — and not for a condition that must be
 * dealt with before carrying on, which is a `Banner`. One provider sits in
 * the shell; everything inside calls `useToast().toast(...)`.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastRecord[]>([]);
  const timers = useRef(new Map<number, number>());
  const next = useRef(1);
  const host = useDialogHost();

  const dismiss = useCallback((id: number) => {
    const pending = timers.current.get(id);
    if (pending) window.clearTimeout(pending);
    timers.current.delete(id);
    setToasts((current) => current.map((entry) => (entry.id === id ? { ...entry, leaving: true } : entry)));
    window.setTimeout(() => setToasts((current) => current.filter((entry) => entry.id !== id)), LEAVE_MS);
  }, []);

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = next.current++;
      setToasts((current) => [...current.slice(-(MAX_VISIBLE - 1)), { ...options, id, leaving: false }]);
      const stay = options.undo ? STAY_WITH_UNDO_MS : STAY_MS;
      timers.current.set(id, window.setTimeout(() => dismiss(id), stay));
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((timer) => window.clearTimeout(timer));
  }, []);

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {host
        ? createPortal(
            <div className="toast-region" aria-live="polite" aria-relevant="additions">
              {toasts.map((entry) => (
                <div key={entry.id} className={entry.leaving ? "toast toast-leaving" : "toast"} role="status">
                  <span className={`toast-mark toast-mark-${entry.tone ?? "success"}`} aria-hidden="true">
                    <Icon name={TONE_ICON[entry.tone ?? "success"]} />
                  </span>
                  <span className="toast-text">
                    <span className="toast-title">{entry.title}</span>
                    {entry.detail ? <span className="toast-detail">{entry.detail}</span> : null}
                  </span>
                  {entry.undo ? (
                    <button
                      type="button"
                      className="toast-undo"
                      onClick={() => {
                        dismiss(entry.id);
                        void entry.undo?.();
                      }}
                    >
                      Undo
                    </button>
                  ) : null}
                  <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => dismiss(entry.id)}>
                    <Icon name="close" />
                  </button>
                </div>
              ))}
            </div>,
            host,
          )
        : null}
    </ToastContext.Provider>
  );
}

/**
 * The way a screen says "done". Outside a provider (a test, a detached
 * editor) it is a no-op rather than a crash, so a screen never depends on
 * the shell being present to save a record.
 */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  return api ?? NOOP;
}

const NOOP: ToastApi = { toast: () => {}, dismiss: () => {} };
