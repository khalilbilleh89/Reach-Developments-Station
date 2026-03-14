import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Dashboard"
      subtitle="Overview of your development portfolio."
    >
      <PlaceholderState module="Dashboard" />
    </PageContainer>
  );
}
