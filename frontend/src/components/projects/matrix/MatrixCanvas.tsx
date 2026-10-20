import type { MatrixFields, MatrixPoint } from "@/lib/api/matrix";
import { templates } from "./templates";

export function MatrixCanvas({ values, points = [] }: { values: MatrixFields; points?: MatrixPoint[] }) {
 const template = templates[values.framework];
 const group = (category: string, index: number) => <section key={category} className={`matrix-cell matrix-tone-${index % 6}`}>
   <div className="matrix-cell-heading"><span className="matrix-letter" aria-hidden="true">{values.framework === "pestel" || values.framework === "swot" ? category[0] : String(index + 1).padStart(2, "0")}</span><div><h3>{category}</h3><p>{template.hints[index]}</p></div></div>
   {values.items.some(item => item.category === category) ? <ul className="matrix-ideas">{values.items.filter(item => item.category === category).map((item, i) => <li key={i}><strong>{item.label}</strong>{item.notes ? <p>{item.notes}</p> : null}</li>)}</ul> : <p className="matrix-placeholder">Add your observations</p>}
 </section>;
 return <div className="matrix-canvas" aria-label={`${template.name} diagram`}>
  <header className="matrix-canvas-heading"><div><span className="eyebrow">{template.name} · {values.as_of || "Date not set"}</span><h2>{values.title || "Your next strategic perspective"}</h2></div><span className="matrix-watermark" aria-hidden="true">M</span></header>
  {values.context ? <p className="matrix-context">{values.context}</p> : null}
  {values.framework === "bcg" ? <>
   <div className="matrix-bcg" role="img" aria-label="BCG chart: market growth increases upwards; relative market share increases to the left. Exact values follow below.">
    <svg viewBox="0 0 1000 600" aria-hidden="true">
     <rect className="matrix-plot-bg" x="0" y="0" width="1000" height="600" rx="16" />
     <path className="matrix-axis" d="M500 0V600 M0 300H1000" />
     <text x="24" y="38" className="matrix-plot-label">STARS</text><text x="530" y="38" className="matrix-plot-label">QUESTION MARKS</text>
     <text x="24" y="340" className="matrix-plot-label">CASH COWS</text><text x="530" y="340" className="matrix-plot-label">DOGS</text>
     {points.map((point, i) => <g key={i}><circle className="matrix-dot" cx={point.x} cy={point.y} r="19"/><text className="matrix-dot-number" x={point.x} y={point.y + 5} textAnchor="middle">{i + 1}</text><title>{point.label}: {point.category}</title></g>)}
    </svg>
   </div>
   <p className="matrix-axis-caption">← Higher relative market share · Centre: 1× share / {values.growth_threshold_pct}% growth · Higher growth ↑</p>
   <p className="muted">Bounded axes show position around the thresholds, not a linear scale. Markers have equal size; numbers identify the items below.</p>
   {!values.items.length ? <p className="matrix-placeholder">Add products or business units to plot your portfolio.</p> : <ol className="matrix-point-legend">{values.items.map((item, i) => <li key={i}><strong>{item.label}</strong> — {item.growth_pct}% growth · {item.relative_share}× relative share{points[i] ? ` · ${points[i].category}` : " · Preview required"}{item.notes ? <p>{item.notes}</p> : null}</li>)}</ol>}
  </> : values.framework === "fishbone" ? <>
   <div className="matrix-fishbone"><div className="matrix-bones">{template.categories.map(group)}</div><div className="matrix-effect"><span className="eyebrow">Problem / effect</span><h3>{values.effect || "Define the problem"}</h3></div></div>
  </> : <>
   {values.framework === "swot" ? <p className="matrix-axis-caption">Internal: strengths & weaknesses · External: opportunities & threats</p> : null}
   {values.framework === "ansoff" ? <p className="matrix-axis-caption">Products: existing → new · Markets: existing ↓ new</p> : null}
   <div className={`matrix-grid matrix-grid-${values.framework}`}>{template.categories.map(group)}</div>
  </>}
 </div>;
}
