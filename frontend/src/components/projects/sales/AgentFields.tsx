"use client";

import { Field, FieldRow } from "@/components/ui";

export const emptyAgent = { agent_country: "", agent_branch: "", agent_branch_leader: "", agent_name: "" };
export const agentLabels = { agent_country: "Country", agent_branch: "Branch", agent_branch_leader: "Branch Leader", agent_name: "Agent" };
export function agentPayload(value: typeof emptyAgent) {
  return Object.fromEntries(Object.entries(value).map(([key, text]) => [key, text.trim() || null]));
}

/**
 * The selling team, never the buyer.
 *
 * The legend and hint are load-bearing. These four fields sat under a buyer's
 * name labelled only "Country" and "Branch", which reads as the purchaser's
 * nationality and address to anybody who has not been told otherwise — and the
 * person filling the form in is exactly that person.
 */
export function AgentFields({value, onChange}: {value: typeof emptyAgent; onChange: (value: typeof emptyAgent) => void}) {
  return <fieldset className="agent-fields"><legend>Sales team — optional</legend>
    <p className="field-hint">Who sold to this buyer. Not the buyer&apos;s nationality, residence or the location of the property. Leave any field empty if it is not known; it can be recorded later in Agents.</p>
    <FieldRow columns={2}>
    {(Object.keys(agentLabels) as (keyof typeof emptyAgent)[]).map(key => <Field key={key} label={agentLabels[key]} optional>
      <input className="input" name={key} maxLength={200} value={value[key]} onChange={event => onChange({...value, [key]: event.target.value})} />
    </Field>)}
  </FieldRow></fieldset>;
}
