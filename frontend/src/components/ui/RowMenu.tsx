"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Icon } from "./Icon";

/**
 * A row's secondary actions behind one control, so a register reads as data
 * rather than as a wall of buttons. A disclosure, not an ARIA menu: the items
 * are ordinary buttons in tab order. The list stays mounted while hidden, so an
 * action that opens a dialog keeps that dialog after the list closes.
 */
export function RowMenu({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  // Fixed to the trigger, so a register's horizontal scroll box cannot clip the list.
  const [place, setPlace] = useState<{ top: number; right: number } | null>(null);
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    root.current?.querySelector<HTMLElement>(".row-menu-list button")?.focus();
    const outside = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { setOpen(false); trigger.current?.focus(); } };
    const away = () => setOpen(false);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    window.addEventListener("scroll", away, true);
    window.addEventListener("resize", away);
    return () => {
      document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape);
      window.removeEventListener("scroll", away, true); window.removeEventListener("resize", away);
    };
  }, [open]);
  return <div className="row-menu" ref={root}>
    <button ref={trigger} type="button" className="row-menu-trigger" aria-label={label} aria-expanded={open} aria-controls={id} onClick={() => {
      const box = trigger.current?.getBoundingClientRect();
      if (box) setPlace({ top: box.bottom + 4, right: window.innerWidth - box.right });
      setOpen(value => !value);
    }}><Icon name="more" /></button>
    <div className="row-menu-list" id={id} hidden={!open} style={place ?? undefined} onClick={() => setOpen(false)}>{children}</div>
  </div>;
}
