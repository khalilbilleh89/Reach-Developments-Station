"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/api/client";
import { workspace } from "@/lib/api/workspace";
import type { SavedView, ViewFilters } from "@/lib/api/workspace";

import { Button } from "./Button";
import { Icon } from "./Icon";
import { PromptDialog } from "./PromptDialog";
import { RowMenu } from "./RowMenu";
import { useToast } from "./Toast";

/**
 * The views a person has saved on this register (design system F3), as a strip
 * of chips under the toolbar: the pressed one is the view on screen, "Save
 * view" keeps the current filters and sort under a name, and each chip's menu
 * pins, renames or removes it. Views live on the server, per person, so they
 * follow the person between browsers.
 *
 * A view holds the register's filter state and sort, nothing from the rows.
 */
export function SavedViews({ screen, filters, sort, onApply }: {
  screen: string;
  /** The register's current filter state, as it would be saved. */
  filters: ViewFilters;
  sort: string | null;
  /** Put a saved view's filters and sort on the register. */
  onApply: (filters: ViewFilters, sort: string | null) => void;
}) {
  const [views, setViews] = useState<SavedView[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [renaming, setRenaming] = useState<SavedView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    let live = true;
    void (async () => {
      try {
        const rows = await workspace.listViews(screen);
        if (live) setViews(rows);
      } catch {
        if (live) setViews([]);
      }
    })();
    return () => {
      live = false;
    };
  }, [screen]);

  const current = views?.find((view) => sameState(view, filters, sort)) ?? null;

  const save = async (name: string) => {
    setBusy(true);
    setError(null);
    try {
      const created = await workspace.createView({ screen, name, filters, sort });
      setViews((rows) => [...(rows ?? []), created]);
      setSaving(false);
      toast({ title: `View “${created.name}” saved` });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the view.");
    } finally {
      setBusy(false);
    }
  };

  const rename = async (view: SavedView, name: string) => {
    setBusy(true);
    setError(null);
    try {
      const updated = await workspace.updateView(view.id, { name });
      setViews((rows) => (rows ?? []).map((row) => (row.id === updated.id ? updated : row)));
      setRenaming(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not rename the view.");
    } finally {
      setBusy(false);
    }
  };

  const pin = async (view: SavedView) => {
    try {
      const updated = await workspace.updateView(view.id, { pinned: !view.pinned });
      setViews((rows) => (rows ?? []).map((row) => (row.id === updated.id ? updated : row)));
    } catch (caught) {
      toast({ title: caught instanceof ApiError ? caught.message : "Could not pin the view.", tone: "error" });
    }
  };

  const removeView = async (view: SavedView) => {
    try {
      await workspace.deleteView(view.id);
      setViews((rows) => (rows ?? []).filter((row) => row.id !== view.id));
      toast({ title: `View “${view.name}” removed` });
    } catch (caught) {
      toast({ title: caught instanceof ApiError ? caught.message : "Could not remove the view.", tone: "error" });
    }
  };

  const ordered = [...(views ?? [])].sort((a, b) => Number(b.pinned) - Number(a.pinned) || a.name.localeCompare(b.name));

  return (
    <div className="saved-views" aria-label="Saved views">
      {ordered.length ? <span className="saved-views-label">Saved views</span> : null}
      {ordered.map((view) => (
        <span key={view.id} className={current?.id === view.id ? "saved-view saved-view-active" : "saved-view"}>
          <button type="button" className="saved-view-apply" aria-pressed={current?.id === view.id} onClick={() => onApply(view.filters, view.sort)}>
            {view.pinned ? <Icon name="pin" /> : null}
            {view.name}
          </button>
          <RowMenu label={`Actions for view ${view.name}`}>
            <button type="button" onClick={() => void pin(view)}>{view.pinned ? "Unpin" : "Pin"}</button>
            <button type="button" onClick={() => { setError(null); setRenaming(view); }}>Rename</button>
            <button type="button" onClick={() => void removeView(view)}>Remove</button>
          </RowMenu>
        </span>
      ))}
      <Button small variant="quiet" disabled={!!current} onClick={() => { setError(null); setSaving(true); }}>
        <Icon name="plus" /> Save view
      </Button>
      {saving ? (
        <PromptDialog
          title="Save this view"
          description="The current filters and sort, kept under a name on this register for you."
          label="View name"
          confirmLabel="Save view"
          busy={busy}
          error={error}
          onSubmit={(name) => void save(name)}
          onCancel={() => setSaving(false)}
        />
      ) : null}
      {renaming ? (
        <PromptDialog
          title={`Rename “${renaming.name}”`}
          label="View name"
          confirmLabel="Rename"
          busy={busy}
          error={error}
          onSubmit={(name) => void rename(renaming, name)}
          onCancel={() => setRenaming(null)}
        />
      ) : null}
    </div>
  );
}

function sameState(view: SavedView, filters: ViewFilters, sort: string | null): boolean {
  if ((view.sort ?? null) !== (sort ?? null)) return false;
  const keys = new Set([...Object.keys(view.filters), ...Object.keys(filters)]);
  for (const key of keys) {
    if ((view.filters[key] ?? "") !== (filters[key] ?? "")) return false;
  }
  return true;
}
