"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, users as usersApi } from "@/lib/api";
import type { AdminUser, Role } from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";

const EMPTY_DRAFT = { email: "", display_name: "", initial_password: "", role_keys: [] as string[] };

/** User administration: who exists, what they may do, and access resets. */
export function UsersSection() {
  const [rows, setRows] = useState<AdminUser[] | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [draft, setDraft] = useState(EMPTY_DRAFT);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [page, roleList] = await Promise.all([usersApi.list(), usersApi.roles()]);
      setRows(page.items);
      setRoles(roleList);
      setError(null);
    } catch (caught) {
      setRows([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load users.");
    }
  }, []);

  useEffect(() => {
    // Wrapped rather than called directly: the effect body must not invoke a
    // state-setting function synchronously (react-hooks/set-state-in-effect).
    void (async () => {
      await load();
    })();
  }, [load]);

  async function act<T>(operation: () => Promise<T>, success: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await operation();
      setNotice(success);
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The change could not be saved.");
    } finally {
      setBusy(false);
    }
  }

  function toggleRole(key: string) {
    setDraft((previous) => ({
      ...previous,
      role_keys: previous.role_keys.includes(key)
        ? previous.role_keys.filter((existing) => existing !== key)
        : [...previous.role_keys, key],
    }));
  }

  // Show the human label, not the internal key.
  const roleLabel = (key: string) => roles.find((role) => role.key === key)?.label ?? key;

  if (rows === null) return <Loading label="Loading users…" />;

  return (
    <Panel
      title="Users"
      description="People who can sign in, and the roles that decide what they may do."
      actions={
        <button className="button" type="button" onClick={() => setAdding((open) => !open)}>
          {adding ? "Cancel" : "Add user"}
        </button>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {adding ? (
        <form
          className="form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            void act(async () => {
              await usersApi.create(draft);
              setDraft(EMPTY_DRAFT);
              setAdding(false);
            }, "User created. They must change the temporary password at first sign-in.");
          }}
        >
          <Field label="Email">
            <input
              className="input"
              type="email"
              required
              value={draft.email}
              onChange={(event) => setDraft({ ...draft, email: event.target.value })}
            />
          </Field>
          <Field label="Display name">
            <input
              className="input"
              required
              value={draft.display_name}
              onChange={(event) => setDraft({ ...draft, display_name: event.target.value })}
            />
          </Field>
          <Field label="Temporary password" hint="At least 12 characters. Replaced at first sign-in.">
            <input
              className="input"
              type="password"
              required
              minLength={12}
              value={draft.initial_password}
              onChange={(event) => setDraft({ ...draft, initial_password: event.target.value })}
            />
          </Field>
          <fieldset className="fieldset">
            <legend className="field-label">Roles</legend>
            <div className="checkbox-grid">
              {roles.map((role) => (
                <label className="checkbox" key={role.key}>
                  <input
                    type="checkbox"
                    checked={draft.role_keys.includes(role.key)}
                    onChange={() => toggleRole(role.key)}
                  />
                  <span>{role.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="form-actions">
            <button className="button button-primary" type="submit" disabled={busy}>
              Create user
            </button>
          </div>
        </form>
      ) : null}

      {rows.length === 0 ? (
        <EmptyState
          title="No users yet"
          hint="The first administrator is created from the server shell, then adds the rest here."
        />
      ) : (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Users and their roles</caption>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Roles</th>
                <th scope="col">Status</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.display_name}</td>
                  <td className="mono">{row.email}</td>
                  <td>{row.role_keys.length > 0 ? row.role_keys.map(roleLabel).join(", ") : "—"}</td>
                  <td>
                    {row.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Inactive</Badge>
                    )}
                    {row.must_change_password ? <Badge tone="neutral">Password due</Badge> : null}
                  </td>
                  <td>
                    <button
                      className="button button-small"
                      type="button"
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () => usersApi.update(row.id, { is_active: !row.is_active }),
                          row.is_active ? "User deactivated." : "User reactivated.",
                        )
                      }
                    >
                      {row.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}
