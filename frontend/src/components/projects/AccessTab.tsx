"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, projects, users } from "@/lib/api";
import type { AdminUser, ProjectAccess, Role } from "@/lib/api";
import { sectionDescription } from "@/components/shell/navigation";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  Loading,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
} from "@/components/ui";
import { PhaseAccessEditor } from "@/components/projects/inventory/PhaseAccessEditor";

/**
 * Project membership. System Administrator only.
 *
 * Access is security administration, not ordinary project editing, so this
 * section is not offered to anyone else and the API refuses it independently.
 * The register answers the governance question in one line per person: who,
 * with which roles, whether they may open the project, and how much of its
 * inventory they can see.
 */
export function AccessTab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<ProjectAccess[] | null>(null);
  const [candidates, setCandidates] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
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
      // Two independent reads: the directory feeds the grant control and the
      // role list only labels the register, so one failing must not take the
      // other with it. The roles fall back to their keys.
      const [page, roleList] = await Promise.allSettled([users.list(), users.roles()]);
      if (page.status === "fulfilled") setCandidates(page.value.items.filter((user) => user.is_active));
      if (roleList.status === "fulfilled") setRoles(roleList.value);
    })();
  }, []);

  const roleLabel = (key: string) => roles.find((role) => role.key === key)?.label ?? key;

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
    <>
      <PageHeader title="Access" subtitle={sectionDescription("access")} compact />

      <div className="stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <Card>
          <form className="form-inline" onSubmit={grant}>
            <Field label="Add someone" grow>
              <select className="input" value={chosen} onChange={(event) => setChosen(event.target.value)}>
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
          <p className="footnote">
            System Administrators reach every project without a membership row. Everyone else is
            granted here, and narrowed to selected phases where their work does not cover the whole
            development.
          </p>
        </Card>

        <Card flush>
          {rows === null ? (
            <Loading label="Loading access…" shape="rows" rows={4} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title="No one has been added yet"
                hint="Grant access to the people who work on this development. Their roles decide what they may do inside it."
              />
            </div>
          ) : (
            <TableScroll label="Project membership">
              <thead>
                <tr>
                  <th scope="col">Person</th>
                  <th scope="col">Roles</th>
                  <th scope="col">Access</th>
                  <th scope="col">Phase scope</th>
                  <th scope="col">Granted</th>
                  <th scope="col">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <th scope="row">
                      {row.display_name}
                      <span className="cell-secondary">{row.email}</span>
                    </th>
                    <td className="cell-prose">
                      {row.role_keys.length > 0 ? row.role_keys.map(roleLabel).join(", ") : "—"}
                    </td>
                    <td>
                      {row.is_active ? (
                        <StatusDot tone="success">Active</StatusDot>
                      ) : (
                        <StatusDot tone="muted">
                          Revoked{row.revoked_at ? ` ${row.revoked_at.slice(0, 10)}` : ""}
                        </StatusDot>
                      )}
                    </td>
                    <td>
                      {row.phase_scope === "selected" ? (
                        <Badge tone="warning">Selected phases</Badge>
                      ) : (
                        <span className="subtle">All phases</span>
                      )}
                    </td>
                    <td className="figure">{row.granted_at.slice(0, 10)}</td>
                    <td>
                      <div className="row-actions">
                        <Button
                          small
                          variant="quiet"
                          onClick={() => setScopeFor(scopeFor?.user_id === row.user_id ? null : row)}
                          aria-expanded={scopeFor?.user_id === row.user_id}
                        >
                          {scopeFor?.user_id === row.user_id ? "Close phases" : "Phases"}
                        </Button>
                        <Button
                          small
                          variant="quiet"
                          disabled={busy}
                          onClick={() => void act(row.user_id, !row.is_active)}
                        >
                          {row.is_active ? "Revoke" : "Restore"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>

        {scopeFor ? (
          <Card
            title={`Phase scope — ${scopeFor.display_name}`}
            description="Whether this person sees the whole development, and if not, which phases."
            actions={<Button small onClick={() => setScopeFor(null)}>Close</Button>}
          >
            <PhaseAccessEditor
              projectId={projectId}
              userId={scopeFor.user_id}
              displayName={scopeFor.display_name}
              phaseScope={scopeFor.phase_scope}
              onScopeChanged={async () => {
                const refreshed = await projects.access(projectId);
                setRows(refreshed);
                setScopeFor(refreshed.find((entry) => entry.user_id === scopeFor.user_id) ?? null);
              }}
            />
          </Card>
        ) : null}
      </div>
    </>
  );
}
