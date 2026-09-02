/**
 * The whole icon set, drawn by hand.
 *
 * Every glyph is a stroke path on a 16×16 grid. There is no icon package
 * because a product that speaks in words does not need one: an icon here only
 * ever repeats something the adjacent text already says, which is why it is
 * hidden from assistive technology.
 *
 * Adding a glyph is adding a path. The navigation rail takes one per module,
 * so a future module — Construction, Cashflow — brings its own line here.
 */

const PATHS: Record<string, string> = {
  // Feedback
  check: "M3.5 8.5 6.5 11.5 12.5 4.5",
  alert: "M8 5.5v3.5M8 11.5h.01M8 2 14.5 13.5h-13z",
  info: "M8 7.25v4M8 4.75h.01M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z",
  close: "M4 4l8 8M12 4l-8 8",
  // Direction
  chevron: "M6 3.5 10.5 8 6 12.5",
  "chevron-down": "M3.5 6 8 10.5 12.5 6",
  "chevron-left": "M10 3.5 5.5 8 10 12.5",
  "arrow-left": "M13 8H3M7 4 3 8l4 4",
  external: "M9 3h4v4M13 3 7.5 8.5M12 9.5V12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h2.5",
  // Controls
  search: "M7.25 12.5a5.25 5.25 0 1 0 0-10.5 5.25 5.25 0 0 0 0 10.5ZM11 11l3.5 3.5",
  menu: "M2.5 4.5h11M2.5 8h11M2.5 11.5h11",
  "panel-left": "M2.5 3.5h11a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1ZM6 3.5v9",
  plus: "M8 3v10M3 8h10",
  swap: "M4 6.5 6.5 4 9 6.5M6.5 4v8M12 9.5 9.5 12 7 9.5",
  filter: "M2.5 4h11M4.5 8h7M6.5 12h3",
  // Places
  projects: "M2.5 5.5a1 1 0 0 1 1-1h3l1.5 1.5h4.5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1Z",
  overview: "M2.5 2.5h4.5v4.5H2.5ZM9 2.5h4.5V6H9ZM9 8h4.5v5.5H9ZM2.5 9.5H7v4H2.5Z",
  land: "M2 4.5 6 3l4 1.5 4-1.5v8L10 12.5 6 11l-4 1.5ZM6 3v8M10 4.5v8",
  permits: "M4 2.5h6l3 3v8a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-10a1 1 0 0 1 1-1ZM10 2.5v3h3M5.5 9.5 7 11l3.5-3.5",
  inventory: "M2.5 13.5h11M3.5 13.5V3.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v10M10.5 7h2a1 1 0 0 1 1 1v5.5M5.5 5h2M5.5 7.5h2M5.5 10h2",
  pricing: "M2.5 8.5v-5a1 1 0 0 1 1-1h5l5 5-6 6-5-5ZM5.5 5.5h.01",
  sales: "M3 12.5V4a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v8.5M5 6h6M5 8.5h4M2 13h12",
  payments: "M2.5 4.5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1ZM2.5 7h11M5.5 2v3M10.5 2v3",
  collections: "M1.5 5.5a1 1 0 0 1 1-1h11a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-11a1 1 0 0 1-1-1ZM8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM4 8h.01M12 8h.01",
  economics: "M2.5 13.5h11M3.5 11V7M6.5 11V4M9.5 11V6M12.5 11V2.5",
  documents: "M4 2.5h5l3 3v7a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1ZM9 2.5v3h3M5.5 8h5M5.5 10.5h5",
  access: "M8 1.5 13 3.5v4c0 3-2.2 5.2-5 6.5-2.8-1.3-5-3.5-5-6.5v-4ZM6 8l1.5 1.5L10.5 6.5",
  settings: "M8 10.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M3.4 12.6l1.4-1.4M11.2 4.8l1.4-1.4",
  user: "M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM2.5 14c.5-3 2.7-4.5 5.5-4.5s5 1.5 5.5 4.5",
  "sign-out": "M6.5 2.5H3.5a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3M10 5l3 3-3 3M13 8H6",
  building: "M3.5 13.5V3a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v10.5M2 13.5h12M6 5h1.5M8.5 5H10M6 7.5h1.5M8.5 7.5H10M6 10h1.5M8.5 10H10",
  calendar: "M2.5 4.5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1ZM2.5 7h11M5.5 2v3M10.5 2v3",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, className }: { name: IconName; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
