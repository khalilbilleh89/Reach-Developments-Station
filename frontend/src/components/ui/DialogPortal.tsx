"use client";

import { useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

const subscribe = () => () => {};
const snapshot = () => document.body;
const serverSnapshot = () => null;
export function useDialogHost() {
  return useSyncExternalStore(subscribe, snapshot, serverSnapshot);
}

/** Dialogs remain visible even when their originating register is replaced by a page. */
export function DialogPortal({ children }: { children: ReactNode }) {
  const host = useDialogHost();
  return host ? createPortal(children, host) : null;
}
