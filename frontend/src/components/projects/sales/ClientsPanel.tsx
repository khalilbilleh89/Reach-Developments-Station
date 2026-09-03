"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type { ClientParty, SalesClient } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
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
  projectId,
  canWrite,
  onChanged,
  onClose,
}: {
  projectId: string;
  canWrite: boolean;
  onChanged: () => Promise<void>;
  onClose: () => void;
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
  const [form, setForm] = useState({ display_name: "", email: "", phone: "" });
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
      description="Project-scoped. This is not a portfolio-wide customer master."
      actions={
        <>
          {canWrite ? (
            <Button variant="primary" small onClick={() => setRegistering((open) => !open)}>
              {registering ? "Cancel" : "Register a buyer"}
            </Button>
          ) : null}
          <Button variant="quiet" small onClick={onClose}>
            Close
          </Button>
        </>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      {canWrite && registering ? (
        <SubPanel title="Register a buyer">
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void run(
                () =>
                  sales.createClient(projectId, {
                    display_name: form.display_name,
                    ...(form.email ? { email: form.email } : {}),
                    ...(form.phone ? { phone: form.phone } : {}),
                  }),
                "Buyer registered. Add the named parties next.",
              ).then(() => {
                setRegistering(false);
                setForm({ display_name: "", email: "", phone: "" });
              });
            }}
          >
            <FieldRow columns={3}>
              <Field label="Display name">
                <input
                  className="input"
                  required
                  value={form.display_name}
                  onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                />
              </Field>
              <Field label="Email" optional>
                <input
                  className="input"
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                />
              </Field>
              <Field label="Phone" optional>
                <input
                  className="input"
                  value={form.phone}
                  onChange={(event) => setForm({ ...form, phone: event.target.value })}
                />
              </Field>
            </FieldRow>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                Register buyer
              </Button>
            </FormActions>
            <p className="footnote">
              The client number is issued by the server. Identity is the stable identifier behind
              it, never the human reference.
            </p>
          </form>
        </SubPanel>
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
                <td>{client.display_name}</td>
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
                <td>
                  <Button
                    small
                    variant="quiet"
                    aria-expanded={selected === client.id}
                    onClick={() => setSelected(selected === client.id ? null : client.id)}
                  >
                    {selected === client.id ? "Hide parties" : "Parties"}
                  </Button>
                </td>
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
