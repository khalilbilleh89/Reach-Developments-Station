import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Projects"
      subtitle="Manage and monitor all development projects."
    >
      <PlaceholderState module="Projects" />
    </PageContainer>
  );
}
