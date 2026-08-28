import type { Metadata, Viewport } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Reach Developments Station",
  robots: { index: false, follow: false },
  description:
    "Real estate development tracking and financial control. Projects, inventory, pricing, sales, collections and cashflow in one auditable source of truth.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
