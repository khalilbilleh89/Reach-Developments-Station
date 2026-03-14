import { redirect } from "next/navigation";

/** Root page: redirect authenticated users to the dashboard. */
export default function RootPage() {
  redirect("/dashboard");
}
