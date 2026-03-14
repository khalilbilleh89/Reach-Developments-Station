"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/shell/AppShell";

/**
 * Protected layout — wraps all authenticated routes.
 *
 * Checks for a stored access token on mount. While the check is running
 * (or when no token is present) the layout renders nothing to prevent
 * protected UI from flashing before the redirect fires. Only once a valid
 * token is confirmed does the AppShell render.
 *
 * The source of truth for authentication remains the backend token issued
 * at /api/v1/auth/login.
 */
export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [isChecking, setIsChecking] = useState(true);
  const [isAuthed, setIsAuthed] = useState(false);

  useEffect(() => {
    const token =
      typeof window !== "undefined"
        ? localStorage.getItem("reach_access_token")
        : null;

    if (!token) {
      router.push("/login");
      // Keep isChecking true so nothing renders during the redirect.
    } else {
      setIsAuthed(true);
      setIsChecking(false);
    }
  }, [router]);

  if (isChecking || !isAuthed) {
    return null;
  }

  return <AppShell>{children}</AppShell>;
}

