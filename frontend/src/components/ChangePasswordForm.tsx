"use client";

import { useState } from "react";

import { ApiError, auth } from "@/lib/api";
import { Button, Field, Notice } from "@/components/ui";

/**
 * Password change.
 *
 * Used both for the forced first-login change and for a voluntary one. Either
 * way the API revokes every session afterwards, so the caller must sign in
 * again — `onChanged` exists to take them back to the login screen.
 */
export function ChangePasswordForm({
  requireCurrent,
  onChanged,
}: {
  requireCurrent: boolean;
  onChanged: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (next !== confirm) {
      setError("The two new passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await auth.changePassword(next, requireCurrent ? current : undefined);
      onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not change the password.");
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} noValidate>
      {requireCurrent ? (
        <Field label="Current password">
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(event) => setCurrent(event.target.value)}
          />
        </Field>
      ) : null}
      <Field label="New password" hint="At least 12 characters. Length matters more than symbols.">
        <input
          className="input"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          value={next}
          onChange={(event) => setNext(event.target.value)}
        />
      </Field>
      <Field label="Confirm new password">
        <input
          className="input"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
        />
      </Field>

      {error ? <Notice tone="error">{error}</Notice> : null}

      <Button variant="primary" type="submit" disabled={busy}>
        {busy ? "Saving…" : "Change password"}
      </Button>
      <p className="footnote">
        Changing your password signs you out everywhere. You will be asked to sign in again.
      </p>
    </form>
  );
}
