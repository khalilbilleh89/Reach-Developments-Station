"use client";

import { ChangePasswordForm } from "@/components/ChangePasswordForm";
import { Card, Icon } from "@/components/ui";

/** The one thing a person maintains about their own account. */
export function AccountSection({ onChanged }: { onChanged: () => void }) {
  return (
    <div className="settings-layout">
      <aside className="settings-context">
        <Icon name="access" />
        <h2>Account security</h2>
        <p>Manage the credentials you use to access Reach.</p>
        <p>Saving a new password signs out every session, including this one.</p>
      </aside>
      <Card
        title="Change password"
        description="Choose a new password. Every session, including this one, is signed out afterwards."
      >
        <ChangePasswordForm requireCurrent onChanged={onChanged} />
      </Card>
    </div>
  );
}
