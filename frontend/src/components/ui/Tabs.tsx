"use client";

/**
 * The project's sections.
 *
 * A real tablist, so the arrow keys work and a screen reader announces which of
 * eight sections is showing. On a phone the row scrolls sideways rather than
 * wrapping into three ragged lines.
 */
export function Tabs({
  label,
  tabs,
  active,
  onSelect,
}: {
  label: string;
  tabs: { key: string; label: string }[];
  active: string;
  onSelect: (key: string) => void;
}) {
  const move = (index: number, step: number) => {
    const next = tabs[(index + step + tabs.length) % tabs.length];
    if (next) onSelect(next.key);
  };

  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((tab, index) => (
        <button
          key={tab.key}
          id={`tab-${tab.key}`}
          role="tab"
          type="button"
          aria-selected={active === tab.key}
          aria-controls={`tabpanel-${tab.key}`}
          tabIndex={active === tab.key ? 0 : -1}
          className={`tab ${active === tab.key ? "tab-active" : ""}`}
          onClick={() => onSelect(tab.key)}
          onKeyDown={(event) => {
            if (event.key === "ArrowRight") {
              event.preventDefault();
              move(index, 1);
            } else if (event.key === "ArrowLeft") {
              event.preventDefault();
              move(index, -1);
            }
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

/** The region a tab reveals. Separate so every tab is labelled by its control. */
export function TabPanel({ tab, children }: { tab: string; children: React.ReactNode }) {
  return (
    <div id={`tabpanel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="stack">
      {children}
    </div>
  );
}
