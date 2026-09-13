"use client";

import { Field, FieldRow } from "@/components/ui";

export const emptyAgent = { agent_country: "", agent_branch: "", agent_branch_leader: "", agent_name: "" };
export const agentLabels = { agent_country: "Country", agent_branch: "Branch", agent_branch_leader: "Branch Leader", agent_name: "Agent" };
export function agentPayload(value: typeof emptyAgent) {
  return Object.fromEntries(Object.entries(value).map(([key, text]) => [key, text.trim() || null]));
}

export function AgentFields({value, onChange}: {value: typeof emptyAgent; onChange: (value: typeof emptyAgent) => void}) {
  return <fieldset className="agent-fields"><legend>Agent information</legend><FieldRow columns={2}>
    {(Object.keys(agentLabels) as (keyof typeof emptyAgent)[]).map(key => <Field key={key} label={agentLabels[key]} optional>
      <input className="input" name={key} maxLength={200} value={value[key]} onChange={event => onChange({...value, [key]: event.target.value})} />
    </Field>)}
  </FieldRow></fieldset>;
}
