"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { ProjectStructureTree } from "@/components/project-structure/ProjectStructureTree";
import { getProjectStructure } from "@/lib/project-structure-api";
import type { ProjectStructureResponse } from "@/lib/project-structure-types";
import styles from "@/styles/project-structure.module.css";

/**
 * ProjectStructureClient
 *
 * Client component for the project structure viewer page.
 * Handles data fetching, loading/error state, and hierarchy rendering.
 *
 * Separated from page.tsx so that the server route entry can export
 * `generateStaticParams` / `dynamicParams` without mixing server and
 * client module boundaries (App Router requirement).
 *
 * Data source:
 *   GET /api/v1/projects/{projectId}/structure
 */
export function ProjectStructureClient() {
  const params = useParams<{ id: string }>();
  const projectId = params?.id ?? "";

  const [structure, setStructure] = useState<ProjectStructureResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId || projectId === "_") {
      setLoading(false);
      setStructure(null);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    getProjectStructure(projectId)
      .then(setStructure)
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load project structure.",
        );
      })
      .finally(() => setLoading(false));
  }, [projectId]);

  const title = structure
    ? `${structure.project_name} — Structure`
    : "Project Structure";

  const subtitle = structure
    ? `${structure.project_code} · ${structure.project_status}`
    : "Canonical hierarchy: Phase → Building → Floor → Unit";

  return (
    <PageContainer title={title} subtitle={subtitle}>
      {loading ? (
        <div className={styles.loadingState}>Loading project structure…</div>
      ) : error ? (
        <div className={styles.errorState} role="alert">
          {error}
        </div>
      ) : structure ? (
        <ProjectStructureTree structure={structure} />
      ) : null}
    </PageContainer>
  );
}
