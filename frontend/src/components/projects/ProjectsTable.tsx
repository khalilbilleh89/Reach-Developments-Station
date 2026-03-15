"use client";

import React, { useState } from "react";
import type { Project } from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

type SortField = "name" | "code" | "status" | "developer_name" | "location" | "start_date" | "target_end_date";
type SortDir = "asc" | "desc";

interface ProjectsTableProps {
  projects: Project[];
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
  if (!dateStr) return "—";
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
 */
export function ProjectsTable({ projects }: ProjectsTableProps) {
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

  const indicator = (field: SortField) =>
    field === sortField ? (
      <span className={styles.sortIndicator} aria-hidden="true">
        {sortDir === "asc" ? "↑" : "↓"}
      </span>
    ) : null;

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
            <th scope="col" onClick={() => handleSort("name")}>
              Project {indicator("name")}
            </th>
            <th scope="col" onClick={() => handleSort("developer_name")}>
              Developer {indicator("developer_name")}
            </th>
            <th scope="col" onClick={() => handleSort("location")}>
              Location {indicator("location")}
            </th>
            <th scope="col" onClick={() => handleSort("status")}>
              Status {indicator("status")}
            </th>
            <th scope="col" onClick={() => handleSort("start_date")}>
              Start Date {indicator("start_date")}
            </th>
            <th scope="col" onClick={() => handleSort("target_end_date")}>
              Target End {indicator("target_end_date")}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((project) => (
            <tr key={project.id}>
              <td>
                <div className={styles.projectName}>{project.name}</div>
                <div className={styles.projectCode}>{project.code}</div>
              </td>
              <td>{project.developer_name ?? "—"}</td>
              <td>{project.location ?? "—"}</td>
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
