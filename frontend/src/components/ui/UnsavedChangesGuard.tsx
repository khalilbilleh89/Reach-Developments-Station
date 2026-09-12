"use client";

import { useEffect, useRef, useState } from "react";
import type { ReactNode, RefObject } from "react";
import { ConfirmDialog } from "./ConfirmDialog";

type NavigateEvent = Event & {
  navigationType: string;
  destination: { sameDocument: boolean; key: string };
};
type NavigationSurface = EventTarget & { traverseTo: (key: string) => unknown };

/** Explicit close paths (Escape, backdrop, page Back) ask the contained draft first. */
export function requestFormLeave(root: HTMLElement | null, action: () => void) {
  const event = new CustomEvent("reach:form-leave", { cancelable: true, detail: { root, action } });
  if (document.dispatchEvent(event)) action();
}

/** For state-owned inline editors. The caller owns the saved baseline and success reset. */
export function DraftBoundary({ dirty, busy, onDiscard, children }: {
  dirty: boolean; busy?: boolean; onDiscard?: () => void; children: ReactNode;
}) {
  const root = useRef<HTMLDivElement>(null);
  return <div ref={root} data-draft-boundary><UnsavedChangesGuard dirty={dirty} busy={busy} form={root} onDiscard={onDiscard} /><fieldset disabled={busy} className="draft-fields">{children}</fieldset></div>;
}

/** Protect the ordinary record editor without making unchanged forms interrupt navigation. */
export function UnsavedChangesGuard({ dirty, busy = false, form, onDiscard }: {
  dirty: boolean; busy?: boolean; form: RefObject<HTMLElement | null>; onDiscard?: () => void;
}) {
  const [pending, setPending] = useState<(() => void) | null>(null);
  const replaying = useRef(false);
  const allowedTraversal = useRef<string | null>(null);
  useEffect(() => {
    if (!dirty && !busy) return;
    const unload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    const ask = (event: Event, action: () => void) => {
      event.preventDefault(); event.stopImmediatePropagation();
      setPending(() => action);
    };
    const click = (event: MouseEvent) => {
      if (replaying.current || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('a,[role="tab"],button[data-leaves-editor]') : null;
      if (!target || target.closest('[role="alertdialog"]')) return;
      // A nested editor's Cancel belongs to that editor, not to the draft beneath it.
      if (target.matches("button[data-leaves-editor]") && form.current?.contains(target) && target.closest("[data-draft-boundary]") !== form.current && target.closest("[data-draft-boundary]") !== null) return;
      if (!(target instanceof HTMLAnchorElement) && target.closest('[role="dialog"]') && !form.current?.contains(target) && !target.closest('[role="dialog"]')?.contains(form.current)) return;
      if (target.getAttribute("role") === "tab" && target.getAttribute("aria-selected") === "true") return;
      if (target instanceof HTMLAnchorElement && (target.target === "_blank" || target.hasAttribute("download"))) return;
      ask(event, () => target.click());
    };
    const keyboard = (event: KeyboardEvent) => {
      if (replaying.current || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
      const target = event.target instanceof Element ? event.target.closest<HTMLElement>('[role="tab"]') : null;
      if (target) ask(event, () => target.dispatchEvent(new KeyboardEvent("keydown", {key: event.key, bubbles: true, cancelable: true})));
    };
    const leave = (raw: Event) => {
      const event = raw as CustomEvent<{ root: HTMLElement | null; action: () => void }>;
      if (!replaying.current && form.current && event.detail.root?.contains(form.current)) ask(event, event.detail.action);
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
    document.addEventListener("reach:form-leave", leave);
    navigation?.addEventListener("navigate", traverse);
    return () => {
      window.removeEventListener("beforeunload", unload);
      document.removeEventListener("click", click, true);
      document.removeEventListener("keydown", keyboard, true);
      document.removeEventListener("reach:form-leave", leave);
      navigation?.removeEventListener("navigate", traverse);
    };
  }, [dirty, busy, form]);
  return pending ? <ConfirmDialog title={busy ? "Save in progress" : "Discard unsaved changes?"} body={busy ? "Wait for the save to finish before leaving. Your inputs will remain here if the request fails." : "Your edits have not been saved. Stay to continue editing, or discard them and continue."} busy={busy} cancelLabel="Stay" confirmLabel="Discard changes" onCancel={() => setPending(null)} onConfirm={() => {
    setPending(null);
    // Let the overlay remove background inertness before replaying navigation.
    requestAnimationFrame(() => {
      replaying.current = true;
      try { onDiscard?.(); pending(); } finally { replaying.current = false; }
    });
  }} /> : null;
}
