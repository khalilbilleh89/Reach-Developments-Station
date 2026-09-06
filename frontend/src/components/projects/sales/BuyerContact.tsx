"use client";

import { useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import { KeyValue, KeyValueGrid, Loading, Notice, SectionHeader } from "@/components/ui";

export function BuyerContact({ projectId, clientId }: { projectId: string; clientId: string }) {
  const [buyer, setBuyer] = useState<SalesClient | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    void sales.client(projectId, clientId).then((row) => { if (active) { setBuyer(row); setError(null); } }).catch((caught) => {
      if (active) setError(caught instanceof ApiError ? caught.message : "Could not load buyer details.");
    });
    return () => { active = false; };
  }, [projectId, clientId]);
  return <section><SectionHeader title="Buyer contact" />
    {error ? <Notice tone="error">{error}</Notice> : buyer ? <KeyValueGrid columns={3}>
      <KeyValue label="Buyer" value={buyer.display_name} />
      {"phone" in buyer ? <KeyValue label="Phone" value={buyer.phone} /> : null}
      {"email" in buyer ? <KeyValue label="Email" value={buyer.email} /> : null}
    </KeyValueGrid> : <Loading label="Loading buyer…" />}
  </section>;
}
