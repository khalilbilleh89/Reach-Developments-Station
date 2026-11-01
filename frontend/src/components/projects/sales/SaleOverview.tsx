"use client";
import { PriceComparison } from "./PriceComparison";
import { ChangeSalesPrice } from "./ChangeSalesPrice";
import { collections } from "@/lib/api";
import type { ReservationDetail, SaleDetail, SalesClient, CollectionSaleSummary } from "@/lib/api";
import { useAnswer } from "@/lib/answer";
import { COLLECTION_READERS, hasAnyRole } from "@/lib/roles";
import { businessDate, money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { Badge, Banner, Button, KeyValue, KeyValueGrid, SectionHeader, StatusDot, Tooltip } from "@/components/ui";
import { CollectionSnapshot } from "@/components/projects/inventory/unit/UnitSummary";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { gateLabel, gateTone } from "./labels";

export function SaleOverview({ projectId, sale, reservation, client, roles, onOpenTab, onChanged, priceReadError }: {
  projectId: string; sale: SaleDetail | null; reservation: ReservationDetail | null; client: SalesClient | null;
  onChanged: () => Promise<void>; priceReadError?: string | null;
  roles: Set<string>; onOpenTab: (tab: string) => void;
}) {
  const codeOf = useCurrencyCode();
  const account = useAnswer<CollectionSaleSummary>(!!sale && sale.sale.status !== "draft" && hasAnyRole(roles, COLLECTION_READERS), () => collections.account(projectId, sale!.sale.id), [projectId, sale?.sale.id]);
  return <div className="sale-overview">
    {sale || reservation ? <section><SectionHeader level={2} title="Commercial price" /><PriceComparison facts={sale?.sale ?? reservation!.reservation} />{!sale && reservation ? <ChangeSalesPrice projectId={projectId} detail={reservation} onChanged={onChanged} unavailable={priceReadError} /> : null}</section> : null}
    <section><SectionHeader level={2} title="Transaction position" actions={<Button small onClick={() => onOpenTab(sale ? "contract" : "commercial")}>Inspect terms</Button>} />
      <KeyValueGrid columns={2}>
        <KeyValue label="Buyer" value={client?.display_name ?? "Not returned by source"} />
        <KeyValue label="Governing record" value={sale?.sale.spa_number ?? sale?.sale.sale_number ?? reservation?.reservation.reservation_number} />
        {sale ? <><KeyValue label="Contract principal · ex tax" value={money(sale.sale.net_contract_price_ex_tax, codeOf(sale.sale.currency_id))} /><KeyValue label="Legal position" value={<StatusDot tone={statusTone(sale.legal.legal_status)}>{statusLabel(sale.legal.legal_status)}</StatusDot>} /><KeyValue label="Contract date" value={businessDate(sale.sale.contract_date)} /><KeyValue label="First-payment gate" value={<Badge tone={gateTone(sale.sale.first_payment_gate_status)}>{gateLabel(sale.sale.first_payment_gate_status)}</Badge>} /></> : <KeyValue label="Reservation expires" value={businessDate(reservation?.reservation.expires_on)} />}
      </KeyValueGrid>
      {!sale ? <Banner tone="info" action={<Button small onClick={() => onOpenTab("commercial")}>Open the reservation</Button>}>Complete the reservation&apos;s deposit and approval gates before creating the Sale Contract. Its <Tooltip term="SPA">Sale and purchase agreement: the contract the buyer signs for the unit.</Tooltip> schedule is prepared after the contract reaches an eligible state.</Banner> : null}
    </section>
    {account.status !== "off" ? <section><SectionHeader level={2} title="Collections position" actions={<Button small onClick={() => onOpenTab("collections")}>Account detail</Button>} /><CollectionSnapshot answer={account} /></section> : null}
  </div>;
}
