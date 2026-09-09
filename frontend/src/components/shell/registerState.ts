"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";

/** Small URL-owned register state. Native replaceState is integrated with Next's query hooks.
 * Read location at the time of the write so consecutive hierarchy updates compose atomically. */
export function useRegisterFields<T extends Record<string, string>>(defaults: T): [T, (changes: Partial<T>) => void] {
  const params = useSearchParams();
  const encoded = JSON.stringify(Object.fromEntries(Object.entries(defaults).map(([key, value]) => [key, params.get(key) ?? value])));
  const values = useMemo(() => JSON.parse(encoded) as T, [encoded]);
  return [values, (changes) => {
    const next = new URLSearchParams(window.location.search);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value); else next.delete(key);
    }
    window.history.replaceState(null, "", `/projects/?${next}`);
  }];
}

/** Restore the originating row after the asynchronous register has returned. */
export function useRegisterRestore(ready: boolean) {
  const params = useSearchParams();
  const address = `/projects/?${params}`;
  useEffect(() => {
    if (!ready) return;
    let saved: { href: string; y: number; tables?: { label: string | null; x: number; y: number }[] } | null = null;
    try { saved = JSON.parse(sessionStorage.getItem(`reach-register:${address}`) ?? "null"); } catch { return; }
    if (!saved) return;
    const frame = requestAnimationFrame(() => {
      const link = Array.from(document.querySelectorAll<HTMLAnchorElement>("a[data-record-link]")).find(item => item.getAttribute("href") === saved!.href);
      link?.focus({ preventScroll: true });
      for (const table of document.querySelectorAll<HTMLElement>(".table-scroll")) {
        const position = saved!.tables?.find(item => item.label === table.getAttribute("aria-label"));
        if (position) table.scrollTo({ left: position.x, top: position.y, behavior: "instant" });
      }
      window.scrollTo({ top: saved!.y, behavior: "instant" });
    });
    return () => cancelAnimationFrame(frame);
  }, [ready, address]);
}
