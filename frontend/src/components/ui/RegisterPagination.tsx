"use client";

import { Button } from "./Button";

export function RegisterPagination({ offset, total, pageSize = 200, busy = false, onChange }: {
  offset: number; total: number; pageSize?: number; busy?: boolean; onChange: (offset: number) => void;
}) {
  return <nav aria-label="Register pages" className="form-actions">
    <Button disabled={busy || offset === 0} onClick={() => onChange(0)}>First page</Button>
    <Button disabled={busy || offset === 0} onClick={() => onChange(Math.max(0, offset - pageSize))}>Previous page</Button>
    <span aria-live="polite">{busy ? "Loading page…" : total === 0 ? "No results" : offset >= total ? `No rows on this page (${total} total)` : `${offset + 1}–${Math.min(offset + pageSize, total)} of ${total}`}</span>
    <Button disabled={busy || offset + pageSize >= total} onClick={() => onChange(offset + pageSize)}>Next page</Button>
  </nav>;
}
