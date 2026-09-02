"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, users as usersApi } from "@/lib/api";
import type { AdminUser, Role } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  Loading,
  Notice,
  StatusDot,
  TableScroll,
} from "@/components/ui";

const EMPTY_DRAFT = { email: "", display_name: "", initial_password: "", role_keys: [] as string[] };

/** User administration: who exists, what they may do, and access resets. */
export function UsersSection() {
  const [rows, setRows] = useState<AdminUser[] | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [search, setSearch] = useState("");
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

  const needle = search.trim().toLowerCase();
  const shown = (rows ?? []).filter(
    (row) =>
      !needle ||
      row.display_name.toLowerCase().includes(needle) ||
      row.email.toLowerCase().includes(needle),
  );

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {adding ? (
        <Card title="Add a user" description="They sign in with a temporary password and must replace it before doing anything else.">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void act(async () => {
                await usersApi.create(draft);
                setDraft(EMPTY_DRAFT);
                setAdding(false);
              }, "User created. They must change the temporary password at first sign-in.");
            }}
          >
            <FormSection title="Identity">
              <FieldRow columns={3}>
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
                    autoComplete="new-password"
                    value={draft.initial_password}
                    onChange={(event) => setDraft({ ...draft, initial_password: event.target.value })}
                  />
                </Field>
              </FieldRow>
            </FormSection>
            <FormSection title="Roles" description="What this person may do, across every project they are granted.">
              <fieldset className="fieldset">
                <legend className="visually-hidden">Roles</legend>
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
            </FormSection>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                {busy ? "Creating…" : "Create user"}
              </Button>
              <Button onClick={() => setAdding(false)} disabled={busy}>
                Cancel
              </Button>
            </FormActions>
          </form>
        </Card>
      ) : null}

      <DataToolbar
        search={{ value: search, onChange: setSearch, placeholder: "Name or email", label: "Search users" }}
        count={rows ? { shown: shown.length, total: rows.length, noun: "user" } : undefined}
        actions={
          adding ? undefined : (
            <Button variant="primary" onClick={() => setAdding(true)}>
              Add user
            </Button>
          )
        }
      />

      <Card flush>
        {rows === null ? (
          <Loading label="Loading users…" shape="rows" />
        ) : shown.length === 0 ? (
          <div className="card-body">
            <EmptyState
              title={rows.length === 0 ? "No users yet" : "No user matches"}
              hint={
                rows.length === 0
                  ? "The first administrator is created from the server shell, then adds the rest here."
                  : "Try another name or email."
              }
            />
          </div>
        ) : (
          <TableScroll label="Users and their roles">
            <thead>
              <tr>
                <th scope="col">Person</th>
                <th scope="col">Roles</th>
                <th scope="col">Status</th>
                <th scope="col">Last sign-in</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.map((row) => (
                <tr key={row.id}>
                  <th scope="row">
                    {row.display_name}
                    <span className="cell-secondary">{row.email}</span>
                  </th>
                  <td className="cell-prose">
                    {row.role_keys.length > 0 ? row.role_keys.map(roleLabel).join(", ") : "—"}
                  </td>
                  <td>
                    <div className="row-actions">
                      {row.is_active ? (
                        <StatusDot tone="success">Active</StatusDot>
                      ) : (
                        <StatusDot tone="muted">Inactive</StatusDot>
                      )}
                      {row.must_change_password ? <Badge tone="warning">Password due</Badge> : null}
                    </div>
                  </td>
                  <td className="figure">{row.last_login_at ? row.last_login_at.slice(0, 10) : "Never"}</td>
                  <td>
                    <Button
                      small
                      variant="quiet"
                      disabled={busy}
                      onClick={() =>
                        void act(
                          () => usersApi.update(row.id, { is_active: !row.is_active }),
                          row.is_active ? "User deactivated." : "User reactivated.",
                        )
                      }
                    >
                      {row.is_active ? "Deactivate" : "Reactivate"}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>
    </div>
  );
}
