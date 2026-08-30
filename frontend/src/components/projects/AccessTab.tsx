"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, users } from "@/lib/api";
import type { AdminUser, ProjectAccess } from "@/lib/api";
import {
  Badge,
  Button,
  EmptyState,
  Field,
  Loading,
  Notice,
  Panel,
  TableScroll,
} from "@/components/ui";
import { PhaseAccessEditor } from "@/components/projects/inventory/PhaseAccessEditor";

/**
 * Project membership administration. System Administrator only.
 *
 * Access is security administration, not ordinary project editing, so this tab
 * is not shown to anyone else and the API refuses it independently.
 */
export function AccessTab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<ProjectAccess[] | null>(null);
  const [candidates, setCandidates] = useState<AdminUser[]>([]);
  const [chosen, setChosen] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scopeFor, setScopeFor] = useState<ProjectAccess | null>(null);

  const load = useCallback(async () => {
    try {
      setRows(await projects.access(projectId));
      setError(null);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load project access.");
    }
  }, [projectId]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      try {
        setCandidates((await users.list()).items.filter((user) => user.is_active));
      } catch {
        // Only the grant control needs the directory.
      }
    })();
  }, []);

  const act = async (userId: string, isActive: boolean) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await projects.setAccess(projectId, userId, isActive);
      setNotice(isActive ? "Access granted." : "Access revoked.");
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change access.");
    } finally {
      setBusy(false);
    }
  };

  const grant = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!chosen) return;
    await act(chosen, true);
    setChosen("");
  };

  const members = new Set((rows ?? []).map((row) => row.user_id));

  return (
    <Panel
      title="Access"
      description="Who may open this project. Roles decide what they can do once inside."
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <form className="form-inline" onSubmit={grant}>
        <Field label="Add someone">
          <select
            className="input"
            value={chosen}
            onChange={(event) => setChosen(event.target.value)}
          >
            <option value="">Choose a user…</option>
            {candidates
              .filter((user) => !members.has(user.id))
              .map((user) => (
                <option key={user.id} value={user.id}>
                  {user.display_name} — {user.email}
                </option>
              ))}
          </select>
        </Field>
        <Button variant="primary" type="submit" disabled={busy || !chosen}>
          Grant access
        </Button>
      </form>

      {rows === null ? (
        <Loading label="Loading access…" />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No one has been added yet"
          hint="System Administrators reach every project without a membership row."
        />
      ) : (
        <TableScroll label="Project membership">
            <thead>
              <tr>
                <th scope="col">User</th>
                <th scope="col">Email</th>
                <th scope="col">Roles</th>
                <th scope="col">Access</th>
                <th scope="col">Inventory scope</th>
                <th scope="col">Granted</th>
                <th scope="col">Revoked</th>
                <th scope="col">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row">{row.display_name}</th>
                  <td>{row.email}</td>
                  <td className="chip-list">
                    {row.role_keys.map((key) => (
                      <span className="chip" key={key}>
                        {key}
                      </span>
                    ))}
                  </td>
                  <td>
                    {row.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Revoked</Badge>
                    )}
                  </td>
                  <td>
                    {row.phase_scope === "selected" ? (
                      <Badge tone="neutral">Selected phases</Badge>
                    ) : (
                      <span className="subtle">All phases</span>
                    )}
                  </td>
                  <td className="nowrap">{row.granted_at.slice(0, 10)}</td>
                  <td className="nowrap">{row.revoked_at?.slice(0, 10) ?? "—"}</td>
                  <td className="chip-list">
                    <Button
                      small
                      disabled={busy}
                      onClick={() => void act(row.user_id, !row.is_active)}
                    >
                      {row.is_active ? "Revoke" : "Restore"}
                    </Button>
                    <Button
                      small
                      onClick={() =>
                        setScopeFor(scopeFor?.user_id === row.user_id ? null : row)
                      }
                    >
                      {scopeFor?.user_id === row.user_id ? "Close phases" : "Phases"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
</TableScroll>
      )}

      {scopeFor ? (
        <PhaseAccessEditor
          projectId={projectId}
          userId={scopeFor.user_id}
          displayName={scopeFor.display_name}
          phaseScope={scopeFor.phase_scope}
          onScopeChanged={async () => {
            const refreshed = await projects.access(projectId);
            setRows(refreshed);
            setScopeFor(
              refreshed.find((entry) => entry.user_id === scopeFor.user_id) ?? null,
            );
          }}
        />
      ) : null}
    </Panel>
  );
}
