"use client";

import React, { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageContainer } from "@/components/shell/PageContainer";
import { MetricCard } from "@/components/dashboard/MetricCard";
import { ConstructionScopesTable } from "@/components/construction/ConstructionScopesTable";
import { ScopeDetailView } from "@/components/construction/ScopeDetailView";
import { CreateScopeModal } from "@/components/construction/CreateScopeModal";
import { listScopes, getScope, createScope, deleteScope } from "@/lib/construction-api";
import type {
  ConstructionScope,
  ConstructionScopeCreate,
  ConstructionStatus,
} from "@/lib/construction-types";
import styles from "@/styles/construction.module.css";

/**
 * ConstructionList — filterable portfolio view shown when no scope is selected.
 */
function ConstructionList() {
  const router = useRouter();
  const [scopes, setScopes] = useState<ConstructionScope[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<ConstructionStatus | "">("");
  const [showCreateModal, setShowCreateModal] = useState(false);

  const fetchScopes = useCallback(() => {
    setLoading(true);
    listScopes({ limit: 500 })
      .then((resp) => {
        setScopes(resp.items);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load construction scopes.");
        setScopes([]);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchScopes();
  }, [fetchScopes]);

  const handleCreateScope = useCallback(
    async (data: ConstructionScopeCreate) => {
      await createScope(data);
      setShowCreateModal(false);
      fetchScopes();
    },
    [fetchScopes],
  );

  const handleDeleteScope = useCallback(
    async (scopeId: string) => {
      try {
        await deleteScope(scopeId);
        fetchScopes();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to delete scope.");
      }
    },
    [fetchScopes],
  );

  const handleSelectScope = useCallback(
    (scopeId: string) => {
      router.push(`/construction?id=${encodeURIComponent(scopeId)}`);
    },
    [router],
  );

  const filtered = statusFilter
    ? scopes.filter((s) => s.status === statusFilter)
    : scopes;

  const inProgressCount = scopes.filter((s) => s.status === "in_progress").length;
  const plannedCount = scopes.filter((s) => s.status === "planned").length;
  const completedCount = scopes.filter((s) => s.status === "completed").length;

  return (
    <PageContainer
      title="Construction"
      subtitle="Track construction scopes and milestone delivery progress."
      actions={
        <button
          type="button"
          className={styles.addButton}
          onClick={() => setShowCreateModal(true)}
        >
          + Create Scope
        </button>
      }
    >
      {/* KPI summary */}
      <div className={styles.kpiGrid}>
        <MetricCard
          title="Total Scopes"
          value={loading ? "…" : scopes.length}
          subtitle="All statuses"
          icon="🏗️"
        />
        <MetricCard
          title="In Progress"
          value={loading ? "…" : inProgressCount}
          subtitle="Active construction"
          icon="⚙️"
        />
        <MetricCard
          title="Planned"
          value={loading ? "…" : plannedCount}
          subtitle="Upcoming"
          icon="📋"
        />
        <MetricCard
          title="Completed"
          value={loading ? "…" : completedCount}
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
              setStatusFilter(e.target.value as ConstructionStatus | "")
            }
          >
            <option value="">All statuses</option>
            <option value="planned">Planned</option>
            <option value="in_progress">In Progress</option>
            <option value="on_hold">On Hold</option>
            <option value="completed">Completed</option>
          </select>
        </div>
      </div>

      {/* Section header */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Construction Scopes</h2>
        {!loading && (
          <span className={styles.sectionNote}>
            {filtered.length} scope{filtered.length !== 1 ? "s" : ""}
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
        <div className={styles.loadingText}>Loading construction scopes…</div>
      )}

      {/* Table */}
      {!loading && !error && (
        <ConstructionScopesTable
          scopes={filtered}
          onSelectScope={handleSelectScope}
          onDeleteScope={handleDeleteScope}
        />
      )}

      {/* Create Scope modal */}
      {showCreateModal && (
        <CreateScopeModal
          onSubmit={handleCreateScope}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </PageContainer>
  );
}

/**
 * ConstructionDetailPage — loads and displays a single construction scope with milestones.
 */
function ConstructionDetailPage({ scopeId }: { scopeId: string }) {
  const router = useRouter();
  const [scope, setScope] = useState<ConstructionScope | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getScope(scopeId)
      .then((s) => {
        setScope(s);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load scope.");
      })
      .finally(() => setLoading(false));
  }, [scopeId]);

  const handleBack = useCallback(() => {
    router.push("/construction");
  }, [router]);

  return (
    <PageContainer
      title="Construction Scope"
      subtitle="View scope details and manage delivery milestones."
    >
      {loading && (
        <div className={styles.loadingText}>Loading scope…</div>
      )}
      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}
      {!loading && !error && scope && (
        <ScopeDetailView scope={scope} onBack={handleBack} />
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
  const scopeId = searchParams.get("id");

  if (scopeId) {
    return <ConstructionDetailPage scopeId={scopeId} />;
  }
  return <ConstructionList />;
}

/**
 * Construction page — wraps Inner in Suspense as required by useSearchParams.
 */
export default function Page() {
  return (
    <Suspense fallback={null}>
      <Inner />
    </Suspense>
  );
}
