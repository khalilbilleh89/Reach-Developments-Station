import { PageContainer } from "@/components/shell/PageContainer";
import { PlaceholderState } from "@/components/shell/PlaceholderState";

export default function Page() {
  return (
    <PageContainer
      title="Settings"
      subtitle="Application and user settings."
    >
      <PlaceholderState module="Settings" />
    </PageContainer>
  );
}
