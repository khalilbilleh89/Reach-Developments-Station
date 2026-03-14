import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Collections"
      subtitle="Monitor payment receipts and receivable status."
    >
      <PlaceholderState module="Collections" />
    </PageContainer>
  );
}
