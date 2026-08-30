"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { Phase, PhaseAccess } from "@/lib/api";
import { Badge, Button, Loading, Notice, TableScroll } from "@/components/ui";

/**
 * Which phases one member of a project may see.
 *
 * Two questions, in the order an administrator asks them: does this person see
 * the whole development, and if not, which phases. Narrowing to "selected"
 * without granting a phase is a real state and shows as such — an empty
 * inventory is the honest consequence, not a bug to paper over.
 */
export function PhaseAccessEditor({
  projectId,
  userId,
  displayName,
  phaseScope,
  onScopeChanged,
}: {
  projectId: string;
  userId: string;
  displayName: string;
  phaseScope: string;
  onScopeChanged: () => Promise<void>;
}) {
  const [phases, setPhases] = useState<Phase[] | null>(null);
  const [granted, setGranted] = useState<PhaseAccess[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [phaseList, accessList] = await Promise.all([
        inventory.phases(projectId),
        inventory.phaseAccess(projectId, userId),
      ]);
      setPhases(phaseList);
      setGranted(accessList);
      setError(null);
    } catch (caught) {
      setPhases([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load phase access.");
    }
  }, [projectId, userId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  const setScope = async (scope: "all" | "selected") => {
    setBusy(true);
    setError(null);
    try {
      await inventory.phaseScope(projectId, userId, scope);
      await onScopeChanged();
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change the scope.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (phaseId: string, isActive: boolean, exists: boolean) => {
    setBusy(true);
    setError(null);
    try {
      if (exists) {
        await inventory.setPhaseAccess(projectId, userId, phaseId, isActive);
      } else {
        await inventory.grantPhaseAccess(projectId, userId, phaseId);
      }
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change phase access.");
    } finally {
      setBusy(false);
    }
  };

  const activeCount = granted.filter((row) => row.is_active).length;

  return (
    <div>
      <h3 className="section-heading">Inventory scope — {displayName}</h3>
      {error ? <Notice tone="error">{error}</Notice> : null}

      <div className="chip-list">
        <button
          className={`button button-small ${phaseScope === "all" ? "button-primary" : ""}`}
          type="button"
          disabled={busy || phaseScope === "all"}
          onClick={() => void setScope("all")}
        >
          All phases
        </button>
        <button
          className={`button button-small ${phaseScope === "selected" ? "button-primary" : ""}`}
          type="button"
          disabled={busy || phaseScope === "selected"}
          onClick={() => void setScope("selected")}
        >
          Selected phases only
        </button>
      </div>

      {phaseScope === "all" ? (
        <p className="subtle">
          This person sees every phase, including phases added later. Phase grants below are kept
          but not applied while the scope is “all”.
        </p>
      ) : activeCount === 0 ? (
        <Notice tone="info">
          Narrowed to selected phases with none granted, so this person sees no units at all.
        </Notice>
      ) : null}

      {phases === null ? (
        <Loading label="Loading phases…" />
      ) : phases.length === 0 ? (
        <p className="subtle">This project has no phases yet.</p>
      ) : (
        <TableScroll label="Phase access">
            <thead>
              <tr>
                <th scope="col">Phase</th>
                <th scope="col">Name</th>
                <th scope="col">Access</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {phases.map((phase) => {
                const row = granted.find((entry) => entry.phase_id === phase.id);
                const isActive = row?.is_active ?? false;
                return (
                  <tr key={phase.id}>
                    <th scope="row">{phase.code}</th>
                    <td>{phase.name}</td>
                    <td>
                      {isActive ? (
                        <Badge tone="success">Granted</Badge>
                      ) : (
                        <Badge tone="muted">Not granted</Badge>
                      )}
                    </td>
                    <td>
                      <Button
                        small
                        disabled={busy}
                        onClick={() => void toggle(phase.id, !isActive, row !== undefined)}
                      >
                        {isActive ? "Revoke" : "Grant"}
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
</TableScroll>
      )}
    </div>
  );
}
