"use client";

import React, { useEffect, useState } from "react";
import type {
  ProjectAttributeDefinition,
  ProjectAttributeOption,
} from "@/lib/projects-types";
import {
  createAttributeDefinition,
  createAttributeOption,
  listAttributeDefinitions,
  updateAttributeDefinition,
  updateAttributeOption,
} from "@/lib/projects-api";
import { ApiError } from "@/lib/api-client";
import styles from "@/styles/projects.module.css";

interface ProjectAttributeConfigProps {
  projectId: string;
}

/**
 * ProjectAttributeConfig
 *
 * Displays the project-level attribute definition engine for a single project.
 * For PR-032, the supported attribute type is `view_type`.
 *
 * Features:
 *   - List existing view type options for the project
 *   - Add a new view option (label + value)
 *   - Edit an option's label
 *   - Deactivate an option
 */
export function ProjectAttributeConfig({
  projectId,
}: ProjectAttributeConfigProps) {
  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  const [definition, setDefinition] =
    useState<ProjectAttributeDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add option form state
  const [addValue, setAddValue] = useState("");
  const [addLabel, setAddLabel] = useState("");
  const [addError, setAddError] = useState<string | null>(null);
  const [addSaving, setAddSaving] = useState(false);

  // Edit option state
  const [editingOption, setEditingOption] =
    useState<ProjectAttributeOption | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editError, setEditError] = useState<string | null>(null);
  const [editSaving, setEditSaving] = useState(false);

  // -----------------------------------------------------------------------
  // Data loading
  // -----------------------------------------------------------------------

  const loadDefinitions = () => {
    setLoading(true);
    setError(null);
    listAttributeDefinitions(projectId)
      .then((resp) => {
        // Find the view_type definition if it exists
        const found = resp.items.find((d) => d.key === "view_type") ?? null;
        setDefinition(found);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error ? err.message : "Failed to load attribute definitions."
        );
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDefinitions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // -----------------------------------------------------------------------
  // Ensure view_type definition exists (create on first use)
  // -----------------------------------------------------------------------

  const ensureDefinition = async (): Promise<ProjectAttributeDefinition> => {
    if (definition) return definition;
    const created = await createAttributeDefinition(projectId, {
      key: "view_type",
      label: "View Type",
    });
    setDefinition(created);
    return created;
  };

  // -----------------------------------------------------------------------
  // Add option
  // -----------------------------------------------------------------------

  const handleAddOption = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addValue.trim() || !addLabel.trim()) return;
    setAddSaving(true);
    setAddError(null);
    try {
      const defn = await ensureDefinition();
      const option = await createAttributeOption(projectId, defn.id, {
        value: addValue.trim(),
        label: addLabel.trim(),
      });
      setDefinition((prev) => {
        if (!prev) return defn ? { ...defn, options: [option] } : null;
        return { ...prev, options: [...prev.options, option] };
      });
      setAddValue("");
      setAddLabel("");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setAddError(err.message);
      } else {
        setAddError("Failed to add option.");
      }
    } finally {
      setAddSaving(false);
    }
  };

  // -----------------------------------------------------------------------
  // Edit option
  // -----------------------------------------------------------------------

  const openEdit = (option: ProjectAttributeOption) => {
    setEditingOption(option);
    setEditLabel(option.label);
    setEditError(null);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingOption || !definition) return;
    setEditSaving(true);
    setEditError(null);
    try {
      const updated = await updateAttributeOption(
        projectId,
        definition.id,
        editingOption.id,
        { label: editLabel.trim() }
      );
      setDefinition((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          options: prev.options.map((o) =>
            o.id === updated.id ? updated : o
          ),
        };
      });
      setEditingOption(null);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setEditError(err.message);
      } else {
        setEditError("Failed to update option.");
      }
    } finally {
      setEditSaving(false);
    }
  };

  // -----------------------------------------------------------------------
  // Deactivate option
  // -----------------------------------------------------------------------

  const handleDeactivate = async (option: ProjectAttributeOption) => {
    if (!definition) return;
    try {
      const updated = await updateAttributeOption(
        projectId,
        definition.id,
        option.id,
        { is_active: false }
      );
      setDefinition((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          options: prev.options.map((o) =>
            o.id === updated.id ? updated : o
          ),
        };
      });
    } catch {
      // Surface error inline if needed — for now silently reload
      loadDefinitions();
    }
  };

  // -----------------------------------------------------------------------
  // Reactivate option
  // -----------------------------------------------------------------------

  const handleReactivate = async (option: ProjectAttributeOption) => {
    if (!definition) return;
    try {
      const updated = await updateAttributeOption(
        projectId,
        definition.id,
        option.id,
        { is_active: true }
      );
      setDefinition((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          options: prev.options.map((o) =>
            o.id === updated.id ? updated : o
          ),
        };
      });
    } catch {
      loadDefinitions();
    }
  };

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  if (loading) {
    return <div className={styles.loadingText}>Loading attribute configuration…</div>;
  }

  if (error) {
    return (
      <div className={styles.modalError} role="alert">
        {error}
      </div>
    );
  }

  const options = definition?.options ?? [];
  const activeOptions = options.filter((o) => o.is_active);
  const inactiveOptions = options.filter((o) => !o.is_active);

  return (
    <div>
      {/* Header */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>Premium Attributes</h2>
        <span className={styles.sectionNote}>
          Define the selectable attribute values available to units in this project.
        </span>
      </div>

      {/* View Type card */}
      <div
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--card-radius)",
          boxShadow: "var(--card-shadow)",
          padding: "var(--card-padding)",
          marginBottom: "var(--space-6)",
        }}
      >
        <h3
          style={{
            fontSize: "var(--font-size-md)",
            fontWeight: "var(--font-weight-semibold)",
            marginBottom: "var(--space-4)",
            color: "var(--color-text)",
          }}
        >
          View Type Options
        </h3>

        {/* Active options table */}
        {activeOptions.length > 0 ? (
          <div className={styles.tableWrapper} style={{ marginBottom: "var(--space-6)" }}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>Label</th>
                  <th>Value</th>
                  <th style={{ width: 120 }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {activeOptions.map((option) => (
                  <tr key={option.id}>
                    <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                      {option.label}
                    </td>
                    <td
                      style={{
                        padding: "var(--space-3) var(--space-4)",
                        color: "var(--color-text-muted)",
                        fontFamily: "monospace",
                        fontSize: "var(--font-size-xs, 0.75rem)",
                      }}
                    >
                      {option.value}
                    </td>
                    <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <button
                          type="button"
                          className={styles.actionButton}
                          onClick={() => openEdit(option)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className={`${styles.actionButton} ${styles.actionButtonDanger}`}
                          onClick={() => handleDeactivate(option)}
                        >
                          Deactivate
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className={styles.emptyState} style={{ marginBottom: "var(--space-6)" }}>
            No active view options yet. Add one below.
          </div>
        )}

        {/* Add option form */}
        <form onSubmit={handleAddOption}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr auto",
              gap: "var(--space-3)",
              alignItems: "flex-end",
            }}
          >
            <div className={styles.formField}>
              <label className={styles.formLabel} htmlFor="attr-label">
                Label
              </label>
              <input
                id="attr-label"
                className={styles.formInput}
                type="text"
                placeholder="e.g. Sea View"
                value={addLabel}
                onChange={(e) => setAddLabel(e.target.value)}
                disabled={addSaving}
                required
              />
            </div>
            <div className={styles.formField}>
              <label className={styles.formLabel} htmlFor="attr-value">
                Value (key)
              </label>
              <input
                id="attr-value"
                className={styles.formInput}
                type="text"
                placeholder="e.g. sea_view"
                value={addValue}
                onChange={(e) => setAddValue(e.target.value)}
                disabled={addSaving}
                required
              />
            </div>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={addSaving || !addLabel.trim() || !addValue.trim()}
            >
              {addSaving ? "Adding…" : "Add Option"}
            </button>
          </div>
          {addError && (
            <div
              className={styles.modalError}
              role="alert"
              style={{ marginTop: "var(--space-3)" }}
            >
              {addError}
            </div>
          )}
        </form>

        {/* Inactive options (collapsed) */}
        {inactiveOptions.length > 0 && (
          <details style={{ marginTop: "var(--space-6)" }}>
            <summary
              style={{
                cursor: "pointer",
                fontSize: "var(--font-size-sm)",
                color: "var(--color-text-muted)",
              }}
            >
              Inactive options ({inactiveOptions.length})
            </summary>
            <div className={styles.tableWrapper} style={{ marginTop: "var(--space-3)" }}>
              <table className={styles.table}>
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Value</th>
                    <th style={{ width: 120 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {inactiveOptions.map((option) => (
                    <tr
                      key={option.id}
                      style={{ opacity: 0.6 }}
                    >
                      <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                        {option.label}
                      </td>
                      <td
                        style={{
                          padding: "var(--space-3) var(--space-4)",
                          fontFamily: "monospace",
                          fontSize: "var(--font-size-xs, 0.75rem)",
                        }}
                      >
                        {option.value}
                      </td>
                      <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                        <button
                          type="button"
                          className={styles.actionButton}
                          onClick={() => handleReactivate(option)}
                        >
                          Reactivate
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </div>

      {/* Edit option modal */}
      {editingOption && (
        <div className={styles.modalOverlay} role="dialog" aria-modal="true">
          <div className={styles.modal}>
            <h2 className={styles.modalTitle}>Edit View Option</h2>
            <form className={styles.modalForm} onSubmit={handleSaveEdit}>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="edit-label">
                  Label
                </label>
                <input
                  id="edit-label"
                  className={styles.formInput}
                  type="text"
                  value={editLabel}
                  onChange={(e) => setEditLabel(e.target.value)}
                  disabled={editSaving}
                  required
                />
              </div>
              {editError && (
                <div className={styles.modalError} role="alert">
                  {editError}
                </div>
              )}
              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.cancelButton}
                  onClick={() => {
                    setEditingOption(null);
                    setEditError(null);
                  }}
                  disabled={editSaving}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.submitButton}
                  disabled={editSaving || !editLabel.trim()}
                >
                  {editSaving ? "Saving…" : "Save"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
