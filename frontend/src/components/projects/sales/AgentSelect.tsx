"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError, sales } from "@/lib/api";
import type { SalesAgent } from "@/lib/api";
import { Button, Field, Notice } from "@/components/ui";

export const agentOption = (agent: SalesAgent) =>
  `${agent.display_name}${agent.branch ? ` — ${agent.branch}` : ""}${agent.is_active ? "" : " (Inactive)"}`;

/** UUID selection; inactive roster entries are visible only for an existing link. */
export function AgentSelect({projectId, value, onChange, disabled = false, currentId = null}: {
  projectId: string; value: string; onChange: (id: string) => void;
  disabled?: boolean; currentId?: string | null;
}) {
  const [agents, setAgents] = useState<SalesAgent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { setAgents(await sales.agents(projectId)); setError(null); }
    catch (caught) { setError(caught instanceof ApiError ? caught.message : "Could not load Agents."); }
  }, [projectId]);
  useEffect(() => { void (async () => { await load(); })(); }, [load]);
  return <Field label="Sales agent — optional" hint="Future reservations copy the selected Agent; existing transactions do not change.">
    {error ? <Notice tone="error">{error}<Button onClick={() => void load()}>Retry Agents</Button></Notice> : null}
    <select className="input" aria-label="Sales agent — optional" value={value} disabled={disabled || agents === null || !!error} onChange={event => onChange(event.target.value)}>
      <option value="">No agent</option>
      {(agents ?? []).filter(agent => agent.is_active || agent.id === currentId).map(agent =>
        <option key={agent.id} value={agent.id}>{agentOption(agent)}</option>)}
    </select>
    {agents?.length === 0 ? <p className="field-hint">No agents have been registered yet. Add one from Commercial → Agents.</p> : null}
  </Field>;
}
