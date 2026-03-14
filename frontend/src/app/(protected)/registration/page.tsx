import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Registration"
      subtitle="Conveyancing cases, milestones, and document tracking."
    >
      <PlaceholderState module="Registration" />
    </PageContainer>
  );
}
