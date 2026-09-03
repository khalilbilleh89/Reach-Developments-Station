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

/**
 * What is owed, blocked or overdue, as a list of counts and their way in.
 *
 * The card takes the attention tone only when it has something to say. A page
 * where nothing is flagged is good news, and drawing good news in warning
 * colours teaches people to ignore the colour.
 *
 * There is no score and no ranking. Ordering these by a weight the browser
 * invented would put a number in front of a director that no one on the
 * finance team could reproduce; lifecycle order is the order the development
 * itself runs in, and it needs no arithmetic to defend.
 */
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
  const flagged = shown.length > 0;
  return (
    <Card
      title="Needs attention"
      description={flagged ? "In lifecycle order." : undefined}
      tone={flagged ? "attention" : undefined}
    >
      {problems.map((problem) => (
        <Notice key={problem} tone="warning">
          {problem}
        </Notice>
      ))}
      {loading && !flagged ? (
        <Loading label="Checking the project…" lines={3} />
      ) : !flagged ? (
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
