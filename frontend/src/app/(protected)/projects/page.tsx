"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { ProjectsTable } from "@/components/projects/ProjectsTable";
import { ProjectDetailView } from "@/components/projects/ProjectDetailView";
import { listProjects, getProject, createProject, deleteProject } from "@/lib/projects-api";
import type { Project, ProjectCreate, ProjectStatus } from "@/lib/projects-types";
import { CreateProjectModal } from "@/components/projects/CreateProjectModal";
import styles from "@/styles/projects.module.css";

/**
 * ProjectsList — filterable portfolio view shown when no project is selected.
 */
function ProjectsList() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [statusFilter, setStatusFilter] = useState<ProjectStatus | "">("");
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Debounce raw search input by 350 ms to reduce request volume
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 350);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchProjects = useCallback(() => {
    setLoading(true);
    listProjects({
      status: statusFilter || undefined,
      search: debouncedSearch || undefined,
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
  }, [statusFilter, debouncedSearch]);

  // Fetch projects whenever status filter or debounced search changes
  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleCreateProject = useCallback(async (data: ProjectCreate) => {
    // Let the error propagate so CreateProjectModal can display it.
    // setShowCreateModal and fetchProjects only run on success.
    await createProject(data);
    setShowCreateModal(false);
    fetchProjects();
  }, [fetchProjects]);

  const handleDeleteProject = useCallback(async (projectId: string) => {
    try {
      await deleteProject(projectId);
      fetchProjects();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete project.");
    }
  }, [fetchProjects]);

  const handleSelectProject = useCallback(
    (projectId: string) => {
      router.push(`/projects?id=${encodeURIComponent(projectId)}`);
    },
    [router],
  );

  const activeCount = projects.filter((p) => p.status === "active").length;
  const pipelineCount = projects.filter((p) => p.status === "pipeline").length;
  const completedCount = projects.filter((p) => p.status === "completed").length;

  return (
    <PageContainer
      title="Projects"
      subtitle="Manage and monitor all development projects."
      actions={
        <button
          type="button"
          className={styles.addButton}
          onClick={() => setShowCreateModal(true)}
        >
          + Create Project
        </button>
      }
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
            onChange={(e) =>
              setStatusFilter(e.target.value as ProjectStatus | "")
            }
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
      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className={styles.loadingText}>Loading projects\u2026</div>
      )}

      {/* Table */}
      {!loading && !error && (
        <ProjectsTable
          projects={projects}
          onSelectProject={handleSelectProject}
          onCreateProject={() => setShowCreateModal(true)}
          onDeleteProject={handleDeleteProject}
        />
      )}

      {/* Create Project modal */}
      {showCreateModal && (
        <CreateProjectModal
          onSubmit={handleCreateProject}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </PageContainer>
  );
}

/**
 * ProjectDetailPage — loads and displays a single project with its phases.
 */
function ProjectDetailPage({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getProject(projectId)
      .then((p) => {
        setProject(p);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load project.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleBack = useCallback(() => {
    router.push("/projects");
  }, [router]);

  return (
    <PageContainer title="Project Detail" subtitle="View and manage project phases.">
      {loading && (
        <div className={styles.loadingText}>Loading project\u2026</div>
      )}
      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}
      {!loading && !error && project && (
        <ProjectDetailView project={project} onBack={handleBack} />
      )}
    </PageContainer>
  );
}

/**
 * Inner — reads query params and delegates to list or detail view.
 *
 * Must be a separate component so useSearchParams() is inside a Suspense boundary.
 */
function Inner() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("id");

  if (projectId) {
    return <ProjectDetailPage projectId={projectId} />;
  }
  return <ProjectsList />;
}

/**
 * Projects page — wraps Inner in Suspense as required by useSearchParams.
 */
export default function Page() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
