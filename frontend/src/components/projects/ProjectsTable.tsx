"use client";

import React, { useState } from "react";
import type { Project } from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

type SortField = "name" | "code" | "status" | "developer_name" | "location" | "start_date" | "target_end_date";
type SortDir = "asc" | "desc";

interface ProjectsTableProps {
  projects: Project[];
  onSelectProject?: (projectId: string) => void;
}

function statusClass(status: string): string {
  switch (status) {
    case "active":
      return styles.statusActive;
    case "completed":
      return styles.statusCompleted;
    case "on_hold":
      return styles.statusOnHold;
    default:
      return styles.statusPipeline;
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "on_hold":
      return "On Hold";
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "\u2014";
  return new Date(dateStr).toLocaleDateString("en-GB", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * ProjectsTable — sortable table of live project records.
 *
 * All data comes from the live /api/v1/projects backend endpoint.
 * Sortable headers use <button> inside <th> for full keyboard accessibility.
 */
export function ProjectsTable({ projects, onSelectProject }: ProjectsTableProps) {
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const handleSort = (field: SortField) => {
    if (field === sortField) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sorted = [...projects].sort((a, b) => {
    const aVal = (a[sortField] ?? "") as string;
    const bVal = (b[sortField] ?? "") as string;
    if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
    if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
    return 0;
  });

  /** aria-sort value for a given column header */
  const ariaSortFor = (field: SortField): React.AriaAttributes["aria-sort"] =>
    field === sortField ? (sortDir === "asc" ? "ascending" : "descending") : "none";

  /** Sort button rendered inside each <th> */
  const SortButton = ({
    field,
    children,
  }: {
    field: SortField;
    children: React.ReactNode;
  }) => (
    <button
      type="button"
      className={styles.sortButton}
      onClick={() => handleSort(field)}
    >
      {children}
      {field === sortField && (
        <span className={styles.sortIndicator} aria-hidden="true">
          {sortDir === "asc" ? "\u2191" : "\u2193"}
        </span>
      )}
    </button>
  );

  if (projects.length === 0) {
    return (
      <div className={styles.emptyState}>
        <div className={styles.emptyIcon}>📁</div>
        <div className={styles.emptyText}>No projects found</div>
        <div className={styles.emptySubtext}>
          Create your first project to get started.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table} aria-label="Projects list">
        <thead>
          <tr>
            <th scope="col" aria-sort={ariaSortFor("name")}>
              <SortButton field="name">Project</SortButton>
            </th>
            <th scope="col" aria-sort={ariaSortFor("developer_name")}>
              <SortButton field="developer_name">Developer</SortButton>
            </th>
            <th scope="col" aria-sort={ariaSortFor("location")}>
              <SortButton field="location">Location</SortButton>
            </th>
            <th scope="col" aria-sort={ariaSortFor("status")}>
              <SortButton field="status">Status</SortButton>
            </th>
            <th scope="col" aria-sort={ariaSortFor("start_date")}>
              <SortButton field="start_date">Start Date</SortButton>
            </th>
            <th scope="col" aria-sort={ariaSortFor("target_end_date")}>
              <SortButton field="target_end_date">Target End</SortButton>
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((project) => (
            <tr
              key={project.id}
              className={onSelectProject ? styles.clickableRow : undefined}
              onClick={onSelectProject ? () => onSelectProject(project.id) : undefined}
              style={onSelectProject ? { cursor: "pointer" } : undefined}
            >
              <td>
                <div className={styles.projectName}>{project.name}</div>
                <div className={styles.projectCode}>{project.code}</div>
              </td>
              <td>{project.developer_name ?? "\u2014"}</td>
              <td>{project.location ?? "\u2014"}</td>
              <td>
                <span className={`${styles.badge} ${statusClass(project.status)}`}>
                  {statusLabel(project.status)}
                </span>
              </td>
              <td>{formatDate(project.start_date)}</td>
              <td>{formatDate(project.target_end_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
