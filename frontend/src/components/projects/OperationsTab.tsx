"use client";
import { useState } from "react";
import { operations } from "@/lib/api/operations";
import type { OperationSection } from "@/lib/api/operations";
import { useAnswer } from "@/lib/answer";
import { SALES_READERS, hasAnyRole } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import type { OperationBuyer } from "@/lib/api/operations";
import { Badge, Button, CountComposition, DataToolbar, DensitySwitch, Disclosure, EmptyState, FilterChips, Loading, Notice, PageHeader, ProgressRing, Segmented, SortHeader, StageBar, StatusDot, TableScroll, Tabs, TabPanel, ToolbarFilter, useSort } from "@/components/ui";
import { contextualRecordHref } from "@/components/shell/recordRoutes";
import { OperationsImport } from "./operations/OperationsImport";
import { BuyerOperations } from "./operations/BuyerOperations";
import { PipelineConfiguration } from "./operations/PipelineConfiguration";

const PURPOSE_LABEL: Record<string, string> = {golden_visa: "Golden Visa", investment_only: "Investment Only", unknown: "Not recorded"};
const STATUS_LABEL: Record<string, string> = {yes: "Yes", no: "No", unknown: "Not recorded", missing_date: "Missing completion date", na: "Not applicable", purpose_unknown: "Purpose unknown"};

/** Orders the buyers already on screen; every value compared is the server's. */
function readBuyerColumn(row: OperationBuyer, column: string): string | number | null {
  if (column === "buyer") return row.name;
  if (column === "purpose") return row.purpose ? PURPOSE_LABEL[row.purpose] : null;
  if (column === "progress") return row.applicable_count ? row.completion_percent : null;
  if (column === "next") return row.next_stage;
  return null;
}
export function OperationsTab({projectId, roles}: {projectId: string; roles: Set<string>}) {
  const [revision, setRevision] = useState(0);
  const [section, setSection] = useState<OperationSection>("property_purchase");
  const [search, setSearch] = useState("");
  const [purpose, setPurpose] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [detail, setDetail] = useState(false);
  const [configure, setConfigure] = useState(false);
  const answer = useAnswer(hasAnyRole(roles, SALES_READERS), () => operations.read(projectId), [projectId, revision]);
  const changed = async () => { setSelected(null); setConfigure(false); setImporting(false); setRevision(value => value + 1); };
  const loaded = answer.status === "ready" ? answer.data : null;
  const stages = (loaded?.stages ?? []).filter(stage => stage.is_active && stage.section === section);
  const rows = (loaded?.buyers ?? []).filter(row => {
    if (search && !`${row.name} ${row.number} ${row.purchases.map(p => p.number).join(" ")}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) return false;
    if (purpose && (row.purpose ?? "unknown") !== purpose) return false;
    if (stageFilter && statusFilter) {
      const value = row.milestones.find(item => item.stage_id === stageFilter);
      const status = value?.applicable === false ? "na" : value?.applicable === null ? "purpose_unknown" : value?.completed === true ? "yes" : value?.completed === false ? "no" : "unknown";
      if (statusFilter === "missing_date") { if (!(value?.applicable === true && value?.completed === true && !value.completed_date)) return false; }
      else if (status !== statusFilter) return false;
    }
    return true;
  });
  const { sort, toggle, sorted } = useSort(rows, readBuyerColumn);
  if (answer.status === "off") return null;
  if (answer.status === "loading") return <Loading label="Loading buyer operations" />;
  if (answer.status === "denied") return <Notice tone="info">Operations is not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice>;
  const data = answer.data;
  const buyer = data.buyers.find(row => row.id === selected);
  if (importing) return <OperationsImport projectId={projectId} onClose={() => setImporting(false)} onImported={changed} />;
  if (configure) return <PipelineConfiguration projectId={projectId} data={data} onClose={() => setConfigure(false)} onChanged={changed} />;
  if (buyer) return <BuyerOperations projectId={projectId} buyer={buyer} data={data} onClose={() => setSelected(null)} onChanged={changed} />;
  const reset = () => {setSearch(""); setPurpose(""); setStageFilter(""); setStatusFilter("");};
  const filteredStage = stages.find(stage => stage.id === stageFilter);
  const chips = [
    purpose ? {key: "purpose", label: `Purpose: ${PURPOSE_LABEL[purpose]}`, onRemove: () => setPurpose("")} : null,
    filteredStage ? {key: "stage", label: statusFilter ? `${filteredStage.label}: ${STATUS_LABEL[statusFilter]}` : `Stage: ${filteredStage.label}`, onRemove: () => {setStageFilter(""); setStatusFilter("");}} : null,
    search ? {key: "search", label: `“${search}”`, onRemove: () => setSearch("")} : null,
  ].filter((chip): chip is NonNullable<typeof chip> => chip !== null);
  return <div className="stack">
    <PageHeader title="Operations" icon="sales" subtitle="Every buyer, their purchase paperwork and Golden Visa progress." compact actions={<>{data.can_edit ? <Button variant="primary" onClick={() => setImporting(true)}>Update from Excel</Button> : null}{data.can_configure ? <Button onClick={() => setConfigure(true)}>Configure pipeline</Button> : null}</>} />
    <section className="operations-position" aria-label="Client overview">
      <div><span className="eyebrow">Connected clients</span><strong className="operations-lead">{data.buyer_count}</strong><p>One pipeline per buyer, connected to Sales.</p></div>
      <CountComposition label="Purpose of purchase" note="Includes all accessible clients, including inactive records." rows={[{label:"Golden Visa",count:data.golden_visa_count,tone:"info"},{label:"Investment Only",count:data.investment_count,tone:"neutral"},{label:"Purpose not recorded",count:data.purpose_unknown_count,tone:"warning"}]} />
    </section>
    <Tabs label="Operations sections" group="operations-sections" tabs={[{key: "property_purchase", label: "1. Property Purchase"}, {key: "golden_visa", label: "2. Golden Visa"}]} active={section} onSelect={key => {setSection(key as OperationSection); setStageFilter(""); setStatusFilter("");}} />
    <TabPanel group="operations-sections" tab={section}><section aria-label="Stage analysis" className="stack">
      <h2>Stage analysis</h2><p className="muted">All {data.buyer_count} buyers you can access, including inactive buyers. Register filters below do not change these totals.</p>
      {stages.length === 0 ? <EmptyState title="No active stages in this section" hint="Add or restore stages in Configure pipeline." /> : <div className="operations-stage-grid">{stages.map((stage, index) => {
        const summary = data.summaries.find(row => row.stage_id === stage.id)!;
        return <article className="operations-stage" key={stage.id}>
          <div className="operations-stage-heading"><span className="operations-stage-number">{index + 1}</span><h3>{stage.label}</h3></div>
          {summary.applicable ? <ProgressRing percent={summary.completion_percent} label={`${summary.yes} of ${summary.applicable} applicable clients complete`} /> : <><div className="operations-stage-total"><strong>{summary.yes}</strong><span>of {summary.applicable} applicable clients complete</span></div><p className="muted">No applicable clients</p></>}
          <div className="operations-stage-actions"><Button onClick={() => {setStageFilter(stage.id); setStatusFilter("yes");}}>{summary.yes} Yes</Button><Button onClick={() => {setStageFilter(stage.id); setStatusFilter("no");}}>{summary.no} No</Button><Button onClick={() => {setStageFilter(stage.id); setStatusFilter("unknown");}}>{summary.unrecorded} Not recorded</Button></div>
          {summary.missing_dates ? <Button onClick={() => {setStageFilter(stage.id); setStatusFilter("missing_date");}}>{summary.missing_dates} missing dates</Button> : <small className="muted">No missing completion dates</small>}
          {section === "golden_visa" ? <small className="muted">{summary.not_applicable} not applicable · {summary.purpose_unknown} purpose unknown</small> : null}
        </article>;
      })}</div>}
    </section>
    <div className="section-header"><h2>Client register</h2><Button onClick={() => setDetail(value => !value)}>{detail ? "Compact view" : "Show every stage"}</Button></div>
    <DataToolbar framed search={{value: search, onChange: setSearch, label: "Search buyers or purchases", placeholder: "Buyer, number or purchase"}} count={{shown: rows.length, total: data.buyers.length, noun: "buyer"}} onReset={chips.length ? reset : undefined} actions={<DensitySwitch />}>
      <ToolbarFilter label="Purpose of Purchase" active={purpose !== ""}><Segmented label="Purpose of Purchase" value={purpose} onChange={setPurpose} options={[{value: "", label: "All buyers"}, {value: "golden_visa", label: "Golden Visa"}, {value: "investment_only", label: "Investment Only"}, {value: "unknown", label: "Not recorded"}]} /></ToolbarFilter>
      <ToolbarFilter label="Filter by stage" active={stageFilter !== ""}><select className="input" value={stageFilter} onChange={event => setStageFilter(event.target.value)}><option value="">All stages</option>{stages.map(stage => <option key={stage.id} value={stage.id}>{stage.label}</option>)}</select></ToolbarFilter>
      <ToolbarFilter label="Stage status" active={statusFilter !== ""}><select className="input" disabled={!stageFilter} value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option>{Object.entries(STATUS_LABEL).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></ToolbarFilter>
    </DataToolbar>
    <FilterChips chips={chips} onClearAll={reset} />
    {rows.length === 0 ? <EmptyState title={data.buyer_count ? "No buyers match these filters" : "No buyers yet"} hint="Buyers registered in Sales appear here automatically." /> : <TableScroll label="Buyer operations pipeline" fixedFirst stickyHeader><thead><tr><SortHeader column="buyer" sort={sort} onToggle={toggle}>Buyer / purchases</SortHeader><SortHeader column="purpose" sort={sort} onToggle={toggle}>Purpose</SortHeader><SortHeader column="progress" sort={sort} onToggle={toggle}>Overall progress</SortHeader><SortHeader column="next" sort={sort} onToggle={toggle}>Next step</SortHeader>{detail ? stages.map(stage => <th scope="col" key={stage.id}>{stage.label}</th>) : null}</tr></thead><tbody>{sorted.map(row => <tr key={row.id}>
      <th scope="row"><Button onClick={() => setSelected(row.id)}>{row.name}</Button><div>{row.number}{!row.active ? <> · <Badge tone="muted">Inactive</Badge></> : null}</div>{row.purchases.map(purchase => <div key={purchase.id}><a href={contextualRecordHref(new URLSearchParams({project: projectId, section: "operations"}), projectId, purchase.kind, purchase.id)}>{purchase.number}</a> <StatusDot>{purchase.status.replaceAll("_", " ")}</StatusDot></div>)}</th>
      <td>{row.purpose ? PURPOSE_LABEL[row.purpose] : <span className="muted">Not recorded</span>}</td><td>{row.applicable_count ? <StageBar label="Stages complete" done={row.completed_count} total={row.applicable_count} /> : <><strong>{row.completed_count} / {row.applicable_count}</strong><span className="muted"> stages complete</span></>}</td><td>{row.next_stage ?? (row.applicable_count ? "Applicable stages complete" : "No applicable stages")}{!row.purpose ? <div className="muted">Record purchase purpose</div> : null}</td>
      {detail ? stages.map(stage => {const value = row.milestones.find(item => item.stage_id === stage.id)!; return <td key={stage.id}><Badge tone={value.applicable === true && value.completed === true ? "success" : "neutral"}>{value.applicable === false ? "Not applicable" : value.applicable === null ? "Choose purpose" : value.completed === true ? "Yes" : value.completed === false ? "No" : "Not recorded"}</Badge>{value.applicable === true ? <><div>{value.completed_date ? businessDate(value.completed_date) : value.completed ? "Date missing" : "—"}</div>{value.total_sales ? <small>Sales: {value.signed_sales} / {value.total_sales} signed</small> : null}</> : null}</td>;}) : null}
    </tr>)}</tbody></TableScroll>}
    </TabPanel><Disclosure title="How this pipeline is connected"><p>Buyer identity and purchases come from Sales. Signed SPA follows unreversed buyer-signature events for all current sales; cancelled sales are excluded from completion. Other milestones are recorded here. No signature, bank clearance or visa outcome is inferred from a document reference or commercial status. Buyer progress spans the project and requires whole-project access.</p></Disclosure>
  </div>;
}
