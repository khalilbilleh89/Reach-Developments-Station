"use client";

import React, { useState } from "react";
import type { ProjectCreate, ProjectStatus } from "@/lib/projects-types";
import styles from "@/styles/projects.module.css";

interface CreateProjectModalProps {
  onSubmit: (data: ProjectCreate) => Promise<void>;
  onClose: () => void;
}

const STATUS_OPTIONS: { value: ProjectStatus; label: string }[] = [
  { value: "pipeline", label: "Pipeline" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "on_hold", label: "On Hold" },
];

/**
 * CreateProjectModal — modal form for creating a new project.
 *
 * Used by the Projects page header action and empty-state CTA.
 * Both entry points open this same modal to keep the create workflow DRY.
 */
export function CreateProjectModal({
  onSubmit,
  onClose,
}: CreateProjectModalProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [developerName, setDeveloperName] = useState("");
  const [location, setLocation] = useState("");
  const [status, setStatus] = useState<ProjectStatus>("pipeline");
  const [startDate, setStartDate] = useState("");
  const [targetEndDate, setTargetEndDate] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Project name is required.");
      return;
    }
    if (!code.trim()) {
      setError("Project code is required.");
      return;
    }

    const payload: ProjectCreate = {
      name: name.trim(),
      code: code.trim(),
      developer_name: developerName.trim() || null,
      location: location.trim() || null,
      status,
      start_date: startDate || null,
      target_end_date: targetEndDate || null,
      description: description.trim() || null,
    };

    setSubmitting(true);
    try {
      await onSubmit(payload);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className={styles.modalOverlay}
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-project-modal-title"
    >
      <div className={styles.modal}>
        <h2 id="create-project-modal-title" className={styles.modalTitle}>
          Create Project
        </h2>

        <form className={styles.modalForm} onSubmit={handleSubmit} noValidate>
          {error && (
            <div className={styles.modalError} role="alert">
              {error}
            </div>
          )}

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="project-name" className={styles.formLabel}>
                Project Name <span aria-hidden="true">*</span>
              </label>
              <input
                id="project-name"
                type="text"
                className={styles.formInput}
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={255}
                required
                autoFocus
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="project-code" className={styles.formLabel}>
                Code <span aria-hidden="true">*</span>
              </label>
              <input
                id="project-code"
                type="text"
                className={styles.formInput}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                maxLength={100}
                placeholder="e.g. PROJ-01"
                required
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="project-developer" className={styles.formLabel}>
                Developer Name
              </label>
              <input
                id="project-developer"
                type="text"
                className={styles.formInput}
                value={developerName}
                onChange={(e) => setDeveloperName(e.target.value)}
                maxLength={255}
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="project-location" className={styles.formLabel}>
                Location
              </label>
              <input
                id="project-location"
                type="text"
                className={styles.formInput}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                maxLength={255}
              />
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="project-status" className={styles.formLabel}>
                Status
              </label>
              <select
                id="project-status"
                className={styles.formSelect}
                value={status}
                onChange={(e) => setStatus(e.target.value as ProjectStatus)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.formRow}>
            <div className={styles.formField}>
              <label htmlFor="project-start" className={styles.formLabel}>
                Start Date
              </label>
              <input
                id="project-start"
                type="date"
                className={styles.formInput}
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>

            <div className={styles.formField}>
              <label htmlFor="project-end" className={styles.formLabel}>
                Target Completion
              </label>
              <input
                id="project-end"
                type="date"
                className={styles.formInput}
                value={targetEndDate}
                onChange={(e) => setTargetEndDate(e.target.value)}
              />
            </div>
          </div>

          <div className={styles.formField}>
            <label htmlFor="project-description" className={styles.formLabel}>
              Description
            </label>
            <textarea
              id="project-description"
              className={styles.formTextarea}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Optional description of this project…"
            />
          </div>

          <div className={styles.modalActions}>
            <button
              type="button"
              className={styles.cancelButton}
              onClick={onClose}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={submitting}
            >
              {submitting ? "Creating…" : "Create Project"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
