"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type { ClientParty, SalesClient } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  RecordPage,
  DataToolbar,
  EmptyState,
  Field,
  FieldRow,
  FormActions,
  FormSection,
  InlineMeta,
  InlineMetaItem,
  Loading,
  Notice,
  StatusDot,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { BuyerForm } from "@/components/projects/sales/BuyerForm";
import { DeleteRecordButton } from "@/components/projects/DeleteRecordButton";
import { EditForm, asValue } from "@/components/projects/EditForm";
import type { EditField } from "@/components/projects/EditForm";
import { kycLabel, kycTone } from "@/components/projects/sales/labels";

/**
 * The project's buyers, and the named parties on each.
 *
 * Which fields arrive here is the server's decision, made before the response
 * was built: a reader who may not see contact details receives a client object
 * without those keys. This panel renders what it was given and never asks
 * whether it should be hiding something.
 *
 * Shares are shown against every buyer because they are the thing that stops a
 * unit being committed: two purchasers at forty per cent each is a contract
 * that sells eighty per cent of a flat, and finding that out at activation is
 * finding out too late.
 */
export function ClientsPanel({
  canAdmin = false,
  projectId,
  canWrite,
  onChanged,
  onClose,
  onConnect,
}: {
  projectId: string;
  canWrite: boolean;
  canAdmin?: boolean;
  onChanged: () => Promise<void>;
  onClose?: () => void;
  onConnect?: (buyer: SalesClient) => void;
}) {
  const [clients, setClients] = useState<SalesClient[] | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [parties, setParties] = useState<ClientParty[]>([]);
  const [shares, setShares] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [editing, setEditing] = useState<SalesClient | null>(null);
  const [editingParty, setEditingParty] = useState<ClientParty | null>(null);
  const partyFields: EditField[] = [
    { name: "name_as_identification", label: "Full name as identification" },
    { name: "share_fraction", label: "Ownership share", hint: "1 = 100%; 0.5 = 50%" },
    { name: "nationality_code", label: "Nationality code" },
    { name: "residency_code", label: "Residency code" },
    { name: "party_role", label: "Party role", kind: "select", options: [{ value: "purchaser", label: "Purchaser" }, { value: "joint_purchaser", label: "Joint purchaser" }] },
    ...["tax_id", "identity_document_type", "identity_document_number", "representative_name", "poa_reference"].map(name => ({ name, label: name.replaceAll("_", " "), visible: editingParty ? name in editingParty : false })),
    { name: "is_primary", label: "Primary purchaser", kind: "checkbox" },
    { name: "is_active", label: "Active party", kind: "checkbox" },
  ];
  const clientFields: EditField[] = [
    { name: "display_name", label: "Buyer name" },
    { name: "agent_country", label: "Country" },
    { name: "agent_branch", label: "Branch" },
    { name: "agent_branch_leader", label: "Branch Leader" },
    { name: "agent_name", label: "Agent" },

    { name: "email", label: "Email" }, { name: "phone", label: "Phone" },
    { name: "address", label: "Address" },
    { name: "preferred_language_code", label: "Language code" },
    { name: "kyc_status", label: "KYC status", kind: "select", options: ["not_started", "in_progress", "cleared", "rejected"].map(value => ({ value, label: value.replaceAll("_", " ") })) },
    { name: "is_active", label: "Active buyer", kind: "checkbox" },
  ];
  const [party, setParty] = useState({
    name_as_identification: "",
    share_fraction: "1.000000",
    party_role: "purchaser",
    identity_document_type: "",
    identity_document_number: "",
  });

  const load = useCallback(async () => {
    try {
      setClients(await sales.clients(projectId, search ? { search } : {}));
      setError(null);
    } catch (caught) {
      setClients([]);
      setError(caught instanceof ApiError ? caught.message : "Could not load buyers.");
    }
  }, [projectId, search]);

  const loadParties = useCallback(
    async (clientId: string) => {
      try {
        setParties(await sales.parties(projectId, clientId));
        const reconciliation = await sales.shareReconciliation(projectId, clientId);
        setShares(reconciliation.total_share_fraction);
      } catch (caught) {
        setError(caught instanceof ApiError ? caught.message : "Could not load buyer parties.");
      }
    },
    [projectId],
  );

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  useEffect(() => {
    void (async () => {
      if (selected) await loadParties(selected);
    })();
  }, [selected, loadParties]);

  const run = async (action: () => Promise<unknown>, done: string) => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(done);
      await load();
      if (selected) await loadParties(selected);
      // The register behind this panel offers these buyers when a unit is
      // reserved, so it has to hear about a new one.
      await onChanged();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  if (clients === null) {
    return (
      <Card title="Buyers">
        <Loading label="Loading buyers…" shape="rows" rows={4} />
      </Card>
    );
  }

  const chosen = clients.find((client) => client.id === selected) ?? null;

  return (
    <Card
      title="Buyers"
      description="Buyer details, sales team and unit connections for this project."
      actions={
        <>
          {canWrite ? (
            <Button variant="primary" small data-leaves-editor={registering || undefined} onClick={() => setRegistering(!registering)}>
              {registering ? "Cancel" : "Register a buyer"}
            </Button>
          ) : null}
          {onClose ? <Button variant="quiet" small data-leaves-editor onClick={onClose}>
            Close
          </Button> : null}
        </>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {editing ? <RecordPage title={`Edit ${editing.display_name}`} onClose={() => setEditing(null)}><EditForm
        key={editing.id} fields={clientFields}
        initial={Object.fromEntries(clientFields.map(field => [field.name, asValue(editing[field.name as keyof SalesClient] as never)]))}
        onCancel={() => setEditing(null)} onSave={async changes => {
          await sales.updateClient(projectId, editing.id, changes); setEditing(null); await load(); await onChanged();
        }} /></RecordPage> : null}

      {canWrite && registering ? (
        <RecordPage title="Register buyer and agent" onClose={() => setRegistering(false)}>
          <BuyerForm projectId={projectId} onCancel={() => setRegistering(false)} onSaved={(buyer) => {
            setRegistering(false);
            setSelected(buyer.id);
            void load();
            void onChanged();
          }} />
        </RecordPage>
      ) : null}

      <DataToolbar
        search={{
          value: search,
          onChange: setSearch,
          placeholder: "Name or client number",
          label: "Search buyers",
        }}
        count={{ shown: clients.length, noun: "buyer" }}
        onReset={search ? () => setSearch("") : undefined}
      />

      {clients.length === 0 ? (
        <EmptyState
          title="No buyers yet"
          hint={canWrite ? "Register one to reserve a unit for them." : "Nobody has been registered on this project."}
        />
      ) : (
        <TableScroll label="Buyers" compact>
          <thead>
            <tr>
              <th scope="col">Client</th>
              <th scope="col">Name</th>
              <th scope="col">Identity checks</th>
              <th scope="col">Contact</th>
              <th scope="col">Standing</th>
              <th scope="col">
                <span className="visually-hidden">Parties</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {clients.map((client) => (
              <tr key={client.id} aria-selected={selected === client.id}>
                <th scope="row" className="mono">
                  {client.client_number}
                </th>
                <td className="buyer-identity">{client.display_name}<span className="cell-secondary">{[client.agent_country, client.agent_branch, client.agent_branch_leader, client.agent_name].filter(Boolean).join(" · ") || "Sales team not recorded"}</span></td>
                <td>
                  <Badge tone={kycTone(client.kyc_status)}>{kycLabel(client.kyc_status)}</Badge>
                </td>
                <td>
                  {"email" in client ? (
                    (client.email ?? client.phone ?? "—")
                  ) : (
                    <span className="subtle">Not shown to your role</span>
                  )}
                </td>
                <td>
                  {client.is_active ? (
                    <StatusDot tone="success">Active</StatusDot>
                  ) : (
                    <StatusDot tone="muted">Inactive</StatusDot>
                  )}
                </td>
                <td><div className="buyer-actions">
                  <Button
                    small
                    variant="quiet"
                    aria-expanded={selected === client.id}
                    data-leaves-editor
                    onClick={() => { setEditingParty(null); setParties([]); setShares(null); setSelected(selected === client.id ? null : client.id); }}
                  >
                    {selected === client.id ? "Hide parties" : "Parties"}
                  </Button>
                  {canWrite && client.is_active && onConnect ? <Button small data-leaves-editor onClick={() => onConnect(client)}>Connect unit</Button> : null}
                  {canWrite ? <Button small data-leaves-editor onClick={() => setEditing(client)}>Edit buyer</Button> : null}
                  {canAdmin ? <DeleteRecordButton label="buyer" onDelete={reason => sales.deleteClient(projectId, client.id, reason)} onDeleted={async () => { setSelected(null); setEditing(null); await load(); await onChanged(); }} /> : null}
                </div></td>
              </tr>
            ))}
          </tbody>
        </TableScroll>
      )}

      {selected ? (
        <SubPanel
          title={chosen ? `Parties on ${chosen.display_name}` : "Buyer parties"}
          actions={
            shares !== null ? (
              <InlineMeta>
                <InlineMetaItem label="Shares total">
                  <span className="figure">{shares}</span>
                </InlineMetaItem>
                <InlineMetaItem label="Unit">
                  {shares === "1.000000" ? (
                    <Badge tone="success">A whole unit</Badge>
                  ) : (
                    <Badge tone="warning">Not yet a whole unit</Badge>
                  )}
                </InlineMetaItem>
              </InlineMeta>
            ) : undefined
          }
        >
          {editingParty ? <EditForm key={editingParty.id} fields={partyFields}
            initial={Object.fromEntries(partyFields.map(field => [field.name, asValue(editingParty[field.name as keyof ClientParty] as never)]))}
            onCancel={() => setEditingParty(null)} onSave={async changes => {
              await sales.updateParty(projectId, editingParty.id, changes); setEditingParty(null); await loadParties(selected); await onChanged();
            }} /> : null}
          {parties.length === 0 ? (
            <EmptyState compact title="No parties recorded" hint="A unit cannot be committed until the buyer shares total 1.000000." />
          ) : (
            <TableScroll label="Buyer parties" compact>
              <thead>
                <tr>
                  <th scope="col">Name as identification</th>
                  <th scope="col">Role</th>
                  <th scope="col" className="num">
                    Share
                  </th>
                  <th scope="col">Identity document</th>
                  <th scope="col">Standing</th>
                </tr>
              </thead>
              <tbody>
                {parties.map((item) => (
                  <tr key={item.id}>
                    <th scope="row">{item.name_as_identification}</th>
                    <td>{item.party_role === "purchaser" ? "Purchaser" : "Joint purchaser"}</td>
                    <td className="num">{item.share_fraction}</td>
                    <td className="mono">
                      {"identity_document_number" in item ? (
                        `${item.identity_document_type ?? "—"} ${item.identity_document_number ?? ""}`
                      ) : (
                        <span className="subtle">Not shown to your role</span>
                      )}
                    </td>
                    <td>
                      {item.is_active ? (
                        <StatusDot tone="success">Active</StatusDot>
                      ) : (
                        <StatusDot tone="muted">Inactive</StatusDot>
                      )}
                      {canWrite ? <Button small data-leaves-editor onClick={() => setEditingParty(item)}>Edit party</Button> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}

          {canWrite ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    sales.createParty(projectId, selected, {
                      name_as_identification: party.name_as_identification,
                      share_fraction: party.share_fraction,
                      party_role: party.party_role,
                      ...(party.identity_document_type ? { identity_document_type: party.identity_document_type } : {}),
                      ...(party.identity_document_number
                        ? { identity_document_number: party.identity_document_number }
                        : {}),
                    }),
                  "Buyer added.",
                );
              }}
            >
              <FormSection title="Add a named party" description="All active shares on a buyer must total 1.000000 before a unit can be committed.">
                <FieldRow columns={3}>
                  <Field label="Name as identification">
                    <input
                      className="input"
                      required
                      value={party.name_as_identification}
                      onChange={(event) => setParty({ ...party, name_as_identification: event.target.value })}
                    />
                  </Field>
                  <Field label="Share" hint="A fraction of one: 0.500000 for a half.">
                    <input
                      className="input figure"
                      inputMode="decimal"
                      required
                      value={party.share_fraction}
                      onChange={(event) => setParty({ ...party, share_fraction: event.target.value })}
                    />
                  </Field>
                  <Field label="Role">
                    <select
                      className="input"
                      value={party.party_role}
                      onChange={(event) => setParty({ ...party, party_role: event.target.value })}
                    >
                      <option value="purchaser">Purchaser</option>
                      <option value="joint_purchaser">Joint purchaser</option>
                    </select>
                  </Field>
                </FieldRow>
                <FieldRow columns={2}>
                  <Field label="Identity document type" optional>
                    <input
                      className="input"
                      value={party.identity_document_type}
                      onChange={(event) => setParty({ ...party, identity_document_type: event.target.value })}
                    />
                  </Field>
                  <Field label="Identity document number" optional>
                    <input
                      className="input"
                      value={party.identity_document_number}
                      onChange={(event) => setParty({ ...party, identity_document_number: event.target.value })}
                    />
                  </Field>
                </FieldRow>
              </FormSection>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  Add party
                </Button>
              </FormActions>
            </form>
          ) : null}
        </SubPanel>
      ) : null}
    </Card>
  );
}
