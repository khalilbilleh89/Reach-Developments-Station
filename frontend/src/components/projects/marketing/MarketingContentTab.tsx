"use client";

import { useState } from "react";
import { marketing, type Bio, type Branding, type SavedContent } from "@/lib/api/marketing";
import { useAnswer } from "@/lib/answer";
import { hasAnyRole, MARKETING_READERS, MARKETING_WRITERS } from "@/lib/roles";
import { businessDate } from "@/lib/format";
import { Button, Card, EmptyState, KeyValue, KeyValueGrid, Loading, Notice, PageHeader, SectionHeader } from "@/components/ui";
import { DeleteRecordButton } from "../DeleteRecordButton";
import { MarketingContentEditor } from "./MarketingContentEditor";

export const NARRATIVES = [["country", "About Country"], ["area", "About Area"], ["project", "About Project"], ["location", "About Location"]] as const;

export function MarketingContentTab({ projectId, roles, kind }: { projectId: string; roles: Set<string>; kind: "bio" | "branding" }) {
  const answer = useAnswer<SavedContent<Bio | Branding>>(hasAnyRole(roles, MARKETING_READERS), () => kind === "bio" ? marketing.bio(projectId) : marketing.branding(projectId), [projectId, kind]);
  const [editing, setEditing] = useState(false);
  const canWrite = hasAnyRole(roles, MARKETING_WRITERS);
  const title = kind === "bio" ? "Project Bio" : "Branding";
  if (editing && answer.status === "ready") return <MarketingContentEditor kind={kind} initial={answer.data.data} onClose={() => setEditing(false)} onSave={async data => { await marketing.saveContent(projectId, kind, data, answer.data.version); setEditing(false); answer.retry(); }} />;
  return <div className="stack">
    <PageHeader title={title} subtitle={kind === "bio" ? "The story and setting behind this development." : "A consistent identity for every project touchpoint."} actions={canWrite && answer.status === "ready" ? <Button onClick={() => setEditing(true)}>{answer.data.version ? "Edit" : "Create"} {title.toLowerCase()}</Button> : undefined} />
    {answer.status === "loading" ? <Loading label={`Loading ${title.toLowerCase()}…`} /> : null}
    {answer.status === "denied" ? <Notice tone="info">Not available to your access level.</Notice> : null}
    {answer.status === "failed" ? <Notice tone="error">{answer.message} <Button onClick={answer.retry}>Retry</Button></Notice> : null}
    {answer.status === "ready" ? <>
      {!answer.data.version ? <Card><EmptyState title={`No ${title.toLowerCase()} recorded`} hint="Create the project content using confirmed sources. No marketing facts are prefilled." /></Card> : <>
        {kind === "bio" ? <BioView data={answer.data.data as Bio} /> : <BrandView data={answer.data.data as Branding} />}
        <Card tone="subtle"><KeyValueGrid><KeyValue label="Source" value={answer.data.data.source || "Not recorded"} /><KeyValue label="As at" value={businessDate(answer.data.data.as_of)} /></KeyValueGrid>
          {canWrite ? <DeleteRecordButton label={title.toLowerCase()} recordName={title} confirmLabel={`Delete ${title.toLowerCase()}`} description="Remove this content from Marketing. Previous revisions and the deletion reason remain in the audit history." onDelete={reason => marketing.remove(projectId, `content/${kind}`, answer.data.version, reason)} onDeleted={async () => { answer.retry(); }} /> : null}
        </Card>
      </>}
    </> : null}
  </div>;
}

function BioView({ data }: { data: Bio }) {
  return <>
    {NARRATIVES.map(([key, title]) => <Card key={key}><SectionHeader title={title} level={2} />
      <p className="marketing-prose">{data[key].paragraph || "Not entered"}</p>
      {data[key].bullets.length ? <ul className="marketing-bullets">{data[key].bullets.map((bullet, index) => <li key={index}>{bullet}</li>)}</ul> : null}
      {key === "location" && data.nearby.length ? <div className="marketing-nearby">{data.nearby.map((place, index) => <section className="marketing-place" key={index}><strong>{place.name}</strong><span>{place.duration_minutes === null ? "Time not recorded" : `${place.duration_minutes} min`} · {place.travel_mode}</span>{place.note ? <p>{place.note}</p> : null}</section>)}</div> : null}
    </Card>)}
    <Card><SectionHeader title="Project Amenities" level={2} />{data.amenities.length ? <ul className="marketing-bullets">{data.amenities.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="muted">No amenities recorded.</p>}</Card>
    <Card><SectionHeader title="Indicative Return on Investment" level={2} /><p className="marketing-return">{data.roi_min_percent === null ? "Not recorded" : `${data.roi_min_percent}% – ${data.roi_max_percent}%`}</p><p>{data.roi_basis || "Record the return period, basis and supporting source before quoting a range."}</p><p className="muted">Marketing estimate; returns are not guaranteed. Unit projections are available in Economics.</p></Card>
  </>;
}

function BrandView({ data }: { data: Branding }) {
  return <>
    <Card><SectionHeader title={data.project_name || "Project Name Definition"} level={2} /><p className="marketing-prose">{data.name_definition || "Name definition not recorded."}</p></Card>
    <Card><SectionHeader title="Colour Scheme" level={2} />{data.colors.length ? <div className="marketing-palette">{data.colors.map((color, index) => <div className="marketing-color" key={index}><span className="marketing-swatch" style={{ backgroundColor: color.hex }} aria-hidden="true" /><strong>{color.name}</strong><code>{color.hex}</code><p>{color.usage}</p></div>)}</div> : <p className="muted">No brand colours recorded.</p>}</Card>
    <Card><SectionHeader title="Font Types" level={2} />{data.fonts.length ? <KeyValueGrid>{data.fonts.map((font, index) => <KeyValue key={index} label={font.usage || "Font family"} value={font.family} />)}</KeyValueGrid> : <p className="muted">No fonts recorded.</p>}</Card>
  </>;
}
