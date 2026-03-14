import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Sales"
      subtitle="Track and manage unit sales across projects."
    >
      <PlaceholderState module="Sales" />
    </PageContainer>
  );
}
