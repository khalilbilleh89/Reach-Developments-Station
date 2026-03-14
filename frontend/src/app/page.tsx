import { redirect } from "next/navigation";

/** Root page: unconditionally redirects all users to the dashboard.
 *  The protected layout handles auth gating from there. */
export default function RootPage() {
  redirect("/dashboard");
}
