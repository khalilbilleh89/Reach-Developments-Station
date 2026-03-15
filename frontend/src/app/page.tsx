"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Root page: unconditionally redirects all users to the dashboard.
 *  Uses a client-side redirect so the page is compatible with static export.
 *  The protected layout handles auth gating from there. */
export default function RootPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/dashboard");
  }, [router]);
  return <p aria-live="polite">Redirecting…</p>;
}
