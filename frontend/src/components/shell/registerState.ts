"use client";
import { usePathname, useSearchParams } from "next/navigation";
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
      if (value === defaults[key]) next.delete(key); else if (value !== undefined) next.set(key, value);
    }
    window.history.replaceState(null, "", `${window.location.pathname}?${next}`);
  }];
}

export function pageOffset(value: string): number {
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= 0 ? parsed : 0;
}

export function registerAddress(pathname: string, query: string): string {
  const params = new URLSearchParams(query);
  params.sort();
  return `${pathname}?${params}`;
}

export function rememberRegisterLink(href: string) {
  const source = registerAddress(window.location.pathname, window.location.search);
  try {
    sessionStorage.setItem(`reach-register:${source}`, JSON.stringify({ href, y: window.scrollY, tables: Array.from(document.querySelectorAll<HTMLElement>(".table-scroll")).map(table => ({ label: table.getAttribute("aria-label"), x: table.scrollLeft, y: table.scrollTop })) }));
  } catch { /* URL navigation works when storage is unavailable. */ }
}

/** Restore the originating row after the asynchronous register has returned. */
export function useRegisterRestore(ready: boolean) {
  const params = useSearchParams();
  const pathname = usePathname();
  const address = registerAddress(pathname, params.toString());
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
