"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory } from "@/lib/api";
import type { Phase, PhaseAccess } from "@/lib/api";
import { Button, Loading, Notice, StatusDot, TableScroll } from "@/components/ui";

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
    <div className="stack stack-tight">
      {error ? <Notice tone="error">{error}</Notice> : null}

      <div className="segmented" role="group" aria-label={`Inventory scope for ${displayName}`}>
        <button
          type="button"
          className="segment"
          aria-pressed={phaseScope === "all"}
          disabled={busy}
          onClick={() => phaseScope !== "all" && void setScope("all")}
        >
          All phases
        </button>
        <button
          type="button"
          className="segment"
          aria-pressed={phaseScope === "selected"}
          disabled={busy}
          onClick={() => phaseScope !== "selected" && void setScope("selected")}
        >
          Selected phases only
        </button>
      </div>

      {phaseScope === "all" ? (
        <p className="footnote">
          This person sees every phase, including phases added later. Phase grants below are kept
          but not applied while the scope is “all”.
        </p>
      ) : activeCount === 0 ? (
        <Notice tone="warning">
          Narrowed to selected phases with none granted, so this person sees no units at all.
        </Notice>
      ) : null}

      {phases === null ? (
        <Loading label="Loading phases…" lines={3} />
      ) : phases.length === 0 ? (
        <p className="footnote">This project has no phases yet.</p>
      ) : (
        <TableScroll label="Phase access" compact>
          <thead>
            <tr>
              <th scope="col">Phase</th>
              <th scope="col">Name</th>
              <th scope="col">Access</th>
              <th scope="col">
                <span className="visually-hidden">Action</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {phases.map((phase) => {
              const row = granted.find((entry) => entry.phase_id === phase.id);
              const isActive = row?.is_active ?? false;
              return (
                <tr key={phase.id}>
                  <th scope="row" className="mono">
                    {phase.code}
                  </th>
                  <td>{phase.name}</td>
                  <td>
                    {isActive ? (
                      <StatusDot tone="success">Granted</StatusDot>
                    ) : (
                      <StatusDot tone="muted">Not granted</StatusDot>
                    )}
                  </td>
                  <td>
                    <Button
                      small
                      variant="quiet"
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
