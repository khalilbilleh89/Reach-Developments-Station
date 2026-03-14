"use client";

import React, { useEffect, useState } from "react";
import { getProjects, type Project } from "@/lib/dashboard-api";
import styles from "@/styles/dashboard.module.css";

interface ProjectSelectorProps {
  /** Called whenever the selected project changes. */
  onSelect: (project: Project) => void;
  /** Currently selected project id (controlled). */
  selectedId?: string;
}

/**
 * ProjectSelector — dropdown for switching the active project.
 *
 * Fetches the project list from GET /api/v1/projects on mount and notifies
 * the parent via onSelect when the user picks a different project.
 */
export function ProjectSelector({ onSelect, selectedId }: ProjectSelectorProps) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProjects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0 && !selectedId) {
          onSelect(list[0]);
        }
      })
      .catch((err: unknown) => {
        const message =
          err instanceof Error ? err.message : "Failed to load projects.";
        setError(message);
      })
      .finally(() => setLoading(false));
  // selectedId is intentionally omitted — we only run this once on mount
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onSelect]);

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const project = projects.find((p) => p.id === e.target.value);
    if (project) {
      onSelect(project);
    }
  };

  if (loading) {
    return (
      <div className={styles.selectorRow}>
        <span className={styles.selectorLabel}>Project</span>
        <span className={styles.emptyMessage}>Loading projects…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.selectorRow}>
        <span className={styles.selectorLabel}>Project</span>
        <span className={styles.emptyMessage}>{error}</span>
      </div>
    );
  }

  if (projects.length === 0) {
    return (
      <div className={styles.selectorRow}>
        <span className={styles.selectorLabel}>Project</span>
        <span className={styles.emptyMessage}>No projects found.</span>
      </div>
    );
  }

  return (
    <div className={styles.selectorRow}>
      <label htmlFor="project-selector" className={styles.selectorLabel}>
        Project
      </label>
      <select
        id="project-selector"
        className={styles.selectorSelect}
        value={selectedId ?? ""}
        onChange={handleChange}
        aria-label="Select project"
      >
        {projects.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
    </div>
  );
}
