/**
 * ConstructionCostTable — tabular display of construction cost line items.
 *
 * Renders all cost items for a scope with columns for category, description,
 * vendor, budget, committed, actual, variance, cost date, and actions.
 * Supports inline delete and an "Add" flow via the parent.
 */

"use client";

import React, { useCallback, useEffect, useState } from "react";
import {
  listCostItems,
  createCostItem,
  deleteCostItem,
  getScopeCostSummary,
} from "@/lib/construction-api";
import type {
  CostCategory,
  CostType,
  ConstructionCostItem,
  ConstructionCostItemCreate,
  ConstructionCostSummary,
} from "@/lib/construction-types";
import { ConstructionCostSummaryCard } from "./ConstructionCostSummaryCard";
import styles from "@/styles/construction.module.css";

const COST_CATEGORIES: CostCategory[] = [
  "materials",
  "labor",
  "equipment",
  "subcontractor",
  "consultant",
  "permits",
  "utilities",
  "site_overheads",
  "other",
];

const COST_TYPES: CostType[] = ["budget", "commitment", "actual"];

interface ConstructionCostTableProps {
  scopeId: string;
}

function fmt(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  return num.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface AddCostItemFormState {
  cost_category: CostCategory;
  cost_type: CostType;
  description: string;
  vendor_name: string;
  budget_amount: string;
  committed_amount: string;
  actual_amount: string;
  currency: string;
  cost_date: string;
  notes: string;
}

const EMPTY_FORM: AddCostItemFormState = {
  cost_category: "materials",
  cost_type: "budget",
  description: "",
  vendor_name: "",
  budget_amount: "",
  committed_amount: "",
  actual_amount: "",
  currency: "AED",
  cost_date: "",
  notes: "",
};

export function ConstructionCostTable({ scopeId }: ConstructionCostTableProps) {
  const [items, setItems] = useState<ConstructionCostItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("");

  const [summary, setSummary] = useState<ConstructionCostSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);

  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState<AddCostItemFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const fetchItems = useCallback(() => {
    setLoading(true);
    listCostItems(scopeId, { category: categoryFilter || undefined })
      .then((resp) => {
        setItems(resp.items);
        setTotal(resp.total);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load cost items.");
      })
      .finally(() => setLoading(false));
  }, [scopeId, categoryFilter]);

  const fetchSummary = useCallback(() => {
    setSummaryLoading(true);
    getScopeCostSummary(scopeId)
      .then((data) => setSummary(data))
      .catch(() => setSummary(null))
      .finally(() => setSummaryLoading(false));
  }, [scopeId]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  useEffect(() => {
    fetchSummary();
  }, [fetchSummary]);

  const handleDeleteItem = useCallback(
    async (itemId: string) => {
      try {
        await deleteCostItem(itemId);
        fetchItems();
        fetchSummary();
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Failed to delete cost item.");
      }
    },
    [fetchItems, fetchSummary],
  );

  const handleFormChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
    >,
  ) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    const budget = parseFloat(form.budget_amount) || 0;
    const committed = parseFloat(form.committed_amount) || 0;
    const actual = parseFloat(form.actual_amount) || 0;

    if (budget === 0 && committed === 0 && actual === 0) {
      setFormError("At least one amount (budget, committed, or actual) must be non-zero.");
      return;
    }

    const payload: ConstructionCostItemCreate = {
      cost_category: form.cost_category,
      cost_type: form.cost_type,
      description: form.description.trim(),
      vendor_name: form.vendor_name.trim() || null,
      budget_amount: budget,
      committed_amount: committed,
      actual_amount: actual,
      currency: form.currency.trim() || "AED",
      cost_date: form.cost_date || null,
      notes: form.notes.trim() || null,
    };

    setSubmitting(true);
    try {
      await createCostItem(scopeId, payload);
      setForm(EMPTY_FORM);
      setShowAddForm(false);
      fetchItems();
      fetchSummary();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to create cost item.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      {/* Summary card */}
      {!summaryLoading && summary && (
        <ConstructionCostSummaryCard
          summary={summary}
          currency={items[0]?.currency ?? "AED"}
        />
      )}

      {/* Toolbar */}
      <div className={styles.sectionHeader}>
        <h2 className={styles.sectionTitle}>
          Cost Items{total > 0 ? ` (${total})` : ""}
        </h2>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <select
            className={styles.filterSelect}
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
            aria-label="Filter by category"
          >
            <option value="">All Categories</option>
            {COST_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, " ")}
              </option>
            ))}
          </select>
          <button
            type="button"
            className={styles.addButton}
            onClick={() => {
              setShowAddForm(true);
              setFormError(null);
            }}
          >
            + Add Cost Item
          </button>
        </div>
      </div>

      {error && (
        <div className={styles.errorBanner} role="alert">
          {error}
        </div>
      )}

      {loading && (
        <div className={styles.loadingText}>Loading cost items…</div>
      )}

      {/* Items table */}
      {!loading && (
        <div className={styles.tableWrapper}>
          {items.length === 0 ? (
            <p className={styles.emptyState}>
              No cost items yet.{" "}
              {categoryFilter
                ? "Try clearing the category filter."
                : "Add the first one to start tracking costs."}
            </p>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th className={styles.th}>Category</th>
                  <th className={styles.th}>Type</th>
                  <th className={styles.th}>Description</th>
                  <th className={styles.th}>Vendor</th>
                  <th className={styles.th}>Budget</th>
                  <th className={styles.th}>Committed</th>
                  <th className={styles.th}>Actual</th>
                  <th className={styles.th}>Var. (Budget)</th>
                  <th className={styles.th}>Date</th>
                  <th className={styles.th}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const varBudget = parseFloat(item.variance_to_budget);
                  return (
                    <tr key={item.id} className={styles.tr}>
                      <td className={styles.td}>
                        {item.cost_category.replace(/_/g, " ")}
                      </td>
                      <td className={styles.td}>{item.cost_type}</td>
                      <td className={styles.td}>{item.description}</td>
                      <td className={styles.td}>{item.vendor_name ?? "—"}</td>
                      <td className={styles.td}>{fmt(item.budget_amount)}</td>
                      <td className={styles.td}>{fmt(item.committed_amount)}</td>
                      <td className={styles.td}>{fmt(item.actual_amount)}</td>
                      <td
                        className={`${styles.td} ${
                          varBudget > 0
                            ? styles.varianceOver
                            : varBudget < 0
                              ? styles.varianceUnder
                              : ""
                        }`}
                      >
                        {fmt(item.variance_to_budget)}
                      </td>
                      <td className={styles.td}>
                        {item.cost_date ?? "—"}
                      </td>
                      <td className={styles.td}>
                        <button
                          type="button"
                          className={styles.deleteButton}
                          onClick={() => handleDeleteItem(item.id)}
                          aria-label={`Delete cost item ${item.description}`}
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Add cost item modal */}
      {showAddForm && (
        <div className={styles.modalOverlay}>
          <div className={styles.modal}>
            <h3 className={styles.modalTitle}>Add Cost Item</h3>
            {formError && (
              <div className={styles.errorBanner} role="alert">
                {formError}
              </div>
            )}
            <form onSubmit={handleAddSubmit} className={styles.form}>
              <div className={styles.formRow}>
                <label className={styles.formLabel}>
                  Category
                  <select
                    name="cost_category"
                    className={styles.formInput}
                    value={form.cost_category}
                    onChange={handleFormChange}
                    required
                  >
                    {COST_CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </label>
                <label className={styles.formLabel}>
                  Type
                  <select
                    name="cost_type"
                    className={styles.formInput}
                    value={form.cost_type}
                    onChange={handleFormChange}
                    required
                  >
                    {COST_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label className={styles.formLabel}>
                Description *
                <input
                  name="description"
                  type="text"
                  className={styles.formInput}
                  value={form.description}
                  onChange={handleFormChange}
                  required
                  maxLength={500}
                />
              </label>

              <label className={styles.formLabel}>
                Vendor Name
                <input
                  name="vendor_name"
                  type="text"
                  className={styles.formInput}
                  value={form.vendor_name}
                  onChange={handleFormChange}
                  maxLength={255}
                />
              </label>

              <div className={styles.formRow}>
                <label className={styles.formLabel}>
                  Budget Amount
                  <input
                    name="budget_amount"
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.formInput}
                    value={form.budget_amount}
                    onChange={handleFormChange}
                  />
                </label>
                <label className={styles.formLabel}>
                  Committed Amount
                  <input
                    name="committed_amount"
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.formInput}
                    value={form.committed_amount}
                    onChange={handleFormChange}
                  />
                </label>
                <label className={styles.formLabel}>
                  Actual Amount
                  <input
                    name="actual_amount"
                    type="number"
                    min="0"
                    step="0.01"
                    className={styles.formInput}
                    value={form.actual_amount}
                    onChange={handleFormChange}
                  />
                </label>
              </div>

              <div className={styles.formRow}>
                <label className={styles.formLabel}>
                  Currency
                  <input
                    name="currency"
                    type="text"
                    className={styles.formInput}
                    value={form.currency}
                    onChange={handleFormChange}
                    maxLength={10}
                  />
                </label>
                <label className={styles.formLabel}>
                  Cost Date
                  <input
                    name="cost_date"
                    type="date"
                    className={styles.formInput}
                    value={form.cost_date}
                    onChange={handleFormChange}
                  />
                </label>
              </div>

              <label className={styles.formLabel}>
                Notes
                <textarea
                  name="notes"
                  className={styles.formInput}
                  value={form.notes}
                  onChange={handleFormChange}
                  rows={2}
                />
              </label>

              <div className={styles.modalActions}>
                <button
                  type="button"
                  className={styles.cancelButton}
                  onClick={() => {
                    setShowAddForm(false);
                    setForm(EMPTY_FORM);
                    setFormError(null);
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.submitButton}
                  disabled={submitting}
                >
                  {submitting ? "Saving…" : "Add Cost Item"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
