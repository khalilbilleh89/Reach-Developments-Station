"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, sales } from "@/lib/api";
import type { ClientParty, SalesClient } from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";
import { kycLabel } from "@/components/projects/sales/labels";

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
  onClose,
}: {
  projectId: string;
  canWrite: boolean;
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
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  };

  if (clients === null) return <Loading label="Loading buyers…" />;

  return (
    <Panel
      title="Buyers"
      description="Project-scoped. This is not a portfolio-wide customer master."
      actions={
        <button className="button button-small" type="button" onClick={onClose}>
          Close
        </button>
      }
    >
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}

      <div className="form-inline">
        <Field label="Search">
          <input
            className="input"
            value={search}
            placeholder="Name or client number"
            onChange={(event) => setSearch(event.target.value)}
          />
        </Field>
      </div>

      {clients.length === 0 ? (
        <EmptyState
          title="No buyers yet"
          hint={canWrite ? "Register one below." : "Nobody has been registered on this project."}
        />
      ) : (
        <div className="table-scroll">
          <table className="table">
            <caption className="visually-hidden">Buyers</caption>
            <thead>
              <tr>
                <th scope="col">Client</th>
                <th scope="col">Name</th>
                <th scope="col">Identity checks</th>
                <th scope="col">Contact</th>
                <th scope="col">Active</th>
                <th scope="col">Parties</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((client) => (
                <tr key={client.id}>
                  <th scope="row" className="mono">
                    {client.client_number}
                  </th>
                  <td>{client.display_name}</td>
                  <td>{kycLabel(client.kyc_status)}</td>
                  <td>
                    {"email" in client ? (
                      (client.email ?? client.phone ?? "—")
                    ) : (
                      <span className="subtle">Not shown to your role</span>
                    )}
                  </td>
                  <td>
                    {client.is_active ? (
                      <Badge tone="success">Active</Badge>
                    ) : (
                      <Badge tone="muted">Inactive</Badge>
                    )}
                  </td>
                  <td>
                    <button
                      className="button button-small"
                      type="button"
                      onClick={() => setSelected(selected === client.id ? null : client.id)}
                    >
                      {selected === client.id ? "Hide" : "Open"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected ? (
        <>
          <h3 className="section-heading">Buyer parties</h3>
          {shares !== null ? (
            <div className="chip-list">
              <span className="chip">Shares total {shares}</span>
              {shares === "1.000000" ? (
                <Badge tone="success">A whole unit</Badge>
              ) : (
                <Badge tone="muted">Not yet a whole unit</Badge>
              )}
            </div>
          ) : null}
          {parties.length === 0 ? (
            <EmptyState title="No parties recorded" />
          ) : (
            <div className="table-scroll">
              <table className="table">
                <caption className="visually-hidden">Buyer parties</caption>
                <thead>
                  <tr>
                    <th scope="col">Name as identification</th>
                    <th scope="col">Role</th>
                    <th scope="col">Share</th>
                    <th scope="col">Identity document</th>
                    <th scope="col">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {parties.map((item) => (
                    <tr key={item.id}>
                      <th scope="row">{item.name_as_identification}</th>
                      <td>{item.party_role === "purchaser" ? "Purchaser" : "Joint purchaser"}</td>
                      <td className="mono nowrap">{item.share_fraction}</td>
                      <td className="mono">
                        {"identity_document_number" in item ? (
                          `${item.identity_document_type ?? "—"} ${item.identity_document_number ?? ""}`
                        ) : (
                          <span className="subtle">Not shown to your role</span>
                        )}
                      </td>
                      <td>{item.is_active ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {canWrite ? (
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void run(
                  () =>
                    sales.createParty(projectId, selected, {
                      name_as_identification: party.name_as_identification,
                      share_fraction: party.share_fraction,
                      party_role: party.party_role,
                      ...(party.identity_document_type
                        ? { identity_document_type: party.identity_document_type }
                        : {}),
                      ...(party.identity_document_number
                        ? { identity_document_number: party.identity_document_number }
                        : {}),
                    }),
                  "Buyer added.",
                );
              }}
            >
              <Field label="Name as identification">
                <input
                  className="input"
                  required
                  value={party.name_as_identification}
                  onChange={(event) =>
                    setParty({ ...party, name_as_identification: event.target.value })
                  }
                />
              </Field>
              <Field label="Share" hint="0.500000 for a half. All active shares must total 1.000000.">
                <input
                  className="input"
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
              <Field label="Identity document type">
                <input
                  className="input"
                  value={party.identity_document_type}
                  onChange={(event) =>
                    setParty({ ...party, identity_document_type: event.target.value })
                  }
                />
              </Field>
              <Field label="Identity document number">
                <input
                  className="input"
                  value={party.identity_document_number}
                  onChange={(event) =>
                    setParty({ ...party, identity_document_number: event.target.value })
                  }
                />
              </Field>
              <div className="form-actions">
                <button className="button" type="submit" disabled={busy}>
                  Add buyer
                </button>
              </div>
            </form>
          ) : null}
        </>
      ) : null}

      {canWrite ? (
        <>
          <h3 className="section-heading">Register a buyer</h3>
          <form
            className="form-grid"
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
              );
            }}
          >
            <Field label="Display name">
              <input
                className="input"
                required
                value={form.display_name}
                onChange={(event) => setForm({ ...form, display_name: event.target.value })}
              />
            </Field>
            <Field label="Email">
              <input
                className="input"
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
              />
            </Field>
            <Field label="Phone">
              <input
                className="input"
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </Field>
            <div className="form-actions">
              <button className="button" type="submit" disabled={busy}>
                Register buyer
              </button>
            </div>
          </form>
          <p className="footnote">
            The client number is issued by the server. Identity is the stable identifier behind it,
            never the human reference.
          </p>
        </>
      ) : null}
    </Panel>
  );
}
