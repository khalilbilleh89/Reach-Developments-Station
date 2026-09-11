"use client";

import { useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesPricePreview } from "@/lib/api";
import { Button, Field, Loading, MoneyInput, Notice } from "@/components/ui";
import { useCurrencyCode } from "@/lib/currency";
import { PriceComparison } from "./PriceComparison";

export function SalesPriceInput({ projectId, unitId, versionId, reservationId, currencyId, value, onChange, onPreview, disabled }: {
  projectId: string; unitId: string; versionId: string; reservationId?: string; currencyId: string;
  value: string; onChange: (value: string) => void;
  onPreview: (preview: SalesPricePreview | null) => void; disabled?: boolean;
}) {
  const codeOf = useCurrencyCode();
  const [result, setResult] = useState<{key: string; preview: SalesPricePreview} | null>(null);
  const [failure, setFailure] = useState<{key: string; message: string} | null>(null);
  const [retry, setRetry] = useState(0);
  const key = JSON.stringify([unitId, versionId, reservationId, value, retry]);
  useEffect(() => {
    let active = true;
    onPreview(null);
    if (!value || disabled) return;
    const timer = setTimeout(() => {
      const request = reservationId
        ? sales.reservationPricePreview(projectId, reservationId, {sales_price_ex_tax: value})
        : sales.pricePreview(projectId, {unit_id: unitId, expected_price_version_id: versionId, sales_price_ex_tax: value});
      void request.then(preview => { if (active) { setResult({key, preview}); setFailure(null); onPreview(preview); } })
        .catch(error => { if (active) { setFailure({key, message: error instanceof ApiError ? error.message : "Could not preview the sales price."}); onPreview(null); } });
    }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [projectId, unitId, versionId, reservationId, value, key, onPreview, disabled]);
  const preview = result?.key === key ? result.preview : null;
  const error = failure?.key === key ? failure.message : null;
  return <div className="stack">
    <Field label="Agreed sales price · excluding tax" hint="The Inventory list price remains unchanged.">
      <MoneyInput name="sales_price_ex_tax" code={codeOf(currencyId)} value={value} onChange={onChange} disabled={disabled} />
    </Field>
    {error ? <Notice tone="error">{error} <Button disabled={disabled} onClick={() => setRetry(retry + 1)}>Retry price preview</Button></Notice>
      : preview ? <><PriceComparison facts={preview} />{preview.exception_approval_required ? <Notice tone="info">Approval required before activation. {preview.exception_reason}</Notice> : <p className="subtle">No price exception approval required for this preview.</p>}</>
      : value && !disabled ? <Loading label="Calculating price preview…" /> : null}
  </div>;
}
