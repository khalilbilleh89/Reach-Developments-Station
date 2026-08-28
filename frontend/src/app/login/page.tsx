"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, auth } from "@/lib/api";
import { Field, Notice } from "@/components/ui";

/**
 * Sign-in.
 *
 * Client-side routing is not a security boundary: this page only decides what
 * to render. The API rejects every protected action on its own.
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
    <div className="shell shell-centred">
      <main className="panel panel-narrow">
        <p className="eyebrow">Reach Developments Station</p>
        <h1 className="title title-compact">Sign in</h1>
        <p className="tagline">Real Estate Development Tracking &amp; Financial Control</p>

        <form onSubmit={submit} noValidate>
          <Field label="Email">
            <input
              className="input"
              type="email"
              name="email"
              autoComplete="username"
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

          <button className="button button-primary button-block" type="submit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="footnote">
          No account is created automatically. An administrator issues access.
        </p>
      </main>
    </div>
  );
}
