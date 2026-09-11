"use client";
import { collections } from "@/lib/api";
import type { ReservationDetail, SaleDetail, SalesClient, CollectionSaleSummary } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { COLLECTION_READERS, hasAnyRole } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { Button, KeyValue, KeyValueGrid, SectionHeader, Notice } from "@/components/ui";
import { CollectionSnapshot } from "@/components/projects/inventory/unit/UnitSummary";
import { statusLabel } from "@/components/projects/inventory/statusLabels";
import { gateLabel } from "./labels";

export function SaleOverview({ projectId, sale, reservation, client, roles, onOpenTab }: {
  projectId: string; sale: SaleDetail | null; reservation: ReservationDetail | null; client: SalesClient | null;
  roles: Set<string>; onOpenTab: (tab: string) => void;
}) {
  const codeOf = useCurrencyCode();
  const account = useAnswer<CollectionSaleSummary>(!!sale && sale.sale.status !== "draft" && hasAnyRole(roles, COLLECTION_READERS), () => collections.account(projectId, sale!.sale.id), [projectId, sale?.sale.id]);
  return <div className="sale-overview">
    <section><SectionHeader level={2} title="Transaction position" actions={<Button small onClick={() => onOpenTab(sale ? "contract" : "commercial")}>Inspect terms</Button>} />
      <KeyValueGrid columns={2}>
        <KeyValue label="Buyer" value={client?.display_name ?? "Not returned by source"} />
        <KeyValue label="Governing record" value={sale?.sale.spa_number ?? sale?.sale.sale_number ?? reservation?.reservation.reservation_number} />
        {sale ? <><KeyValue label="Contract principal · ex tax" value={money(sale.sale.net_contract_price_ex_tax, codeOf(sale.sale.currency_id))} /><KeyValue label="Legal position" value={statusLabel(sale.legal.legal_status)} /><KeyValue label="Contract date" value={businessDate(sale.sale.contract_date)} /><KeyValue label="First-payment gate" value={gateLabel(sale.sale.first_payment_gate_status)} /></> : <KeyValue label="Reservation expires" value={businessDate(reservation?.reservation.expires_on)} />}
      </KeyValueGrid>
      {!sale ? <Notice tone="info">Complete the reservation&apos;s deposit and approval gates before creating the Sale Contract. Its SPA schedule is prepared after the contract reaches an eligible state.</Notice> : null}
    </section>
    {account.status !== "off" ? <section><SectionHeader level={2} title="Collections position" actions={<Button small onClick={() => onOpenTab("collections")}>Account detail</Button>} /><CollectionSnapshot answer={account} /></section> : null}
  </div>;
}
