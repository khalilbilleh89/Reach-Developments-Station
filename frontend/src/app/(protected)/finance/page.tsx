import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Finance"
      subtitle="Financial summary and analytics for all projects."
    >
      <PlaceholderState module="Finance" />
    </PageContainer>
  );
}
