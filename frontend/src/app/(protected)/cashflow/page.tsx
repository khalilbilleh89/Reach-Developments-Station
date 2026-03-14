import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Cashflow"
      subtitle="Cashflow forecasting and period analysis."
    >
      <PlaceholderState module="Cashflow" />
    </PageContainer>
  );
}
