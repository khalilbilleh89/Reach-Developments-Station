"use client";

import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { Card } from "@/components/ui";

/** The one thing a person maintains about their own account. */
export function AccountSection({ onChanged }: { onChanged: () => void }) {
  return (
    <div className="split">
      <Card
        title="Change password"
        description="Choose a new password. Every session, including this one, is signed out afterwards."
      >
        <ChangePasswordForm requireCurrent onChanged={onChanged} />
      </Card>
    </div>
  );
}
