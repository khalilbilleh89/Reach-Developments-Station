"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, auth } from "@/lib/api";
import { Button, Field, Notice } from "@/components/ui";

/**
 * Sign-in.
 *
 * One card on a calm canvas: the product's name, two fields, one button, and
 * the server's own words when it refuses. Client-side routing is not a
 * security boundary — this page only decides what to render, and the API
 * rejects every protected action on its own.
 */
export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Someone already signed in has no business on the login form.
  useEffect(() => {
    auth
      .me()
      .then(() => router.replace("/projects/"))
      .catch(() => undefined);
  }, [router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await auth.login(email, password);
      router.replace("/projects/");
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : "Could not sign in. Please try again.",
      );
      setBusy(false);
    }
  }

  return (
    <div className="shell">
      <main className="signin">
        <div className="signin-brand">
          <span className="brand-mark" aria-hidden="true">
            R
          </span>
          <span>
            <span className="signin-brand-name">Reach</span>
            <br />
            <span className="signin-brand-sub">Developments Station</span>
          </span>
        </div>
        <div className="panel">
          <h1 className="panel-title">Sign in</h1>
          <p className="panel-lead">Real estate development tracking and financial control.</p>

          <form onSubmit={submit} noValidate>
            <Field label="Email">
              <input
                className="input"
                type="email"
                name="email"
                autoComplete="username"
                autoFocus
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
            </Field>
            <Field label="Password">
              <input
                className="input"
                type="password"
                name="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </Field>

            {error ? <Notice tone="error">{error}</Notice> : null}

            <Button variant="primary" block type="submit" disabled={busy}>
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </div>
        <p className="signin-foot">
          No account is created automatically. An administrator issues access.
        </p>
      </main>
    </div>
  );
}
