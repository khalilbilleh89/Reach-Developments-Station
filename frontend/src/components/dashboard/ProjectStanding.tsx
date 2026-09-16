"use client";

import type { ProjectDetail } from "@/lib/api";
import type { ConstructionSummary } from "@/lib/api";
import { businessDate } from "@/lib/format";

/**
 * Where the project is, in four facts an owner can read without arithmetic.
 *
 * Each cell says what the modules already say, or says plainly that nothing is
 * recorded yet. "Not scheduled" is a real answer and is written as one: a dash
 * in its place would read as a page that failed to load rather than a project
 * that has not set a date.
 */
export function ProjectStanding({
  project,
  build,
  hasCostBasis,
}: {
  project: ProjectDetail;
  build: ConstructionSummary | null;
  /** Whether a cost basis governs the project, decided by the caller's read of economics. */
  hasCostBasis: boolean | null;
}) {
  return (
    <div className="project-standing">
      <div className="project-standing-cell">
        <span className="project-standing-label">Planned completion</span>
        <strong className={project.planned_completion ? "project-standing-value num" : "project-standing-value project-standing-absent"}>
          {project.planned_completion ? businessDate(project.planned_completion) : "Not scheduled"}
        </strong>
      </div>
      <div className="project-standing-cell">
        <span className="project-standing-label">Construction</span>
        <strong className={build?.budget_version_number ? "project-standing-value num" : "project-standing-value project-standing-absent"}>
          {build?.budget_version_number ? `Budget v${build.budget_version_number}` : "No budget in force"}
        </strong>
      </div>
      <div className="project-standing-cell">
        <span className="project-standing-label">Permits</span>
        <strong
          className={
            project.blocking_permit_count > 0 || project.overdue_permit_count > 0
              ? "project-standing-value project-standing-flagged num"
              : "project-standing-value num"
          }
        >
          {project.blocking_permit_count > 0
            ? `${project.blocking_permit_count} blocking`
            : "None blocking"}
        </strong>
        <span className="project-standing-note">{project.overdue_permit_count} past their statutory period</span>
      </div>
      <div className="project-standing-cell">
        <span className="project-standing-label">Cost basis</span>
        <strong className={hasCostBasis ? "project-standing-value num" : "project-standing-value project-standing-absent"}>
          {hasCostBasis === null ? "Not visible to you" : hasCostBasis ? "In force" : "None approved"}
        </strong>
      </div>
    </div>
  );
}
