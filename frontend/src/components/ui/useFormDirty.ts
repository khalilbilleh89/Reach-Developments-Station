"use client";
import { useEffect, useState } from "react";
import type { RefObject } from "react";

function snapshot(form: HTMLFormElement) {
  return JSON.stringify(Array.from(form.elements).flatMap(element => {
    if (element instanceof HTMLInputElement) {
      if (["submit", "button", "search", "hidden"].includes(element.type)) return [];
      return [[element.type, element.value, element.checked]];
    }
    if (element instanceof HTMLSelectElement || element instanceof HTMLTextAreaElement) return [[element.type, element.value]];
    return [];
  }));
}

/** Modal inputs live only in memory. A failed submit never resets their baseline. */
export function useFormDirty(ref: RefObject<HTMLFormElement | null>) {
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    const form = ref.current;
    if (!form) return;
    let baseline = snapshot(form), edited = false;
    const update = () => { edited = true; setDirty(snapshot(form) !== baseline); };
    // Options may arrive after the modal opens; initial hydration is not an edit.
    const observer = new MutationObserver(() => { if (!edited) baseline = snapshot(form); });
    observer.observe(form, { childList: true, subtree: true });
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    return () => { observer.disconnect(); form.removeEventListener("input", update); form.removeEventListener("change", update); };
  }, [ref]);
  return dirty;
}
