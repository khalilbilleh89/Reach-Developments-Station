"use client";

/**
 * The one modal behaviour, shared by Drawer, ConfirmDialog and PromptDialog.
 *
 * Overlays stack — a reason dialog opens inside the deal file's drawer — and
 * only the TOPMOST one owns the keyboard:
 *
 * - Escape closes the top overlay only. The first press closes the dialog, the
 *   second closes the drawer; one press never closes both.
 * - Tab and Shift+Tab stay inside the top overlay. The register behind a
 *   drawer, and the drawer behind a dialog, are not reachable by keyboard
 *   while something is open over them.
 * - Focus moves into an overlay when it opens and returns to the control that
 *   opened it when it closes, so an operator working down a register is put
 *   back exactly where they were.
 *
 * Hand-written on purpose: it exists to implement this concrete behaviour and
 * nothing else, and a dependency would bring the rest of a modal library with
 * it.
 */

import { useEffect, useRef } from "react";
import type { RefObject } from "react";

/** What can take keyboard focus, as far as this product's screens go. */
const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  '[tabindex]:not([tabindex="-1"])',
].join(", ");

/** The overlays currently open, bottom to top. The last one owns the keyboard. */
const openOverlays: HTMLElement[] = [];

function focusables(container: HTMLElement): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(FOCUSABLE)].filter(
    (element) => element.offsetParent !== null,
  );
}

/**
 * Make the referenced element a modal overlay for as long as it is mounted.
 *
 * `initialFocus` picks what receives focus on open: a selector (the reason
 * dialog focuses its input), `"container"` for the overlay itself (a drawer,
 * so its accessible name is announced), or nothing for the first focusable
 * control (a confirm dialog, whose first button is the safe one).
 */
export function useOverlay<T extends HTMLElement>(
  onClose: () => void,
  initialFocus?: "container" | string,
): RefObject<T | null> {
  const container = useRef<T>(null);
  const close = useRef(onClose);

  useEffect(() => {
    close.current = onClose;
  }, [onClose]);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    openOverlays.push(element);

    const target =
      initialFocus === "container"
        ? element
        : ((initialFocus ? element.querySelector<HTMLElement>(initialFocus) : null) ??
          focusables(element)[0] ??
          element);
    target.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      // Only the top of the stack reacts. A lower overlay sees the same event
      // and does nothing, which is exactly what makes nested Escape one-level.
      if (openOverlays[openOverlays.length - 1] !== element) return;
      if (event.key === "Escape") {
        if (event.defaultPrevented) return;
        event.preventDefault();
        close.current();
        return;
      }
      if (event.key !== "Tab") return;
      const order = focusables(element);
      if (order.length === 0) {
        event.preventDefault();
        element.focus();
        return;
      }
      const first = order[0];
      const last = order[order.length - 1];
      const active = document.activeElement;
      const inside = active instanceof HTMLElement && element.contains(active);
      if (!inside) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && (active === first || active === element)) {
        event.preventDefault();
        last.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      const index = openOverlays.indexOf(element);
      if (index >= 0) openOverlays.splice(index, 1);
      // Put the person back where they were: on the control that opened this,
      // or failing that (the control may have re-rendered away) on whatever
      // overlay is now on top.
      if (opener && opener.isConnected) {
        opener.focus();
      } else {
        openOverlays[openOverlays.length - 1]?.focus();
      }
    };
  }, [initialFocus]);

  return container;
}
