/**
 * The whole icon set.
 *
 * Six glyphs, drawn inline, because a project needs an icon package the moment
 * it needs a seventh — and a status product that speaks in words does not.
 * Icons here only ever repeat something the adjacent text already says, so a
 * screen reader is given nothing to announce.
 */

const PATHS = {
  check: "M3.5 8.5 6.5 11.5 12.5 4.5",
  alert: "M8 5v4M8 11.5h.01M8 1.5 15 14H1z",
  info: "M8 7.25v4.25M8 4.75h.01M8 14.5a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z",
  close: "M4 4l8 8M12 4l-8 8",
  chevron: "M6 3.5 10.5 8 6 12.5",
  search: "M7.25 12.5a5.25 5.25 0 1 0 0-10.5 5.25 5.25 0 0 0 0 10.5ZM11 11l3.5 3.5",
} as const;

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
