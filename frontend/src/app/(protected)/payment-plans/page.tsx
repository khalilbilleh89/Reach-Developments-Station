import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Payment Plans"
      subtitle="Configure and view customer payment schedules."
    >
      <PlaceholderState module="Payment Plans" />
    </PageContainer>
  );
}
