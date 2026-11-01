"use client";
import { useState } from "react";
import type { CSSProperties, ReactNode } from "react";
import type { MatrixFields, MatrixItem, MatrixPoint } from "@/lib/api/matrix";
import { templates } from "./templates";

/**
 * A saved analysis drawn in the shape of its framework (owner-chosen designs,
 * Nov 2026): SWOT as a balance ledger, PESTEL as a six-lens wheel, Porter as a
 * pressure field, BCG as a decision board, Ansoff as a risk staircase and
 * Fishbone as a cause funnel.
 *
 * Every word comes from the analysis — its items, notes, categories and, for
 * BCG, the quadrant and position the server computed from growth and share.
 * Nothing is scored or derived here. One focus and one open item are held for
 * the whole canvas, so each design is a plain render of the same state.
 */
type Focus = { focus: string | null; open: string | null; setFocus: (key: string | null) => void; setOpen: (key: string | null) => void };

export function MatrixCanvas({ values, points = [] }: { values: MatrixFields; points?: MatrixPoint[] }) {
 const [focus, setFocus] = useState<string | null>(null);
 const [open, setOpen] = useState<string | null>(null);
 const state: Focus = { focus, open, setFocus, setOpen };
 const template = templates[values.framework];
 const body = values.framework === "swot" ? swotLedger(values, state)
  : values.framework === "pestel" ? pestelWheel(values, state)
  : values.framework === "porter" ? porterField(values, state)
  : values.framework === "bcg" ? bcgBoard(values, points, state)
  : values.framework === "ansoff" ? ansoffStairs(values, state)
  : fishboneFunnel(values, state);
 return <div className={`matrix-canvas matrix-canvas-${values.framework}`} aria-label={`${template.name} diagram`}>
  <header className="matrix-canvas-heading">
   <span className="eyebrow">{template.name} · As at {values.as_of || "date not set"}</span>
   <h2>{values.title || "Your next strategic perspective"}</h2>
   {values.context ? <p className="matrix-context">{values.context}</p> : null}
  </header>
  {body}
 </div>;
}

const of = (values: MatrixFields, category: string) => values.items.filter(item => item.category === category);
const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;
const empty = <p className="matrix-placeholder">No observations yet</p>;
const toggle = (state: Focus, key: string) => () => state.setOpen(state.open === key ? null : key);
const pick = (state: Focus, key: string) => () => state.setFocus(state.focus === key ? null : key);

/** An entry that opens its note in place. */
function entry(state: Focus, key: string, item: MatrixItem, ref?: string): ReactNode {
 const isOpen = state.open === key;
 return <button key={key} type="button" className={isOpen ? "matrix-entry matrix-entry-open" : "matrix-entry"} aria-expanded={isOpen} onClick={toggle(state, key)}>
  {ref ? <span className="matrix-entry-ref">{ref}</span> : null}
  <span className="matrix-entry-text"><strong>{item.label}</strong>{isOpen && item.notes ? <span className="matrix-entry-note">{item.notes}</span> : null}{isOpen && !item.notes ? <span className="matrix-entry-note">No note recorded.</span> : null}</span>
 </button>;
}

// SWOT — what works for the project on the left, what works against it on the
// right; the project's own doing above the line, the market's below.
function swotLedger(values: MatrixFields, state: Focus): ReactNode {
 const side = (title: string, tone: string, groups: [string, string, string][]) => <div className={`matrix-ledger-side matrix-ledger-${tone}`}>
  <p className="matrix-ledger-title">{title}</p>
  {groups.map(([category, letter, scope]) => {
   const items = of(values, category);
   const dim = state.focus !== null && state.focus !== category;
   return <section key={category} className={dim ? "matrix-ledger-group matrix-dim" : "matrix-ledger-group"}>
    <button type="button" className="matrix-ledger-head" aria-pressed={state.focus === category} onClick={pick(state, category)}>
     <span className={`matrix-chip matrix-chip-${letter.toLowerCase()}`}>{letter}</span>{category}<span className="matrix-ledger-scope">{scope}</span>
    </button>
    {items.length ? items.map((item, i) => entry(state, `${category}-${i}`, item, `${letter}${i + 1}`)) : empty}
   </section>;
  })}
 </div>;
 return <div className="matrix-ledger">
  {side("Works for us", "for", [["Strengths", "S", "Internal"], ["Opportunities", "O", "External"]])}
  <div className="matrix-ledger-spine" aria-hidden="true"><span>Internal<br />—<br />External</span></div>
  {side("Works against us", "against", [["Weaknesses", "W", "Internal"], ["Threats", "T", "External"]])}
 </div>;
}

// PESTEL — six lenses round the project; one is read at a time.
function pestelWheel(values: MatrixFields, state: Focus): ReactNode {
 const lenses = templates.pestel.categories;
 const current = state.focus && lenses.includes(state.focus) ? state.focus : lenses[0];
 const index = lenses.indexOf(current);
 const step = (by: number) => () => { state.setFocus(lenses[(index + by + lenses.length) % lenses.length]); state.setOpen(null); };
 const items = of(values, current);
 return <div className="matrix-wheel-layout">
  <div className="matrix-wheel" style={{ "--matrix-turn": `${index * 60}deg` } as CSSProperties}>
   <span className="matrix-wheel-arc" aria-hidden="true" />
   <div className="matrix-wheel-hub"><span>The project</span><strong>{count(values.items.length, "observation")}</strong></div>
   {lenses.map((lens, i) => <button key={lens} type="button" className={`matrix-lens matrix-lens-${i}`} aria-pressed={lens === current} onClick={() => { state.setFocus(lens); state.setOpen(null); }}>
    <span className="matrix-lens-letter">{lens[0]}</span><span className="matrix-lens-text"><strong>{lens}</strong><span>{count(of(values, lens).length, "observation")}</span></span>
   </button>)}
  </div>
  <aside className="matrix-wheel-panel" aria-live="polite">
   <div className="matrix-wheel-panel-head"><span className="matrix-chip matrix-chip-s">{current[0]}</span><div><span className="eyebrow">Lens</span><h3>{current}</h3></div></div>
   <p className="muted">{templates.pestel.hints[index]}</p>
   <div className="matrix-entries">{items.length ? items.map((item, i) => entry(state, `${current}-${i}`, item)) : empty}</div>
   <div className="matrix-wheel-steps">
    <button type="button" className="button" onClick={step(-1)}>‹ {lenses[(index + 5) % 6]}</button>
    <span className="muted">Lens {index + 1} of 6</span>
    <button type="button" className="button button-primary" onClick={step(1)}>{lenses[(index + 1) % 6]} ›</button>
   </div>
  </aside>
 </div>;
}

// Porter — rivalry at the centre, the four outside forces pressing in on it.
function porterField(values: MatrixFields, state: Focus): ReactNode {
 const centre = "Competitive rivalry";
 const all = state.focus === centre;
 const force = (category: string, area: string) => {
  const on = state.focus === category;
  const dim = state.focus !== null && !on && !all;
  return <button key={category} type="button" className={`matrix-force matrix-area-${area}${on ? " matrix-force-on" : ""}${dim ? " matrix-dim" : ""}`} aria-pressed={on} onClick={pick(state, category)}>
   <strong>{category}</strong><span className="matrix-force-hint">{templates.porter.hints[templates.porter.categories.indexOf(category)]}</span>
   {of(values, category).length ? <ul>{of(values, category).map((item, i) => <li key={i}>{item.label}{item.notes ? <span>{item.notes}</span> : null}</li>)}</ul> : empty}
  </button>;
 };
 const arrow = (category: string, area: string) => <span key={area} aria-hidden="true" className={`matrix-arrow matrix-area-${area}${state.focus === category || all ? " matrix-arrow-on" : ""}`} />;
 return <div className="matrix-field">
  {force("New entrants", "n")}{arrow("New entrants", "an")}
  {force("Suppliers", "w")}{arrow("Suppliers", "aw")}
  <button type="button" className={`matrix-centre matrix-area-c${all ? " matrix-force-on" : ""}`} aria-pressed={all} onClick={pick(state, centre)}>
   <span className="eyebrow">At the centre</span><strong>{centre}</strong>
   {of(values, centre).length ? <ul>{of(values, centre).map((item, i) => <li key={i}>{item.label}{item.notes ? <span>{item.notes}</span> : null}</li>)}</ul> : empty}
   <span className="matrix-centre-hint">Every arrow presses here</span>
  </button>
  {arrow("Buyers", "ae")}{force("Buyers", "e")}
  {arrow("Substitutes", "as")}{force("Substitutes", "s")}
 </div>;
}

// BCG — the server's quadrant names the move; each card keeps the two inputs
// that placed it, and the small map keeps the server's own positions.
function bcgBoard(values: MatrixFields, points: MatrixPoint[], state: Focus): ReactNode {
 const columns: [string, string, string][] = [["Stars", "Invest", "High growth · high share"], ["Question marks", "Decide", "High growth · low share"], ["Cash cows", "Harvest", "Low growth · high share"], ["Dogs", "Review", "Low growth · low share"]];
 const placed = values.items.map((item, i) => ({ item, n: i + 1, point: points[i] }));
 const unplaced = placed.filter(row => !row.point);
 return <div className="matrix-board-layout">
  {points.length ? <div className="matrix-board-map" role="img" aria-label={`Positions from the server: market growth upwards, relative share to the left, centred on 1× share and ${values.growth_threshold_pct}% growth.`}>
   <svg viewBox="0 0 1000 600" aria-hidden="true">
    <rect className="matrix-plot-bg" x="0" y="0" width="1000" height="600" rx="24" />
    <path className="matrix-axis" d="M500 0V600 M0 300H1000" />
    {points.map((point, i) => <g key={i}><circle className="matrix-dot" cx={point.x} cy={point.y} r="44" /><text className="matrix-dot-number" x={point.x} y={point.y + 14} textAnchor="middle">{i + 1}</text><title>{point.label}: {point.category}</title></g>)}
   </svg>
   <span className="muted">← Higher share · {values.growth_threshold_pct}% growth line · Higher growth ↑</span>
  </div> : null}
  <div className="matrix-board">
   {columns.map(([quadrant, move, rule]) => {
    const rows = placed.filter(row => row.point?.category === quadrant);
    const dim = state.focus !== null && state.focus !== quadrant;
    return <section key={quadrant} className={`matrix-board-column matrix-board-${move.toLowerCase()}${dim ? " matrix-dim" : ""}`}>
     <button type="button" className="matrix-board-head" aria-pressed={state.focus === quadrant} onClick={pick(state, quadrant)}>
      <span className="matrix-board-name"><strong>{quadrant}</strong><span>{rows.length}</span></span>
      <span className="matrix-move">{move}</span><span className="matrix-board-rule">{rule}</span>
     </button>
     {rows.length ? rows.map(({ item, n }) => {
      const key = `bcg-${n}`;
      const isOpen = state.open === key;
      return <button key={key} type="button" className={isOpen ? "matrix-card matrix-card-open" : "matrix-card"} aria-expanded={isOpen} onClick={toggle(state, key)}>
       <span className="matrix-card-title"><span className="matrix-card-number">{n}</span>{item.label}</span>
       <span className="matrix-card-figures"><span><em>Growth</em>{item.growth_pct}%</span><span><em>Share</em>{item.relative_share}×</span></span>
       {isOpen ? <span className="matrix-entry-note">{item.notes || "No note recorded."}</span> : null}
      </button>;
     }) : empty}
    </section>;
   })}
  </div>
  {unplaced.length ? <p className="matrix-placeholder">{unplaced.length === values.items.length ? "View the diagram to place these products." : "Some products are waiting for a preview to be placed."} {unplaced.map(row => `${row.n}. ${row.item.label} (${row.item.growth_pct}% · ${row.item.relative_share}×)`).join(" · ")}</p> : null}
 </div>;
}

// Ansoff — four steps, each a further move from what the business knows.
function ansoffStairs(values: MatrixFields, state: Focus): ReactNode {
 const steps = templates.ansoff.categories;
 const current = state.focus && steps.includes(state.focus) ? state.focus : steps[0];
 const index = steps.indexOf(current);
 const items = of(values, current);
 return <div className="matrix-stairs-layout">
  <section className="matrix-stairs-detail" aria-live="polite">
   <div><span className="eyebrow">Step {index + 1} · {templates.ansoff.hints[index]}</span><h3>{current}</h3></div>
   <div className="matrix-entries matrix-entries-grid">{items.length ? items.map((item, i) => entry(state, `${current}-${i}`, item)) : empty}</div>
  </section>
  <div className="matrix-stairs">
   <span className="matrix-risk" aria-hidden="true"><span>Higher risk</span><i /><span>Lower risk</span></span>
   {steps.map((step, i) => <button key={step} type="button" className={`matrix-step matrix-step-${i}`} aria-pressed={step === current} onClick={() => { state.setFocus(step); state.setOpen(null); }}>
    <span className="matrix-step-number">0{i + 1}</span><strong>{step}</strong><span>{templates.ansoff.hints[i]}</span><span className="matrix-step-count">{count(of(values, step).length, "move")}</span>
   </button>)}
  </div>
 </div>;
}

// Fishbone — six families of cause narrowing toward the one effect.
function fishboneFunnel(values: MatrixFields, state: Focus): ReactNode {
 const families = templates.fishbone.categories;
 const curves = ["M83 0 C 83 110, 470 130, 520 190", "M250 0 C 250 100, 500 130, 540 190", "M417 0 C 417 80, 550 130, 555 190", "M583 0 C 583 80, 570 130, 565 190", "M750 0 C 750 100, 620 130, 580 190", "M917 0 C 917 110, 650 130, 600 190"];
 const traced = state.open ? values.items.find((item, i) => `cause-${i}` === state.open) : undefined;
 return <div className="matrix-funnel">
  <div className="matrix-families">
   {families.map((family, f) => {
    const on = state.focus === family;
    const dim = state.focus !== null && !on;
    return <section key={family} className={`matrix-family${f % 2 ? " matrix-family-alt" : ""}${on ? " matrix-family-on" : ""}${dim ? " matrix-dim" : ""}`}>
     <button type="button" className="matrix-family-head" aria-pressed={on} onClick={() => { state.setFocus(on ? null : family); state.setOpen(null); }}>
      <span className="matrix-family-number">0{f + 1}</span><strong>{family}</strong><span>{templates.fishbone.hints[f]}</span>
     </button>
     {of(values, family).length ? values.items.map((item, i) => item.category !== family ? null : <button key={i} type="button" className={state.open === `cause-${i}` ? "matrix-cause matrix-cause-on" : "matrix-cause"} aria-pressed={state.open === `cause-${i}`} onClick={() => { state.setFocus(family); state.setOpen(state.open === `cause-${i}` ? null : `cause-${i}`); }}>{item.label}</button>) : empty}
    </section>;
   })}
  </div>
  <svg className="matrix-funnel-lines" viewBox="0 0 1000 190" preserveAspectRatio="none" aria-hidden="true">
   {families.map((family, f) => <path key={family} d={curves[f]} className={`matrix-funnel-line${f % 2 ? " matrix-funnel-line-alt" : ""}${state.focus === family ? " matrix-funnel-line-on" : ""}${state.focus !== null && state.focus !== family ? " matrix-funnel-line-dim" : ""}`} />)}
  </svg>
  <div className="matrix-effect" aria-live="polite">
   <span className="eyebrow">The effect</span>
   <strong>{values.effect || "Define the problem"}</strong>
   {traced ? <span className="matrix-trace">Tracing · {traced.category} → {traced.label}{traced.notes ? ` — ${traced.notes}` : ""}</span> : null}
  </div>
 </div>;
}
