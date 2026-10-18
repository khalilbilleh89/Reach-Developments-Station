"use client";

import { useState } from "react";
import type { CSSProperties, MouseEvent } from "react";
import type { Footprint, Masterplan, Point } from "@/lib/api/masterplans";
import type { UnitSummary } from "@/lib/api";
import { Button, Field } from "@/components/ui";
import { statusLabel } from "./statusLabels";

export function projectPoint(point: Point, z: number, aspect: number, yaw: number, pitch: number): Point {
  const x = (point[0] - 0.5) * 1000, y = (point[1] - 0.5) * 1000 * aspect;
  const a = yaw * Math.PI / 180, b = pitch * Math.PI / 180;
  return [x * Math.cos(a) - y * Math.sin(a), (x * Math.sin(a) + y * Math.cos(a)) * Math.sin(b) - z * Math.cos(b)];
}
const pointsString = (points: Point[]) => points.map(p => p.join(",")).join(" ");

/** Drawing coordinates remain independent of zoom, viewport and 3D camera. */
export function MasterplanCanvas({ plan, preview, mappings, units, selected, onSelect, draft, onPoint, threeD = false }: {
  plan: Masterplan; preview: string; mappings: Footprint[]; units: UnitSummary[];
  selected?: string; onSelect?: (mapping: Footprint) => void;
  draft?: Point[]; onPoint?: (point: Point) => void; threeD?: boolean;
}) {
  const [zoom, setZoom] = useState(1), [yaw, setYaw] = useState(-25), [pitch, setPitch] = useState(42);
  const [pan, setPan] = useState<Point>([0, 0]);
  const [imageError, setImageError] = useState(false);
  const aspect = plan.pixel_height / plan.pixel_width;
  const widthM = Number(plan.width_m);
  const spatial = threeD && plan.kind === "plan" && widthM > 0;
  const project = (p: Point, z = 0): Point => spatial ? projectPoint(p, z * 1000 / widthM, aspect, yaw, pitch) : [p[0] * 1000, p[1] * 1000 * aspect];
  const corners: Point[] = [[0, 0], [1, 0], [1, 1], [0, 1]];
  const ground = corners.map(p => project(p));
  const faces = mappings.map(mapping => ({ mapping, unit: units.find(u => u.id === mapping.unit_id), bottom: mapping.points.map(p => project(p, Number(mapping.base_m))), top: mapping.points.map(p => project(p, Number(mapping.base_m) + Number(mapping.height_m))) }));
  const all = [...ground, ...faces.flatMap(f => [...f.top, ...f.bottom])];
  const minX = Math.min(...all.map(p => p[0])) - 30, minY = Math.min(...all.map(p => p[1])) - 30;
  const fullWidth = Math.max(...all.map(p => p[0])) - minX + 30, fullHeight = Math.max(...all.map(p => p[1])) - minY + 30;
  const vw = fullWidth / zoom, vh = fullHeight / zoom;
  const box = `${minX + (fullWidth - vw) / 2 + pan[0]} ${minY + (fullHeight - vh) / 2 + pan[1]} ${vw} ${vh}`;
  const [o, x, , y] = ground;
  const imageMatrix = `matrix(${x[0] - o[0]} ${x[1] - o[1]} ${y[0] - o[0]} ${y[1] - o[1]} ${o[0]} ${o[1]})`;
  const click = (event: MouseEvent<SVGSVGElement>) => {
    if (!onPoint || spatial) return;
    const matrix = event.currentTarget.getScreenCTM();
    if (!matrix) return;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    const normal: Point = [point.x / 1000, point.y / (1000 * aspect)];
    if (normal.every(v => v >= 0 && v <= 1)) onPoint(normal);
  };
  // Painter ordering is camera-dependent. No commercial data is computed here.
  faces.sort((a, b) => Math.max(...a.bottom.map(p => p[1])) - Math.max(...b.bottom.map(p => p[1])));
  return <div className="masterplan-canvas-wrap">
    <div className="masterplan-controls">
      <Field label="Zoom"><input type="range" min="1" max="5" step="0.1" value={zoom} onChange={e => setZoom(Number(e.target.value))} /></Field>
      {spatial ? <><Field label="Rotate"><input type="range" min="-180" max="180" value={yaw} onChange={e => setYaw(Number(e.target.value))} /></Field><Field label="Tilt"><input type="range" min="20" max="80" value={pitch} onChange={e => setPitch(Number(e.target.value))} /></Field></> : null}
      <div className="button-row" aria-label="Pan drawing"><Button aria-label="Pan left" onClick={() => setPan(([x, y]) => [x - 80, y])}>←</Button><Button aria-label="Pan up" onClick={() => setPan(([x, y]) => [x, y - 80])}>↑</Button><Button aria-label="Pan down" onClick={() => setPan(([x, y]) => [x, y + 80])}>↓</Button><Button aria-label="Pan right" onClick={() => setPan(([x, y]) => [x + 80, y])}>→</Button><Button onClick={() => { setZoom(1); setPan([0, 0]); setYaw(-25); setPitch(42); }}>Reset view</Button></div>
    </div>
    {imageError ? <p role="alert">Drawing preview could not load. Refresh the masterplan or check your access.</p> : null}
    <svg className="masterplan-canvas" viewBox={box} onClick={click} aria-label={onPoint ? "Drawing editor. Click vertices, or enter coordinates in the vertex list below." : `${plan.title}: selectable unit footprints`}>
      <title>{plan.title}</title>
      {/* Safe server-rasterised PNG only; uploads never become executable SVG. */}
      <image href={preview} width="1" height="1" preserveAspectRatio="none" transform={imageMatrix} onError={() => setImageError(true)} />
      {faces.map(({ mapping, unit, bottom, top }) => {
        const state = unit?.commercial_status ?? "unmapped";
        const shape = spatial ? top : mapping.points.map(p => project(p));
        const activate = () => onSelect?.(mapping);
        return <g key={mapping.id} className="masterplan-footprint" data-status={state} data-selected={selected === mapping.id || undefined} style={{ "--footprint-opacity": selected === mapping.id ? 0.8 : 0.48 } as CSSProperties}>
          {spatial ? bottom.map((p, i) => <polygon className="masterplan-wall" key={i} points={pointsString([p, bottom[(i + 1) % bottom.length], top[(i + 1) % top.length], top[i]])} onClick={e => { if (onSelect) { e.stopPropagation(); activate(); } }} />) : null}
          <polygon points={pointsString(shape)} role={onSelect ? "button" : undefined} tabIndex={onSelect ? 0 : undefined} aria-label={`${unit?.unit_reference ?? "Unit unavailable"}: ${unit ? statusLabel(state) : "Not in active inventory"}`} onClick={e => { if (onSelect) { e.stopPropagation(); activate(); } }} onKeyDown={e => { if (onSelect && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); activate(); } }}>
            <title>{unit?.unit_reference ?? "Unit unavailable"} · {unit ? statusLabel(state) : "Not in active inventory"}</title>
          </polygon>
        </g>;
      })}
      {draft?.length ? <><polyline className="masterplan-draft" points={pointsString(draft.map(p => project(p)))} />{draft.map((p, i) => <circle className="masterplan-vertex" key={i} cx={project(p)[0]} cy={project(p)[1]} r="4" />)}</> : null}
    </svg>
  </div>;
}
