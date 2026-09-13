"use client";
import { projects, consultantEngineering } from "@/lib/api";
import type { ConsultantWorkspace, PermitRegister } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { businessDate, todayISO } from "@/lib/format";
import { CONSULTANT_READERS, hasAnyRole } from "@/lib/roles";
import type { Roles } from "@/lib/roles";
import { Icon, Button, EmptyState, Loading, Notice } from "@/components/ui";
import { briefingDates } from "./dates";
export function ProjectMilestones({projectId,roles,refreshKey,onNavigate}: {projectId:string;roles:Roles;refreshKey:number;onNavigate:(section:"permits"|"consultant")=>void}) {
  const permits=useAnswer<PermitRegister>(true,()=>projects.permits(projectId),[projectId,refreshKey]);
  const design=useAnswer<ConsultantWorkspace>(hasAnyRole(roles,CONSULTANT_READERS),()=>consultantEngineering.workspace(projectId),[projectId,refreshKey]);
  const dates=briefingDates(permits.status==="ready"?permits.data:null,design.status==="ready"?design.data:null);
  const loading=permits.status==="loading"||design.status==="loading";
  return <section className="briefing-dates" aria-label="Dates to watch"><header><div><span className="eyebrow"><Icon name="calendar" />Development diary</span><h2>Dates to watch</h2></div><span>{loading ? "Loading dates…" : dates.length + " available dated items"}</span></header>
    <p className="footnote">Recorded targets for open permits and the active design agreement. Past dates remain visible for review.</p>
    {permits.status==="failed"?<Notice tone="error">Permit dates could not be loaded. <Button small onClick={permits.retry}>Retry permit dates</Button></Notice>:null}{design.status==="failed"?<Notice tone="error">Design dates could not be loaded. <Button small onClick={design.retry}>Retry design dates</Button></Notice>:null}
    {permits.status==="denied" || design.status==="denied" ? <p className="footnote">Some dates are unavailable to your role.</p> : null}
    {loading?<Loading label="Loading recorded dates" shape="rows"/>:null}
    {dates.length?<ol>{dates.slice(0,6).map(item=><li key={item.id}><time dateTime={item.date} data-past={item.date<todayISO()}>{businessDate(item.date)}{item.date<todayISO()?<small>Past target</small>:null}</time><div><span>{item.context}</span><h3>{item.title}</h3></div><Button small variant="quiet" aria-label={"Open " + item.title} onClick={()=>onNavigate(item.section)}>Open</Button></li>)}</ol>:!loading?<EmptyState compact title="No dated items in available records" hint="Dates appear when open permits, stages or deliverables have a recorded target."/>:null}
    {dates.length>6?<p className="footnote">First 6 of {dates.length} dated items. Open the source module for the complete programme.</p>:null}
  </section>;
}
