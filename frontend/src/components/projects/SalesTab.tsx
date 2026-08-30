"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory, sales } from "@/lib/api";
import type { Phase, SalesClient, SalesPolicy, SalesRegister } from "@/lib/api";
import { Badge, EmptyState, Field, Loading, Notice, Panel } from "@/components/ui";
import { statusLabel } from "@/components/projects/inventory/statusLabels";
import { ClientsPanel } from "@/components/projects/sales/ClientsPanel";
import { DealFile } from "@/components/projects/sales/DealFile";
import {
  handoverLabel,
  legalEventLabel,
  reservationLabel,
  saleLabel,
} from "@/components/projects/sales/labels";

/**
 * The Sales workspace, inside the project.
 *
 * One register with one line per unit, showing where it stands commercially,
 * legally and on delivery — three answers from three teams, side by side and
 * never collapsed into "sold". Opening a line opens the deal file: the buyer,
 * the quote, the contract, the registry, the cancellation and the handover, all
 * on one screen, because they are five records of one transaction.
 *
 * The totals come from the server and cover the whole authorised filtered set,
 * not the page on screen. Where a project's contracts are denominated in more
 * than one currency the value is withheld rather than added up: a sum of two
 * currencies is not a number.
 */

const POLICY_FIELDS: { name: keyof SalesPolicy; label: string; hint?: string }[] = [
  {
    name: "reservation_requires_deposit_confirmation",
    label: "A reservation needs deposit evidence before it commits the unit",
  },
  { name: "handover_requires_legal_clearance", label: "Handover needs the legal clearance" },
  {
    name: "handover_requires_collection_clearance",
    label: "Handover needs the collections clearance",
  },
  { name: "handover_requires_delivery_clearance", label: "Handover needs the delivery clearance" },
  {
    name: "handover_requires_title_transfer",
    label: "Handover needs the title to have transferred",
  },
  {
    name: "title_transfer_requires_collection_clearance",
    label: "Title transfer needs the collections clearance",
    hint: "Attested by Collections until PR-MVP-07 has real payment truth behind it.",
  },
];

export function SalesTab({
  projectId,
  projectStatus,
  roles,
  onOpenUnit,
}: {
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
  onOpenUnit: (unitId: string) => void;
}) {
  const [register, setRegister] = useState<SalesRegister | null>(null);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [policy, setPolicy] = useState<SalesPolicy | null>(null);
  const [filters, setFilters] = useState({ phase_id: "", commercial_status: "" });
  const [open, setOpen] = useState<"none" | "clients" | "policy">("none");
  const [deal, setDeal] = useState<{ reservationId: string | null; saleId: string | null } | null>(
    null,
  );
  // Reserving is the one thing that starts at a unit rather than at a deal, so
  // it starts here: the register is where somebody is looking when they decide
  // to take a unit off the market.
  const [reserving, setReserving] = useState<{ unitId: string; reference: string } | null>(null);
  const [buyers, setBuyers] = useState<SalesClient[]>([]);
  const [reservation, setReservation] = useState({
    client_id: "",
    sales_channel_code: "",
    sales_branch_code: "",
    deposit_required_amount: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const canWriteClients = roles.has("sales_operations") || roles.has("sales_advisor");
  const canSetPolicy = roles.has("system_admin") || roles.has("project_manager");

  const load = useCallback(async () => {
    try {
      const query: Record<string, string> = { limit: "100" };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const [rows, phaseList, policyRow] = await Promise.all([
        sales.register(projectId, query),
        inventory.phases(projectId),
        sales.policy(projectId),
      ]);
      setRegister(rows);
      setPhases(phaseList);
      setPolicy(policyRow);
      // Allowed to fail quietly: a reader who may see the register is not
      // always entitled to the buyer list, and that should not blank the page.
      try {
        setBuyers(await sales.clients(projectId, { is_active: "true" }));
      } catch {
        setBuyers([]);
      }
      setError(null);
    } catch (caught) {
      setRegister(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load sales.");
    }
  }, [projectId, filters]);

  useEffect(() => {
    void (async () => {
      await load();
    })();
  }, [load]);

  // Sales is refused while the project is in setup, because that is the window
  // in which its currency and country pack can still change under whatever was
  // agreed in them. Saying so beats a row of identical 409s.
  if (projectStatus === "setup") {
    return (
      <Panel title="Sales" description="Not yet — the project basis is still open.">
        <EmptyState
          title="Finalize project setup"
          hint="Confirm country and currency settings, then move the project to
                Pre-development before recording sales."
        />
      </Panel>
    );
  }

  if (error && register === null) {
    return (
      <Panel title="Sales">
        <Notice tone="error">{error}</Notice>
      </Panel>
    );
  }

  if (register === null) return <Loading label="Loading sales…" />;

  const totals = register.totals;

  return (
    <>
      <Panel
        title="Sales"
        description="Where every unit stands commercially, legally and on delivery."
        actions={
          <>
            <button
              className="button button-small"
              type="button"
              onClick={() => setOpen(open === "clients" ? "none" : "clients")}
            >
              {open === "clients" ? "Close buyers" : "Buyers"}
            </button>
            {canSetPolicy ? (
              <button
                className="button button-small"
                type="button"
                onClick={() => setOpen(open === "policy" ? "none" : "policy")}
              >
                {open === "policy" ? "Close gates" : "Sales gates"}
              </button>
            ) : null}
          </>
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <dl className="reference-list">
          <div>
            <dt className="reference-term">Units</dt>
            <dd className="reference-value">{totals.units}</dd>
          </div>
          <div>
            <dt className="reference-term">Available</dt>
            <dd className="reference-value">{totals.available}</dd>
          </div>
          <div>
            <dt className="reference-term">Live reservations</dt>
            <dd className="reference-value">{totals.active_reservations}</dd>
          </div>
          <div>
            <dt className="reference-term">Contract pending</dt>
            <dd className="reference-value">{totals.contract_pending}</dd>
          </div>
          <div>
            <dt className="reference-term">Contracted</dt>
            <dd className="reference-value">{totals.contracted}</dd>
          </div>
          <div>
            <dt className="reference-term">Returned</dt>
            <dd className="reference-value">{totals.returned}</dd>
          </div>
          <div>
            <dt className="reference-term">Open cancellations</dt>
            <dd className="reference-value">{totals.open_cancellations}</dd>
          </div>
          <div>
            <dt className="reference-term">Contracted value</dt>
            <dd className="reference-value mono nowrap">
              {totals.mixed_currency
                ? "Mixed currencies — not summed"
                : (totals.contracted_value ?? "—")}
            </dd>
          </div>
        </dl>
        <p className="footnote">
          Counted over every unit you may see under the current filter, not the page below.
        </p>

        <div className="form-inline">
          <Field label="Phase">
            <select
              className="input"
              value={filters.phase_id}
              onChange={(event) => setFilters({ ...filters, phase_id: event.target.value })}
            >
              <option value="">Every phase</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Commercial status">
            <select
              className="input"
              value={filters.commercial_status}
              onChange={(event) =>
                setFilters({ ...filters, commercial_status: event.target.value })
              }
            >
              <option value="">Any</option>
              {[
                "available",
                "reserved",
                "contract_pending",
                "contracted",
                "returned",
                "held",
                "unreleased",
              ].map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
          </Field>
        </div>

        {register.rows.length === 0 ? (
          <EmptyState
            title="Nothing to show"
            hint="No unit in this project matches, or none is visible to you."
          />
        ) : (
          <div className="table-scroll">
            <table className="table">
              <caption className="visually-hidden">Sales register</caption>
              <thead>
                <tr>
                  <th scope="col">Unit</th>
                  <th scope="col">Commercial</th>
                  <th scope="col">Buyer</th>
                  <th scope="col">Reservation</th>
                  <th scope="col">Expires</th>
                  <th scope="col">SPA</th>
                  <th scope="col">Contract</th>
                  <th scope="col">Contract price</th>
                  <th scope="col">Legal</th>
                  <th scope="col">Next legal step</th>
                  <th scope="col">Handover</th>
                  <th scope="col">Delivery</th>
                  <th scope="col">Open</th>
                </tr>
              </thead>
              <tbody>
                {register.rows.map((row) => (
                  <tr key={row.unit_id}>
                    <th scope="row">
                      <button
                        className="button button-small"
                        type="button"
                        onClick={() => onOpenUnit(row.unit_id)}
                      >
                        {row.unit_reference}
                      </button>
                    </th>
                    <td>{statusLabel(row.commercial_status)}</td>
                    <td>{row.client_display_name ?? "—"}</td>
                    <td>
                      {row.reservation_number ?? "—"}
                      {row.closure_required ? (
                        <>
                          {" "}
                          <Badge tone="muted">Closure required</Badge>
                        </>
                      ) : row.reservation_status ? (
                        <>
                          {" "}
                          <span className="subtle">
                            {reservationLabel(row.reservation_status)}
                          </span>
                        </>
                      ) : null}
                    </td>
                    <td className="nowrap">{row.reservation_expires_on ?? "—"}</td>
                    <td>{row.spa_number ?? "—"}</td>
                    <td>{row.sale_status ? saleLabel(row.sale_status) : "—"}</td>
                    <td className="mono nowrap">{row.total_contract_price ?? "—"}</td>
                    <td>{statusLabel(row.legal_status)}</td>
                    <td>{row.next_legal_step ? legalEventLabel(row.next_legal_step) : "—"}</td>
                    <td>{row.handover_status ? handoverLabel(row.handover_status) : "—"}</td>
                    <td>{statusLabel(row.delivery_status)}</td>
                    <td>
                      {row.reservation_id || row.sale_id ? (
                        <button
                          className="button button-small"
                          type="button"
                          onClick={() =>
                            setDeal({
                              reservationId: row.reservation_id,
                              saleId: row.sale_id,
                            })
                          }
                        >
                          Deal file
                        </button>
                      ) : canWriteClients && row.commercial_status === "available" ? (
                        <button
                          className="button button-small"
                          type="button"
                          onClick={() =>
                            setReserving({
                              unitId: row.unit_id,
                              reference: row.unit_reference,
                            })
                          }
                        >
                          Reserve
                        </button>
                      ) : (
                        <span className="subtle">No commitment</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {open === "clients" ? (
        <ClientsPanel
          projectId={projectId}
          canWrite={canWriteClients}
          onChanged={load}
          onClose={() => setOpen("none")}
        />
      ) : null}

      {open === "policy" && policy ? (
        <Panel
          title="Sales gates"
          description="Six named choices. Not a rules engine, and never becoming one."
          actions={
            <button className="button button-small" type="button" onClick={() => setOpen("none")}>
              Close
            </button>
          }
        >
          <form
            className="checkbox-grid"
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              try {
                setPolicy(
                  await sales.writePolicy(projectId, policy as unknown as Record<string, unknown>),
                );
                setNotice("Gates saved.");
                setError(null);
              } catch (caught) {
                setError(
                  caught instanceof ApiError ? caught.message : "Could not save the gates.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            {POLICY_FIELDS.map((entry) => (
              <label className="checkbox" key={entry.name}>
                <input
                  type="checkbox"
                  checked={Boolean(policy[entry.name])}
                  onChange={(event) =>
                    setPolicy({ ...policy, [entry.name]: event.target.checked })
                  }
                />
                <span>
                  {entry.label}
                  {entry.hint ? <span className="field-hint"> {entry.hint}</span> : null}
                </span>
              </label>
            ))}
            <div className="form-actions">
              <button className="button button-primary" type="submit" disabled={busy}>
                Save gates
              </button>
            </div>
          </form>
        </Panel>
      ) : null}

      {reserving ? (
        <Panel
          title={`Reserve ${reserving.reference}`}
          description="Creating a reservation holds nothing. The unit stays on the market until it is activated."
          actions={
            <button
              className="button button-small"
              type="button"
              onClick={() => setReserving(null)}
            >
              Cancel
            </button>
          }
        >
          <form
            className="form-grid"
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setError(null);
              try {
                const created = await sales.createReservation(projectId, {
                  unit_id: reserving.unitId,
                  client_id: reservation.client_id,
                  ...(reservation.sales_channel_code
                    ? { sales_channel_code: reservation.sales_channel_code }
                    : {}),
                  ...(reservation.sales_branch_code
                    ? { sales_branch_code: reservation.sales_branch_code }
                    : {}),
                  ...(reservation.deposit_required_amount
                    ? { deposit_required_amount: reservation.deposit_required_amount }
                    : {}),
                });
                setReserving(null);
                setNotice(
                  `${created.reservation.reservation_number} prepared at the unit's live price.`,
                );
                setDeal({ reservationId: created.reservation.id, saleId: null });
                await load();
              } catch (caught) {
                setError(
                  caught instanceof ApiError ? caught.message : "Could not open the reservation.",
                );
              } finally {
                setBusy(false);
              }
            }}
          >
            <Field label="Buyer">
              <select
                className="input"
                required
                value={reservation.client_id}
                onChange={(event) =>
                  setReservation({ ...reservation, client_id: event.target.value })
                }
              >
                <option value="">Choose a buyer</option>
                {buyers.map((buyer) => (
                  <option key={buyer.id} value={buyer.id}>
                    {buyer.client_number} · {buyer.display_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Sales channel">
              <input
                className="input"
                value={reservation.sales_channel_code}
                onChange={(event) =>
                  setReservation({ ...reservation, sales_channel_code: event.target.value })
                }
              />
            </Field>
            <Field label="Sales branch">
              <input
                className="input"
                value={reservation.sales_branch_code}
                onChange={(event) =>
                  setReservation({ ...reservation, sales_branch_code: event.target.value })
                }
              />
            </Field>
            <Field
              label="Deposit required"
              hint="The gate amount. Recording evidence against it is not a receipt."
            >
              <input
                className="input"
                value={reservation.deposit_required_amount}
                onChange={(event) =>
                  setReservation({ ...reservation, deposit_required_amount: event.target.value })
                }
              />
            </Field>
            <div className="form-actions">
              <button className="button button-primary" type="submit" disabled={busy}>
                Open reservation
              </button>
            </div>
          </form>
        </Panel>
      ) : null}

      {deal ? (
        <DealFile
          projectId={projectId}
          reservationId={deal.reservationId}
          saleId={deal.saleId}
          roles={roles}
          onClose={() => setDeal(null)}
          onChanged={load}
        />
      ) : null}
    </>
  );
}
