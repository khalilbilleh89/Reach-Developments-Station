import type { LegalTimeline } from "@/lib/api";
import { KeyValue, KeyValueGrid, SectionHeader } from "@/components/ui";
import { businessDate } from "@/lib/format";

/** Only events the backend says still stand are presented as current facts. */
export function LegalSummary({ timeline }: { timeline: LegalTimeline }) {
  const standing = timeline.events.filter((event) => timeline.effective_event_ids.includes(event.id));
  const event = (type: string) => standing.find((entry) => entry.event_type === type);
  return <section>
    <SectionHeader title="SPA & land registry" description="Signing, lodging and registration are separate legal milestones." />
    <KeyValueGrid columns={3}>
      <KeyValue label="Buyer signed SPA" value={businessDate(event("buyer_signed")?.event_date)} />
      <KeyValue label="Seller signed SPA" value={businessDate(event("seller_signed")?.event_date)} />
      <KeyValue label="Land registry lodging date" value={businessDate(event("land_registry_lodged")?.event_date)} />
      <KeyValue label="Registry authority reference" value={event("land_registry_lodged")?.authority_reference} />
      <KeyValue label="Lodging document" value={event("land_registry_lodged")?.document_reference} />
      <KeyValue label="Registered" value={businessDate(event("registered")?.event_date)} />
    </KeyValueGrid>
  </section>;
}
