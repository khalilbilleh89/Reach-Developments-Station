"use client";

import { useState } from "react";
import type { ReactNode } from "react";

import { Segmented } from "./Segmented";
import { Tabs, TabPanel } from "./Tabs";

export interface View {
  key: string;
  label: string;
  /**
   * The one-line answer this view holds (design system D4): "Top branch ·
   * Limassol · 6 sales". It is a server-ordered fact, never a figure the
   * browser worked out. A view without one is reached from the strip alone.
   */
  answer?: { label: string; value: ReactNode; note?: ReactNode };
  content: ReactNode;
}

/**
 * Breakdowns of the same population, one on screen at a time, none hidden
 * behind an accordion (design system D1, D2, D4).
 *
 * The strip switches which breakdown is shown and the first is open on load,
 * so a reader never meets a row of closed arrows. `strip="segmented"` is for
 * two or three alternatives of one table (branches or salespeople);
 * `strip="tabs"` for a set of distinct breakdowns (property type, view).
 * Where every view carries an answer, the answers lead as tiles and a tile
 * opens its view.
 */
export function Views({ label, views, strip = "segmented", initial }: {
  label: string;
  views: View[];
  strip?: "segmented" | "tabs";
  initial?: string;
}) {
  const [active, setActive] = useState(initial ?? views[0]?.key ?? "");
  const current = views.find((view) => view.key === active) ?? views[0];
  if (!current) return null;
  const answers = views.every((view) => view.answer);

  return <div className="views">
    {answers ? <div className="views-answers" role="group" aria-label={`${label}: at a glance`}>
      {views.map((view) => <button
        key={view.key}
        type="button"
        className={view.key === current.key ? "answer-tile answer-tile-active" : "answer-tile"}
        aria-pressed={view.key === current.key}
        onClick={() => setActive(view.key)}
      >
        <span className="answer-tile-label">{view.answer?.label}</span>
        <span className="answer-tile-value">{view.answer?.value}</span>
        {view.answer?.note ? <span className="answer-tile-note">{view.answer.note}</span> : null}
        <span className="answer-tile-go">See all {view.label.toLowerCase()}</span>
      </button>)}
    </div> : null}
    {strip === "tabs"
      ? <>
        <Tabs label={label} tabs={views.map((view) => ({ key: view.key, label: view.label }))} active={current.key} onSelect={setActive} />
        <TabPanel group={label} tab={current.key} className="views-body">{current.content}</TabPanel>
      </>
      : <>
        <Segmented label={label} value={current.key} options={views.map((view) => ({ value: view.key, label: view.label }))} onChange={setActive} />
        <div className="views-body">{current.content}</div>
      </>}
  </div>;
}
