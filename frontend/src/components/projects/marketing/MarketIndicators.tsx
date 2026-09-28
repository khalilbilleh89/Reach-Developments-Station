"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import { marketing, type Indicator, type IndicatorFields } from "@/lib/api/marketing";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, MARKETING_READERS, MARKETING_WRITERS } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { Button, Card, Disclosure, DraftBoundary, EmptyState, Field, FieldRow, FormActions, Loading, Notice, RecordPage, SectionHeader, TableScroll } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";

export const INDICATOR_GUIDE = [
  ["Policy interest rate", "Borrowing conditions and mortgage affordability."],
  ["Inflation rate", "Construction costs, household purchasing power and rent pressure."],
  ["Unemployment rate", "Local household income and rental demand."],
  ["Real GDP growth", "Economic activity and demand for property."],
  ["Population growth", "Changes in the potential resident and tenant base."],
  ["Tourist arrivals growth", "Seasonal demand for short-term accommodation."],
  ["Building permits / completions", "The pipeline of competing housing supply."],
  ["House price index change", "Observed price movement in a defined market."],
  ["Rental index change", "Observed changes in rents, distinct from advertised rents."],
  ["Residential transaction volume", "Market liquidity and buyer activity."],
] as const;
const blank: IndicatorFields = { name: "", geography: "", value: "", unit: "%", period: "", as_of: "", source: "", commentary: "" };

export function MarketIndicators({ projectId, roles }: { projectId: string; roles: Set<string> }) {
  const answer = useAnswer(hasAnyRole(roles, MARKETING_READERS), () => marketing.indicators(projectId), [projectId]);
  const [editor, setEditor] = useState<{ row?: Indicator } | null>(null);
  const canWrite = hasAnyRole(roles, MARKETING_WRITERS);
  return <Card>
    <SectionHeader level={2} title="Market Indicators" description="Dated observations for the country and area. They provide context; they do not automatically change unit prices or forecast rates." actions={canWrite ? <Button onClick={() => setEditor({})}>Add indicator</Button> : undefined} />
    {answer.status === "loading" ? <Loading label="Loading market indicators…" /> : null}
    {answer.status === "denied" ? <Notice tone="info">Market indicators are not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" ? answer.data.length ? <TableScroll label="Marketing economics"><table><caption>Market observations and their sources</caption><thead><tr><th scope="col">Indicator / geography</th><th scope="col">Value</th><th scope="col">Period / as at</th><th scope="col">Source and implications</th>{canWrite ? <th scope="col">Actions</th> : null}</tr></thead><tbody>{answer.data.map(row => <tr key={row.id}>
      <th scope="row">{row.name}<p className="muted">{row.geography}</p></th><td>{money(row.value)} {row.unit}</td><td>{row.period}<p className="muted">{businessDate(row.as_of)}</p></td><td><p>{row.source}</p><p className="muted">{row.commentary}</p></td>
      {canWrite ? <td><Button variant="default" onClick={() => setEditor({ row })}>Edit</Button><DeleteRecordButton label="indicator" recordName={`${row.name} · ${row.period}`} description="Remove this observation and retain its audit history." confirmLabel="Delete indicator" onDelete={reason => marketing.remove(projectId, `indicators/${row.id}`, row.version, reason)} onDeleted={async () => { answer.retry(); }} /></td> : null}
    </tr>)}</tbody></table></TableScroll> : <EmptyState title="No market observations yet" hint="Add sourced country and area observations. Missing rates are never prefilled as current facts." /> : null}
    <Disclosure title="Which indicators to track"><dl className="marketing-guide">{INDICATOR_GUIDE.map(([name, detail]) => <div key={name}><dt>{name}</dt><dd>{detail}</dd></div>)}</dl></Disclosure>
    {editor ? <IndicatorEditor initial={editor.row ?? blank} onClose={() => setEditor(null)} onSave={async values => { await marketing.saveIndicator(projectId, values, editor.row); setEditor(null); answer.retry(); }} /> : null}
  </Card>;
}

function IndicatorEditor({ initial, onClose, onSave }: { initial: IndicatorFields; onClose: () => void; onSave: (values: IndicatorFields) => Promise<void> }) {
  const [values, setValues] = useState<IndicatorFields>(() => Object.fromEntries(Object.keys(blank).map(key => [key, initial[key as keyof IndicatorFields]])) as IndicatorFields);
  const [original] = useState(values);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fields = [["name", "Indicator"], ["geography", "Country / area"], ["value", "Observed value"], ["unit", "Unit (%, index points, count…)"], ["period", "Observation period"], ["as_of", "As-at date"], ["source", "Source / publication reference"], ["commentary", "Implications for this project"]] as const;
  return <RecordPage title="Market observation" onClose={onClose}><DraftBoundary dirty={JSON.stringify(values) !== JSON.stringify(original)} busy={busy}>
    <form className="stack" onSubmit={async e => { e.preventDefault(); if (busy) return; setBusy(true); setError(null); try { await onSave(values); } catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not save. Your entries have been kept."); } finally { setBusy(false); } }}>
      {error ? <Notice tone="error">{error}</Notice> : null}<fieldset disabled={busy} className="marketing-fieldset"><FieldRow>{fields.map(([key, label]) => <Field key={key} label={label} optional={key === "commentary"}>
        {key === "commentary" ? <textarea maxLength={4000} value={values[key]} onChange={e => setValues({ ...values, [key]: e.target.value })} /> : <input required type={key === "as_of" ? "date" : "text"} inputMode={key === "value" ? "decimal" : undefined} list={key === "name" ? "marketing-indicator-names" : undefined} maxLength={320} value={values[key]} onChange={e => setValues({ ...values, [key]: e.target.value })} />}
      </Field>)}</FieldRow></fieldset><datalist id="marketing-indicator-names">{INDICATOR_GUIDE.map(([name]) => <option key={name} value={name} />)}</datalist>
      <FormActions><Button type="submit" disabled={busy}>{busy ? "Saving…" : "Save observation"}</Button><Button variant="default" data-leaves-editor disabled={busy} onClick={onClose}>Cancel</Button></FormActions>
    </form>
  </DraftBoundary></RecordPage>;
}
