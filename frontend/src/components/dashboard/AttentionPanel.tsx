"use client";

import type { ProjectSection } from "@/components/shell/navigation";
import { Button, Card, Icon, Loading, Notice } from "@/components/ui";
import type { Tone } from "@/components/ui";

/**
 * One thing the server says needs somebody's attention.
 *
 * Every item is a count the API returned on this request — overdue permits,
 * accounts past grace, units whose price no longer describes them. Nothing is
 * scored, ranked or weighted here: the list is in the order of the development
 * lifecycle, and the tone repeats the word the module already uses for the
 * same state.
 */
export interface AttentionItem {
  key: string;
  count: number;
  title: string;
  hint: string;
  tone: Tone;
  section: ProjectSection;
}

export function AttentionPanel({
  items,
  loading,
  problems,
  onNavigate,
}: {
  items: AttentionItem[];
  loading: boolean;
  /** Modules that could not answer, said plainly rather than shown as zero. */
  problems: string[];
  onNavigate: (section: ProjectSection) => void;
}) {
  const shown = items.filter((item) => item.count > 0);
  return (
    <Card title="Needs attention" description="What the system has flagged, in lifecycle order.">
      {problems.map((problem) => (
        <Notice key={problem} tone="warning">
          {problem}
        </Notice>
      ))}
      {loading && shown.length === 0 ? (
        <Loading label="Checking the project…" lines={3} />
      ) : shown.length === 0 ? (
        <p className="attention-clear">
          <Icon name="check" />
          Nothing is flagged for attention.
        </p>
      ) : (
        <ul className="attention-list">
          {shown.map((item) => (
            <li key={item.key} className="attention-item">
              <span
                className={
                  item.tone === "danger"
                    ? "attention-count attention-count-danger"
                    : item.tone === "warning"
                      ? "attention-count attention-count-warning"
                      : "attention-count"
                }
              >
                {item.count}
              </span>
              <div className="attention-text">
                <p className="attention-title">{item.title}</p>
                <p className="attention-hint">{item.hint}</p>
              </div>
              <Button small variant="quiet" onClick={() => onNavigate(item.section)}>
                Open
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
