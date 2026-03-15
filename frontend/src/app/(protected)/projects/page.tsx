"use client";

import React, { useEffect, useState } from "react";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { ProjectsTable } from "@/components/projects/ProjectsTable";
import { listProjects } from "@/lib/projects-api";
import type { Project } from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

/**
 * Projects page -- live data from /api/v1/projects.
 *
 * Displays KPI cards and a sortable project table backed by real backend records.
 */
export default function Page() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    listProjects({
      status: statusFilter || undefined,
      search: search || undefined,
      limit: 500,
    })
      .then((resp) => {
        setProjects(resp.items);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load projects.");
        setProjects([]);
      })
      .finally(() => setLoading(false));
  }, [statusFilter, search]);

  const activeCount = projects.filter((p) => p.status === "active").length;
  const pipelineCount = projects.filter((p) => p.status === "pipeline").length;
  const completedCount = projects.filter((p) => p.status === "completed").length;

  return (
    <PageContainer
      title="Projects"
      subtitle="Manage and monitor all development projects."
    >
      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Total Projects"
          value={loading ? "\u2026" : projects.length}
          subtitle="All statuses"
          icon="📁"
        />
        <MetricCard
          title="Active"
          value={loading ? "\u2026" : activeCount}
          subtitle="In progress"
          icon="🏗️"
        />
        <MetricCard
          title="Pipeline"
          value={loading ? "\u2026" : pipelineCount}
          subtitle="Upcoming"
          icon="📋"
        />
        <MetricCard
          title="Completed"
          value={loading ? "\u2026" : completedCount}
          subtitle="Delivered"
          icon="✅"
        />
      </div>

      {/* Filter bar */}
      <div className={styles.filterBar}>
        <div className={styles.filterGroup}>
          <label htmlFor="status-filter" className={styles.filterLabel}>
            Status
          </label>
          <select
            id="status-filter"
            className={styles.filterSelect}
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="pipeline">Pipeline</option>
            <option value="active">Active</option>
            <option value="completed">Completed</option>
            <option value="on_hold">On Hold</option>
          </select>
        </div>
        <div className={styles.filterGroup}>
          <label htmlFor="search-filter" className={styles.filterLabel}>
            Search
          </label>
          <input
            id="search-filter"
            type="text"
            className={styles.filterInput}
            placeholder="Name or code..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Section header */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Development Portfolio</h2>
        {!loading && (
          <span className={styles.sectionNote}>
            {projects.length} project{projects.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Error */}
      {error && <div className={styles.errorBanner}>\u26a0\ufe0f {error}</div>}

      {/* Loading */}
      {loading && <div className={styles.loadingText}>Loading projects\u2026</div>}

      {/* Table */}
      {!loading && !error && <ProjectsTable projects={projects} />}
    </PageContainer>
  );
}
