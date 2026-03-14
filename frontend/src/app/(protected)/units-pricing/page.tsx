import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Units & Pricing"
      subtitle="Manage unit inventory and pricing configuration."
    >
      <PlaceholderState module="Units & Pricing" />
    </PageContainer>
  );
}
