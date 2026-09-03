"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "@/lib/api/session";
import { SessionScreen } from "@/components/shell/AppShell";

/**
 * Entry point: send the visitor wherever their session says they belong.
 */
export default function HomePage() {
  const router = useRouter();
  const { state } = useSession();

  useEffect(() => {
    if (state.status === "authenticated") router.replace("/projects/");
    if (state.status === "anonymous") router.replace("/login/");
  }, [state, router]);

  return <SessionScreen status="loading" />;
}
