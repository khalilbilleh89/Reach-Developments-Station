"use client";

import { useState } from "react";
import { operations } from "@/lib/api/operations";
import type { OperationSection } from "@/lib/api/operations";
import { useAnswer } from "@/lib/answer";
import { SALES_READERS, hasAnyRole } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { Badge, Button, Disclosure, EmptyState, Field, FieldRow, Loading, Notice, PageHeader, TableScroll, Tabs, TabPanel } from "@/components/ui";
import { contextualRecordHref } from "@/components/shell/recordRoutes";
import { BuyerOperations } from "./operations/BuyerOperations";
import { PipelineConfiguration } from "./operations/PipelineConfiguration";

export function OperationsTab({projectId, roles}: {projectId: string; roles: Set<string>}) {
  const [revision, setRevision] = useState(0);
  const [section, setSection] = useState<OperationSection>("property_purchase");
  const [search, setSearch] = useState("");
  const [purpose, setPurpose] = useState("");
  const [stageFilter, setStageFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [configure, setConfigure] = useState(false);
  const answer = useAnswer(hasAnyRole(roles, SALES_READERS), () => operations.read(projectId), [projectId, revision]);
  const changed = async () => { setSelected(null); setConfigure(false); setRevision(value => value + 1); };
  if (answer.status === "off") return null;
  if (answer.status === "loading") return <Loading label="Loading buyer operations" />;
  if (answer.status === "denied") return <Notice tone="info">Operations is not available to your role.</Notice>;
  if (answer.status === "failed") return <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice>;
  const data = answer.data;
  const buyer = data.buyers.find(row => row.id === selected);
  if (configure) return <PipelineConfiguration projectId={projectId} data={data} onClose={() => setConfigure(false)} onChanged={changed} />;
  if (buyer) return <BuyerOperations projectId={projectId} buyer={buyer} data={data} onClose={() => setSelected(null)} onChanged={changed} />;
  const stages = data.stages.filter(stage => stage.is_active && stage.section === section);
  const rows = data.buyers.filter(row => {
    if (search && !`${row.name} ${row.number} ${row.purchases.map(p => p.number).join(" ")}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())) return false;
    if (purpose && (row.purpose ?? "unknown") !== purpose) return false;
    if (stageFilter && statusFilter) {
      const value = row.milestones.find(item => item.stage_id === stageFilter);
      const status = value?.applicable === false ? "na" : value?.applicable === null ? "purpose_unknown" : value?.completed === true ? "yes" : value?.completed === false ? "no" : "unknown";
      if (status !== statusFilter) return false;
    }
    return true;
  });
  return <div className="stack">
    <PageHeader title="Operations" icon="sales" subtitle="Every buyer, their purchase paperwork and Golden Visa progress." compact actions={data.can_configure ? <Button onClick={() => setConfigure(true)}>Configure pipeline</Button> : undefined} />
    <div className="operations-position">
      <div><strong className="operations-lead">{data.buyer_count}</strong><span> buyers connected from Sales</span></div>
      <p>{data.golden_visa_count} Golden Visa · {data.investment_count} Investment Only · {data.purpose_unknown_count} purpose not recorded</p>
    </div>
    <Tabs label="Operations sections" group="operations-sections" tabs={[{key: "property_purchase", label: "1. Property Purchase"}, {key: "golden_visa", label: "2. Golden Visa"}]} active={section} onSelect={key => {setSection(key as OperationSection); setStageFilter(""); setStatusFilter("");}} />
    <TabPanel group="operations-sections" tab={section}><section aria-label="Stage analysis" className="stack">
      <h2>Stage analysis</h2><p className="muted">All {data.buyer_count} buyers you can access, including inactive buyers. Register filters below do not change these totals.</p>
      <TableScroll label="Stage completion analysis"><thead><tr><th scope="col">Stage</th><th scope="col">Yes / applicable</th><th scope="col">No</th><th scope="col">Not recorded</th><th scope="col">Missing dates</th>{section === "golden_visa" ? <><th scope="col">Not applicable</th><th scope="col">Purpose unknown</th></> : null}</tr></thead><tbody>{stages.map(stage => {
        const summary = data.summaries.find(row => row.stage_id === stage.id)!;
        return <tr key={stage.id}><th scope="row">{stage.label}</th><td><Button onClick={() => {setStageFilter(stage.id); setStatusFilter("yes");}}>{summary.yes} / {summary.applicable}</Button></td><td>{summary.no}</td><td>{summary.unrecorded}</td><td>{summary.missing_dates}</td>{section === "golden_visa" ? <><td>{summary.not_applicable}</td><td>{summary.purpose_unknown}</td></> : null}</tr>;
      })}</tbody></TableScroll>
    </section>
    <FieldRow><Field label="Search buyers or purchases"><input type="search" value={search} onChange={event => setSearch(event.target.value)} /></Field><Field label="Purpose of Purchase"><select value={purpose} onChange={event => setPurpose(event.target.value)}><option value="">All buyers</option><option value="investment_only">Investment Only</option><option value="golden_visa">Golden Visa</option><option value="unknown">Not recorded</option></select></Field></FieldRow>
    <FieldRow><Field label="Filter by stage"><select value={stageFilter} onChange={event => setStageFilter(event.target.value)}><option value="">All stages</option>{stages.map(stage => <option key={stage.id} value={stage.id}>{stage.label}</option>)}</select></Field><Field label="Stage status"><select disabled={!stageFilter} value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="yes">Yes</option><option value="no">No</option><option value="unknown">Not recorded</option><option value="na">Not applicable</option><option value="purpose_unknown">Purpose unknown</option></select></Field></FieldRow>
    <Button onClick={() => {setSearch(""); setPurpose(""); setStageFilter(""); setStatusFilter("");}}>Reset filters</Button>
    {rows.length === 0 ? <EmptyState title={data.buyer_count ? "No buyers match these filters" : "No buyers yet"} hint="Buyers registered in Sales appear here automatically." /> : <TableScroll label="Buyer operations pipeline" fixedFirst stickyHeader><thead><tr><th scope="col">Buyer / purchases</th><th scope="col">Purpose</th><th scope="col">Overall progress</th>{stages.map(stage => <th scope="col" key={stage.id}>{stage.label}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id}>
      <th scope="row"><Button onClick={() => setSelected(row.id)}>{row.name}</Button><div>{row.number}{!row.active ? " · Inactive" : ""}</div>{row.purchases.map(purchase => <div key={purchase.id}><a href={contextualRecordHref(new URLSearchParams({project: projectId, section: "operations"}), projectId, purchase.kind, purchase.id)}>{purchase.number}</a> · {purchase.status.replaceAll("_", " ")}</div>)}</th>
      <td>{row.purpose === "golden_visa" ? "Golden Visa" : row.purpose === "investment_only" ? "Investment Only" : "Not recorded"}</td><td>{row.completed_count} / {row.applicable_count}<div className="muted">{row.next_stage ? `Next: ${row.next_stage}` : "Applicable stages complete"}</div></td>
      {stages.map(stage => {const value = row.milestones.find(item => item.stage_id === stage.id)!; return <td key={stage.id}><Badge tone={value.applicable === true && value.completed === true ? "success" : "neutral"}>{value.applicable === false ? "Not applicable" : value.applicable === null ? "Choose purpose" : value.completed === true ? "Yes" : value.completed === false ? "No" : "Not recorded"}</Badge>{value.applicable === true ? <><div>{value.completed_date ? businessDate(value.completed_date) : value.completed ? "Date missing" : "—"}</div>{value.total_sales ? <small>Sales: {value.signed_sales} / {value.total_sales} signed</small> : null}</> : null}</td>;})}
    </tr>)}</tbody></TableScroll>}
    </TabPanel><Disclosure title="How this pipeline is connected"><p>Buyer identity and purchases come from Sales. Signed SPA follows unreversed buyer-signature events for all current sales; cancelled sales are excluded from completion. Other milestones are recorded here. No signature, bank clearance or visa outcome is inferred from a document reference or commercial status. Buyer progress spans the project and requires whole-project access.</p></Disclosure>
  </div>;
}
