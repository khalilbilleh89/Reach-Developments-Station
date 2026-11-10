"use client";
import { useId, useState } from "react";
import type { ProcedureFields, ProcedureStep } from "@/lib/api/procedure";
import { Button, Notice } from "@/components/ui";
export const paths = (step: ProcedureStep): [string, string | null][] => step.kind === "decision" ? [["Yes", step.yes_id], ["No", step.no_id]] : step.kind === "end" ? [] : [["Next", step.next_id]];
export function ProcedureMap({ values }: { values: ProcedureFields }) {
 const [expanded, setExpanded] = useState(false);
 const marker = useId().replaceAll(":", "");
 const [active, setActive] = useState<string | null>(null);
 const current = values.steps.find(s => s.id === active);
 const height = Math.max(240, values.steps.length * 190 + 30);
 return <div className="stack">
  <div className="procedure-map-heading"><div><span className="eyebrow">PROCEDURE MAP</span><h2>{values.title || "Untitled procedure"}</h2><p>{values.objective}</p></div><Button variant="default" onClick={() => setActive(values.steps.find(s => s.kind === "start")?.id ?? null)}>Walk through</Button></div>
  <Button variant="quiet" onClick={() => setExpanded(v => !v)}>{expanded ? "Fit map to screen" : "Expand map for detail"}</Button>
  <div className="procedure-map-scroll" tabIndex={0} aria-label="Workflow diagram; scroll to explore">
   <svg className={expanded ? "procedure-map procedure-map-expanded" : "procedure-map"} viewBox={`0 0 1000 ${height}`} width="1000" height={height} role="img" aria-label={`Workflow for ${values.title || "procedure"}. Labelled paths are also listed below.`}>
    <defs><marker id={marker} markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" className="procedure-arrow"/></marker></defs>
    {values.steps.flatMap((s, i) => paths(s).map(([label,target], branch) => { const j=values.steps.findIndex(t=>t.id===target); if(j<0)return null; const y=i*190+100, ty=j*190+70, lane=branch===1?880:100+(i%4)*25;return <g key={s.id+label} className={label==="No"?"procedure-edge-no":"procedure-edge-yes"}><path d={`M${branch===1?760:240} ${y} H${lane} V${ty} H${branch===1?760:240}`} markerEnd={`url(#${marker})`}/><text x={branch===1?800:180} y={y-8}>{label}</text></g>; }))}
    {values.steps.map((s,i)=><g key={s.id} className={`procedure-node procedure-node-${s.kind}`} transform={`translate(240,${i*190+30})`}>
     {s.kind==="decision"?<path d="M35 0H485L520 65L485 130H35L0 65Z"/>:<rect width="520" height="130" rx={s.kind==="start"||s.kind==="end"?48:14}/>}
     <text x="260" y="30" textAnchor="middle" className="procedure-node-kind">{i+1} · {s.kind.toUpperCase()}</text>
     <foreignObject x="42" y="42" width="436" height="76"><div className="procedure-node-label" title={s.title}>{s.title || "Name this step"}<small>{s.owner}</small></div></foreignObject>
    </g>)}
   </svg>
  </div>
  {current ? <section className="procedure-walk" aria-live="polite"><span className="eyebrow">WALKTHROUGH · {current.kind}</span><h3>{current.title}</h3><p>{current.description}</p><p><strong>Input:</strong> {current.inputs || "Not specified"}</p><p><strong>Output:</strong> {current.outputs || "Not specified"}</p><div className="button-row">{paths(current).map(([label,target])=><Button key={label} disabled={!values.steps.some(s=>s.id===target)} onClick={()=>setActive(target)}>{label} → {values.steps.find(s=>s.id===target)?.title || "Choose destination"}</Button>)}<Button variant="quiet" onClick={()=>setActive(null)}>Close walkthrough</Button></div>{current.kind==="end"?<Notice tone="info">End of this path.</Notice>:null}</section>:null}
  <section aria-label="Workflow details" className="procedure-detail-grid">{values.steps.map((s,i)=><article key={s.id} className="procedure-detail"><span className="eyebrow">{i+1} · {s.kind}</span><h3>{s.title}</h3><p>{s.description}</p><dl><dt>Responsible</dt><dd>{s.owner || "Not specified"}</dd><dt>Input</dt><dd>{s.inputs || "Not specified"}</dd><dt>Output</dt><dd>{s.outputs || "Not specified"}</dd></dl>{paths(s).map(([label,target])=><p key={label}><strong>{label} → </strong>{values.steps.find(t=>t.id===target)?.title || "Missing destination"}</p>)}</article>)}</section>
 </div>;
}
