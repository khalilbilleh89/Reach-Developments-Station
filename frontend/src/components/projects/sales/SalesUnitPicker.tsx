"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesUnitOption } from "@/lib/api";
import { Button, Field, Loading, Notice } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";

type Result = { key: string; items: SalesUnitOption[]; next_offset: number | null };

export function SalesUnitPicker({ projectId, onSelect, onCancel }: {
  projectId: string; onSelect: (unit: SalesUnitOption) => void; onCancel: () => void;
}) {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  const [completed, setCompleted] = useState<string | null>(null);
  const [failure, setFailure] = useState<{ key: string; message: string } | null>(null);
  const generation = useRef(0);
  const codeOf = useCurrencyCode();
  const queryKey = JSON.stringify([projectId, search]);
  const requestKey = JSON.stringify([queryKey, offset, retry]);
  const rows = result?.key === queryKey ? result : null;
  const error = failure?.key === requestKey ? failure.message : null;
  const loading = completed !== requestKey && !error;

  useEffect(() => {
    let active = true;
    const current = generation.current;
    const valid = () => active && generation.current === current;
    const timer = setTimeout(() => {
      void (async () => {
        try {
          let cursor = offset;
          let page;
          // Eligibility is checked by Sales after candidate pagination. Empty
          // batches are not empty inventory while the server cursor continues.
          do {
            page = await sales.unitOptions(projectId, { search, offset: String(cursor) });
            if (!valid()) return;
            if (page.items.length || page.next_offset === null) break;
            cursor = page.next_offset;
          } while (valid());
          if (!valid() || !page) return;
          setResult(previous => {
            const items = offset !== 0 && previous?.key === queryKey ? previous.items : [];
            const unique = new Map(items.map(unit => [unit.unit_id, unit]));
            page.items.forEach(unit => unique.set(unit.unit_id, unit));
            return { key: queryKey, items: [...unique.values()], next_offset: page.next_offset };
          });
          setFailure(null);
          setCompleted(requestKey);
        } catch (error) {
          if (valid()) setFailure({ key: requestKey, message: error instanceof ApiError ? error.message : "Could not load available units." });
        }
      })();
    }, offset === 0 ? 200 : 0);
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, search, offset, retry, queryKey, requestKey]);

  return <div className="stack sales-unit-picker">
    <div><h3>Choose available unit</h3><p className="subtle">Browse available inventory or search by unit, building or phase.</p></div>
    <Field label="Search unit, building or phase" optional><input className="input" type="search" value={search} placeholder="Search unit, building or phase" onChange={event => {
      if (event.target.value === search) return;
      generation.current += 1;
      setSearch(event.target.value); setOffset(0); setResult(null); setCompleted(null); setFailure(null);
    }} /></Field>
    {rows?.items.length ? <div className="sales-unit-picker-results" role="region" aria-label="Available units" aria-busy={loading}>
      <ul className="sales-unit-picker-list">{rows.items.map(unit => <li key={unit.unit_id}>
        <button type="button" className="sales-unit-picker-option" onClick={() => onSelect(unit)}>
          <span className="sales-unit-picker-details"><strong>{unit.unit_reference}</strong>
            <span>{[unit.unit_type, unit.building_name, unit.floor_name].filter(Boolean).join(" · ")}</span>
            <span className="subtle">{unit.phase_name}{unit.gross_area !== null ? ` · ${unit.gross_area} ${unit.area_unit ?? ""}` : ""}</span>
          </span>
          <span className="sales-unit-picker-price">{money(unit.reference_price_ex_tax, codeOf(unit.currency_id))}<span className="subtle">ex tax</span></span>
        </button>
      </li>)}</ul>
    </div> : null}
    {loading ? <Loading label={rows?.items.length ? "Loading more units…" : "Loading available units…"} /> : null}
    {error ? <Notice tone="error">{error} <Button onClick={() => setRetry(value => value + 1)}>Retry available units</Button></Notice> : null}
    {!loading && !error && rows?.items.length === 0 ? <Notice tone="info">
      <strong>{search.trim() ? "No matching available units" : "No units are currently available for reservation"}</strong>
      <p>{search.trim() ? "Try another unit reference, building or phase." : "Units must be released for sale and have a current approved price before they can be reserved."}</p>
    </Notice> : null}
    {rows && rows.next_offset !== null && !error ? <Button disabled={loading} onClick={() => setOffset(rows.next_offset!)}>Load more units</Button> : null}
    <Button onClick={onCancel}>Cancel</Button>
  </div>;
}
