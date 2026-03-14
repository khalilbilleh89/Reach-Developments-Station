import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Commission"
      subtitle="Commission plans, slabs, and payout tracking."
    >
      <PlaceholderState module="Commission" />
    </PageContainer>
  );
}
