"use client";

import React, { useEffect } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/AppShell";

/**
 * Protected layout — wraps all authenticated routes.
 *
 * Checks for a stored access token on mount. Unauthenticated users
 * are redirected to /login. Authenticated users get the full AppShell.
 *
 * This is the auth guard for the frontend. The source of truth for
 * authentication remains the backend token issued at /api/v1/auth/login.
 */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("reach_access_token");
      if (!token) {
        router.push("/login");
      }
    }
  }, [router]);

  return <AppShell>{children}</AppShell>;
}
