"use client";

import { Badge, Button, Card, TableScroll } from "@/components/ui";
import type { Answer } from "@/lib/answer";
import type { Roles } from "@/lib/roles";
import { PROJECT_NAVIGATION, visibleNavigation } from "@/components/shell/navigation";
import type { ProjectSection } from "@/components/shell/navigation";

const REPORTS: { section: ProjectSection; title: string; purpose: string }[] = [
  { section: "inventory", title: "Inventory & delivery", purpose: "Open a unit to inspect its physical record, commercial standing and construction stages." },
  { section: "sales", title: "Sales & legal register", purpose: "Inspect reservations, signed contracts, registry dates and cancellations." },
  { section: "collections", title: "Collections & buyer statements", purpose: "Review dated balances, overdue accounts, receipts and unapplied cash." },
  { section: "construction", title: "Construction control", purpose: "Inspect budget, commitments, certified work and payments separately." },
  { section: "economics", title: "Project profitability", purpose: "Review the approved cost basis and the server's comparable-unit coverage." },
  { section: "cashflow", title: "Cashflow & management reports", purpose: "Choose an as-of date, inspect funding and reconciliation, and export the dated source rows." },
  { section: "permits", title: "Permit tracker", purpose: "Inspect consent dates, blocking flags and statutory delays." },
];

/** Links share the navigation permission catalogue; this panel fetches no data. */
export function ManagementReports({ roles, sources, onNavigate }: {
  roles: Roles; sources: [string, Answer<unknown>][];
  onNavigate: (section: ProjectSection) => void;
}) {
  const allowed = new Set(visibleNavigation(PROJECT_NAVIGATION, roles).flatMap((group) => group.items.map((item) => item.key)));
  return <details>
    <summary>Management reports & source coverage</summary>
    <Card title="Management reports" description="Open the owning register to apply its filters and inspect the records behind each figure.">
      <TableScroll label="Available management reports" compact>
        <thead><tr><th scope="col">Report</th><th scope="col">Use it to</th><th scope="col">Action</th></tr></thead>
        <tbody>{REPORTS.filter((report) => allowed.has(report.section)).map((report) => <tr key={report.section}>
          <th scope="row">{report.title}</th><td className="cell-prose">{report.purpose}</td>
          <td><Button small variant="quiet" aria-label={`Open ${report.title}`} onClick={() => onNavigate(report.section)}>Open report</Button></td>
        </tr>)}</tbody>
      </TableScroll>
      <h3>Current source coverage</h3>
      <p className="footnote">This overview combines live module responses. Historical reports state their own as-of dates. Unavailable sources are not zero balances.</p>
      <ul>{sources.filter(([, answer]) => answer.status !== "off").map(([name, answer]) => <li key={name}>
        {name}: <Badge tone={answer.status === "ready" ? "success" : answer.status === "failed" ? "danger" : "neutral"}>
          {answer.status === "ready" ? "Loaded" : answer.status === "loading" ? "Loading" : answer.status === "denied" ? "Outside your access" : "Unavailable"}
        </Badge>
      </li>)}</ul>
    </Card>
  </details>;
}
