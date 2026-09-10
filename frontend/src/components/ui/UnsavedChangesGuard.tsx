"use client";

import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { ConfirmDialog } from "./ConfirmDialog";

type NavigateEvent = Event & {
  navigationType: string;
  destination: { sameDocument: boolean; key: string };
};
type NavigationSurface = EventTarget & { traverseTo: (key: string) => unknown };

/** Protect the ordinary record editor without making unchanged forms interrupt navigation. */
export function UnsavedChangesGuard({ dirty, form }: {
  dirty: boolean; form: RefObject<HTMLFormElement | null>;
}) {
  const [pending, setPending] = useState<(() => void) | null>(null);
  const replaying = useRef(false);
  const allowedTraversal = useRef<string | null>(null);
  useEffect(() => {
    if (!dirty) return;
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const ask = (event: Event, action: () => void) => {
      event.preventDefault(); event.stopImmediatePropagation();
      setPending(() => action);
    };
    const click = (event: MouseEvent) => {
      if (replaying.current || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('a,[role="tab"],button[data-leaves-editor]') : null;
      if (!target || form.current?.contains(target) || target.closest('[role="alertdialog"],[role="dialog"]')) return;
      if (target.getAttribute("role") === "tab" && target.getAttribute("aria-selected") === "true") return;
      if (target instanceof HTMLAnchorElement && (target.target === "_blank" || target.hasAttribute("download"))) return;
      ask(event, () => target.click());
    };
    const keyboard = (event: KeyboardEvent) => {
      if (replaying.current || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('[role="tab"]') : null;
      if (target && !form.current?.contains(target)) ask(event, () => target.dispatchEvent(new KeyboardEvent("keydown", {key: event.key, bubbles: true, cancelable: true})));
    };
    const navigation = (window as Window & { navigation?: NavigationSurface }).navigation;
    const traverse = (raw: Event) => {
      const event = raw as NavigateEvent;
      if (allowedTraversal.current === event.destination.key) {
        allowedTraversal.current = null;
        return;
      }
      if (!replaying.current && event.cancelable && event.navigationType === "traverse" && event.destination.sameDocument) {
        ask(event, () => {
          allowedTraversal.current = event.destination.key;
          navigation?.traverseTo(event.destination.key);
        });
      }
    };
    window.addEventListener("beforeunload", unload);
    document.addEventListener("click", click, true);
    document.addEventListener("keydown", keyboard, true);
    navigation?.addEventListener("navigate", traverse);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
      document.removeEventListener("keydown", keyboard, true);
      navigation?.removeEventListener("navigate", traverse);
    };
  }, [dirty, form]);
  return pending ? <ConfirmDialog title="Discard unsaved changes?" body="Your edits have not been saved. Stay to continue editing, or discard them and continue." cancelLabel="Stay" confirmLabel="Discard changes" onCancel={() => setPending(null)} onConfirm={() => {
    setPending(null);
    // Let the overlay remove background inertness before replaying navigation.
    requestAnimationFrame(() => {
      replaying.current = true;
      try { pending(); } finally { replaying.current = false; }
    });
  }} /> : null;
}
