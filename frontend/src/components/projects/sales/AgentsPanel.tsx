"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type { SalesClient } from "@/lib/api";
import {
  Button,
  DataToolbar,
  EmptyState,
  Loading,
  Notice,
  RecordPage,
  TableScroll,
} from "@/components/ui";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { agentLabels } from "./AgentFields";

/**
 * Who sold to whom, as attribution rather than as people.
 *
 * There is no agent record in this system. `agent_country`, `agent_branch`,
 * `agent_branch_leader` and `agent_name` are four strings on the buyer, and the
 * only thing they are load-bearing for is being copied onto a reservation and
 * frozen onto the sale that follows it.
 *
 * So this register lists buyers and the team recorded against each, and it does
 * not group them. Two rows reading "Ahmad" are two strings that match, not one
 * salesperson: there is no identifier behind them, nobody has asserted they are
 * the same person, and a screen that merged them would be inventing a roster the
 * business never agreed to — and then counting sales against it.
 *
 * Editing here changes what the *next* reservation will copy. It does not reach
 * backwards: a reservation or sale already made keeps the attribution that was
 * frozen onto it, and correcting one of those is a separate, audited action on
 * that transaction.
 */
export function AgentsPanel({ projectId, canWrite }: { projectId: string; canWrite: boolean }) {
  const [clients, setClients] = useState<SalesClient[] | null>(null);
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<SalesClient | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const attributionFields: EditField[] = (
    Object.keys(agentLabels) as (keyof typeof agentLabels)[]
  ).map((name) => ({ name, label: agentLabels[name] }));

  const load = useCallback(async () => {
    try {
      setClients(await sales.clients(projectId, search ? { search } : {}));
      setError(null);
    } catch (caught) {
      setClients([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load sales team attribution.");
    }
  }, [projectId, search]);
  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  if (editing) {
    return (
      <RecordPage title={`Sales team for ${editing.display_name}`} onClose={() => setEditing(null)}>
        <p className="subtle">
          The team that brought this buyer. Any field may be left empty. Saving changes what the
          buyer&apos;s next reservation copies; reservations and sales already made keep the
          attribution frozen onto them.
        </p>
        <EditForm
          key={editing.id}
          fields={attributionFields}
          columns={2}
          initial={Object.fromEntries(
            attributionFields.map((f) => [f.name, asValue(editing[f.name as keyof SalesClient] as never)]),
          )}
          onSave={async (changes) => {
            await sales.updateClient(projectId, editing.id, changes);
            setNotice(`Sales team updated for ${editing.display_name}.`);
            setEditing(null);
            await load();
          }}
          onCancel={() => setEditing(null)}
        />
      </RecordPage>
    );
  }

  return (
    <div className="stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      <p className="subtle">
        Country, branch, branch leader and agent describe the sales team that brought the
        transaction — not the buyer&apos;s nationality, residence or the location of the property.
      </p>
      <DataToolbar
        search={{
          value: search,
          onChange: setSearch,
          label: "Search buyers",
          placeholder: "Buyer, agent or branch",
        }}
      />
      {clients === null ? (
        <Loading label="Loading sales team attribution" />
      ) : clients.length === 0 ? (
        <EmptyState
          title="No buyers yet"
          hint="Sales team attribution is recorded against a buyer. Register one in Buyers first."
        />
      ) : (
        <TableScroll label="Sales team attribution" fixedFirst>
          <thead>
            <tr>
              <th scope="col">Buyer</th>
              <th scope="col">Country</th>
              <th scope="col">Branch</th>
              <th scope="col">Branch leader</th>
              <th scope="col">Agent</th>
              {canWrite ? <th scope="col">Actions</th> : null}
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.id}>
                <td>{client.display_name}</td>
                {/* An empty cell reads as "not recorded", which is what it is.
                    It is never filled in from anywhere else. */}
                <td>{client.agent_country || <span className="subtle">Not recorded</span>}</td>
                <td>{client.agent_branch || <span className="subtle">Not recorded</span>}</td>
                <td>{client.agent_branch_leader || <span className="subtle">Not recorded</span>}</td>
                <td>{client.agent_name || <span className="subtle">Not recorded</span>}</td>
                {canWrite ? (
                  <td>
                    <Button small onClick={() => { setNotice(null); setEditing(client); }}>
                      Edit attribution
                    </Button>
                  </td>
                ) : null}
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}
    </div>
  );
}
