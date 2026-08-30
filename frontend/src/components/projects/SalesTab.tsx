"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, inventory, sales } from "@/lib/api";
import type { Phase, SalesClient, SalesPolicy, SalesRegister } from "@/lib/api";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  Field,
  FilterBar,
  FormActions,
  Loading,
  Notice,
  Stat,
  StatRow,
  SubPanel,
  TableScroll,
} from "@/components/ui";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { ClientsPanel } from "@/components/projects/sales/ClientsPanel";
import { DealFile } from "@/components/projects/sales/DealFile";
import {
  handoverLabel,
  handoverTone,
  legalEventLabel,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
} from "@/components/projects/sales/labels";

/**
 * The Sales workspace, inside the project.
 *
 * One register with one line per unit, showing where it stands commercially,
 * legally and on delivery — three answers from three teams, side by side and
 * never collapsed into "sold". Opening a line opens the deal file: the buyer,
 * the quote, the contract, the registry, the cancellation and the handover, all
 * on one record, because they are five records of one transaction.
 *
 * The totals come from the server and cover the whole authorised filtered set,
 * not the page on screen. Where a project's contracts are denominated in more
 * than one currency the value is withheld rather than added up: a sum of two
 * currencies is not a number, and this screen would rather show nothing than
 * something confident and wrong.
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
      <Card title="Sales" description="Not yet — the project basis is still open.">
        <EmptyState
          title="Finalize project setup"
          hint="Confirm country and currency settings, then move the project to Pre-development before recording sales."
        />
      </Card>
    );
  }

  if (error && register === null) {
    return (
      <Card title="Sales">
        <Notice tone="error">{error}</Notice>
      </Card>
    );
  }

  if (register === null) {
    return (
      <Card title="Sales">
        <Loading label="Loading sales…" lines={4} />
      </Card>
    );
  }

  const totals = register.totals;

  return (
    <>
      <Card
        title="Sales"
        description="Where every unit stands commercially, legally and on delivery."
        actions={
          <>
            <Button onClick={() => setOpen(open === "clients" ? "none" : "clients")}>
              {open === "clients" ? "Close buyers" : "Buyers"}
            </Button>
            {canSetPolicy ? (
              <Button onClick={() => setOpen(open === "policy" ? "none" : "policy")}>
                {open === "policy" ? "Close gates" : "Sales gates"}
              </Button>
            ) : null}
          </>
        }
      >
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        <StatRow>
          <Stat label="Units" value={totals.units} small />
          <Stat label="Available" value={totals.available} small />
          <Stat label="Live reservations" value={totals.active_reservations} small />
          <Stat label="Contract pending" value={totals.contract_pending} small />
          <Stat label="Contracted" value={totals.contracted} small />
          <Stat label="Returned" value={totals.returned} small />
          <Stat label="Open cancellations" value={totals.open_cancellations} small />
          <Stat
            label="Contracted value"
            value={
              totals.mixed_currency ? "Not summed" : (totals.contracted_value ?? "—")
            }
            note={totals.mixed_currency ? "Mixed currencies" : undefined}
          />
        </StatRow>
        <p className="footnote">
          Counted over every unit you may see under the current filter, not the page below.
        </p>
      </Card>

      {open === "clients" ? (
        <ClientsPanel
          projectId={projectId}
          canWrite={canWriteClients}
          onChanged={load}
          onClose={() => setOpen("none")}
        />
      ) : null}

      {open === "policy" && policy ? (
        <Card
          title="Sales gates"
          description="Six named choices. Not a rules engine, and never becoming one."
          actions={<Button onClick={() => setOpen("none")}>Close</Button>}
        >
          <form
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
                setError(caught instanceof ApiError ? caught.message : "Could not save the gates.");
              } finally {
                setBusy(false);
              }
            }}
          >
            <div className="checkbox-grid">
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
            </div>
            <FormActions>
              <Button variant="primary" type="submit" disabled={busy}>
                Save gates
              </Button>
            </FormActions>
          </form>
        </Card>
      ) : null}

      <Card
        title="Sales register"
        description="One line per unit. Three teams' answers, side by side."
      >
        <FilterBar>
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
        </FilterBar>

        {reserving ? (
          <SubPanel
            title={`Reserve ${reserving.reference}`}
            actions={<Button small onClick={() => setReserving(null)}>Cancel</Button>}
          >
            <p className="section-description">
              Creating a reservation holds nothing. The unit stays on the market until the
              reservation is activated.
            </p>
            <form
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
                    caught instanceof ApiError
                      ? caught.message
                      : "Could not open the reservation.",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              <div className="form-grid">
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
                      setReservation({
                        ...reservation,
                        deposit_required_amount: event.target.value,
                      })
                    }
                  />
                </Field>
                <FormActions>
                  <Button variant="primary" type="submit" disabled={busy}>
                    Open reservation
                  </Button>
                </FormActions>
              </div>
            </form>
          </SubPanel>
        ) : null}

        {register.rows.length === 0 ? (
          <EmptyState
            title="Nothing to show"
            hint="No unit in this project matches, or none is visible to you."
          />
        ) : (
          <TableScroll label="Sales register" fixedFirst>
            <thead>
              <tr>
                <th scope="col">Unit</th>
                <th scope="col">Commercial</th>
                <th scope="col">Buyer</th>
                <th scope="col">Reservation</th>
                <th scope="col">Expires</th>
                <th scope="col">SPA</th>
                <th scope="col">Contract</th>
                <th scope="col" className="num">
                  Contract price
                </th>
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
                      className="button-link mono"
                      type="button"
                      onClick={() => onOpenUnit(row.unit_id)}
                    >
                      {row.unit_reference}
                    </button>
                  </th>
                  <td>
                    <Badge tone={statusTone(row.commercial_status)}>
                      {statusLabel(row.commercial_status)}
                    </Badge>
                  </td>
                  <td>{row.client_display_name ?? "—"}</td>
                  <td className="nowrap">
                    <span className="mono">{row.reservation_number ?? "—"}</span>{" "}
                    {row.closure_required ? (
                      <Badge tone="danger">Closure required</Badge>
                    ) : row.reservation_status ? (
                      <Badge tone={reservationTone(row.reservation_status)}>
                        {reservationLabel(row.reservation_status)}
                      </Badge>
                    ) : null}
                  </td>
                  <td className="mono nowrap">{row.reservation_expires_on ?? "—"}</td>
                  <td className="mono">{row.spa_number ?? "—"}</td>
                  <td>
                    {row.sale_status ? (
                      <Badge tone={saleTone(row.sale_status)}>{saleLabel(row.sale_status)}</Badge>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="num">{row.total_contract_price ?? "—"}</td>
                  <td>
                    <Badge tone={statusTone(row.legal_status)}>
                      {statusLabel(row.legal_status)}
                    </Badge>
                  </td>
                  <td>{row.next_legal_step ? legalEventLabel(row.next_legal_step) : "—"}</td>
                  <td>
                    {row.handover_status ? (
                      <Badge tone={handoverTone(row.handover_status)}>
                        {handoverLabel(row.handover_status)}
                      </Badge>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    <Badge tone={statusTone(row.delivery_status)}>
                      {statusLabel(row.delivery_status)}
                    </Badge>
                  </td>
                  <td>
                    {row.reservation_id || row.sale_id ? (
                      <Button
                        small
                        onClick={() =>
                          setDeal({ reservationId: row.reservation_id, saleId: row.sale_id })
                        }
                      >
                        Deal file
                      </Button>
                    ) : canWriteClients && row.commercial_status === "available" ? (
                      <Button
                        small
                        onClick={() =>
                          setReserving({ unitId: row.unit_id, reference: row.unit_reference })
                        }
                      >
                        Reserve
                      </Button>
                    ) : (
                      <span className="subtle">No commitment</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </TableScroll>
        )}
      </Card>

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
