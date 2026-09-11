"use client";

import { SalesHistory } from "./sales/SalesHistory";

import { RegisterPagination } from "@/components/ui";

import { useRegisterFields, useRegisterRestore } from "@/components/shell/registerState";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, inventory, sales } from "@/lib/api";
import type { Phase, SalesPolicy, SalesRegister } from "@/lib/api";
import { useCurrencyCode } from "@/lib/currency";
import { businessDate, money } from "@/lib/format";
import { sectionDescription } from "@/components/shell/navigation";
import {
  DraftBoundary,
  Badge,
  Button,
  Card,
  DataToolbar,
  Disclosure,
  IdentityCell,
  EmptyState,
  FormActions,
  Loading,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  Notice,
  PageHeader,
  StatusDot,
  TableScroll,
  ToolbarFilter,
} from "@/components/ui";
import { statusLabel, statusTone } from "@/components/projects/inventory/statusLabels";
import { ReservationForm } from "@/components/projects/sales/ReservationForm";
import { ClientsPanel } from "@/components/projects/sales/ClientsPanel";
import { RecordLink } from "@/components/ui";
import { useRouter } from "next/navigation";
import { useRecordHref } from "@/components/ui";
import {
  handoverLabel,
  handoverTone,
  legalEventLabel,
  reservationLabel,
  reservationTone,
  saleLabel,
  saleTone,
} from "@/components/projects/sales/labels";
import { restrictedToOwnClients } from "@/lib/roles";

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
  { name: "handover_requires_collection_clearance", label: "Handover needs the collections clearance" },
  { name: "handover_requires_delivery_clearance", label: "Handover needs the delivery clearance" },
  { name: "handover_requires_title_transfer", label: "Handover needs the title to have transferred" },
  {
    name: "title_transfer_requires_collection_clearance",
    label: "Title transfer needs the collections clearance",
  },
];

const COMMERCIAL_FILTERS = [
  "available",
  "reserved",
  "contract_pending",
  "contracted",
  "returned",
  "held",
  "unreleased",
];

export function SalesTab({
  projectId,
  projectStatus,
  roles,
  userId,
}: {
  projectId: string;
  projectStatus: string;
  roles: Set<string>;
  /** Who is reading, so an advisor is offered only the deals the server would open. */
  userId: string;
}) {
  const [workspace, setWorkspace] = useRegisterFields({ sales_view: "" });
  const history = workspace.sales_view === "history";
  const ownOnly = restrictedToOwnClients(roles);
  const [pageFields, setPageFields] = useRegisterFields({offset: ""});
  const parsedOffset = Number(pageFields.offset);
  const offset = Number.isSafeInteger(parsedOffset) && parsedOffset >= 0 ? parsedOffset : 0;
  const setOffset = (value: number) => setPageFields({offset: String(value)});
  const [pageTotal, setPageTotal] = useState(0);
  const [register, setRegister] = useState<SalesRegister | null>(null);
  useRegisterRestore(register !== null);
  const [phases, setPhases] = useState<Phase[]>([]);
  const [policy, setPolicy] = useState<SalesPolicy | null>(null);
  const [filters, updateFilters] = useRegisterFields({ phase_id: "", commercial_status: "" });
  const setFilters = (changes: Partial<typeof filters>) => { updateFilters(changes); setPageFields({offset: ""}); };
  const [searchFields, setSearchFields] = useRegisterFields({ search: "" });
  const search = searchFields.search;
  const setSearch = (search: string) => { setSearchFields({ search }); setPageFields({offset: ""}); };
  const [open, setOpen] = useState<"none" | "clients" | "policy">("none");
  const router = useRouter();
  const recordHref = useRecordHref(projectId);
  // Reserving is the one thing that starts at a unit rather than at a deal, so
  // it starts here: the register is where somebody is looking when they decide
  // to take a unit off the market.
  const [reserving, setReserving] = useState<{ unitId: string; reference: string; currencyId: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [auxError, setAuxError] = useState<string | null>(null);
  const [savedPolicy, setSavedPolicy] = useState<SalesPolicy | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const currencyCodeOf = useCurrencyCode();
  const canWriteClients = roles.has("sales_operations") || roles.has("sales_advisor");
  const canSetPolicy = roles.has("system_admin") || roles.has("project_manager");

  const policyDirty = useRef(false);
  useEffect(() => { policyDirty.current = JSON.stringify(policy) !== JSON.stringify(savedPolicy); }, [policy, savedPolicy]);
  const pageRequest = useRef(0);
  const load = useCallback(async () => {
    const ticket = ++pageRequest.current;
    setRegister(null);
    setError(null);
    try {
      const query: Record<string, string> = { limit: "200", offset: String(offset), search };
      for (const [key, value] of Object.entries(filters)) {
        if (value) query[key] = value;
      }
      const [registerResult, phaseResult, policyResult] = await Promise.allSettled([
        sales.register(projectId, query),
        inventory.phases(projectId),
        sales.policy(projectId),
      ]);
      if (ticket !== pageRequest.current) return;
      if (registerResult.status === "rejected") throw registerResult.reason;
      setRegister(registerResult.value);
      setPageTotal(registerResult.value.total);
      if (phaseResult.status === "fulfilled") setPhases(phaseResult.value);
      if (policyResult.status === "fulfilled") { if (!policyDirty.current) setPolicy(policyResult.value); setSavedPolicy(policyResult.value); }
      setAuxError(phaseResult.status === "rejected" || policyResult.status === "rejected" ? "Some sales filters or gates could not load." : null);
      setError(null);
    } catch (caught) {
      if (ticket !== pageRequest.current) return;
      setRegister(null);
      setError(caught instanceof ApiError ? caught.message : "Could not load sales.");
    }
  }, [projectId, filters, offset, search]);

  useEffect(() => {
    void (async () => {
      if (projectStatus !== "setup" && !history) await load();
    })();
  }, [load, projectStatus, history]);

  const header = (actions?: React.ReactNode) => (
    <PageHeader icon="sales" title="Sales" subtitle={sectionDescription("sales")} compact actions={<><Button data-leaves-editor onClick={() => setWorkspace({ sales_view: history ? "" : "history" })}>{history ? "Current sales" : "Transaction history"}</Button>{actions}</>} />
  );

  // Sales is refused while the project is in setup, because that is the window
  // in which its currency and country pack can still change under whatever was
  // agreed in them. Saying so beats a row of identical 409s.
  if (projectStatus === "setup") {
    return (
      <>
        {header()}
        <Card>
          <EmptyState
            title="Finalize project setup first"
            hint="Confirm country and currency settings, then move the project to Pre-development before recording sales."
          />
        </Card>
      </>
    );
  }

  if (history) return <>{header()}<SalesHistory projectId={projectId} /></>;

  if (error && register === null) {
    return (
      <>
        {header()}
        <Notice tone="error">{error}<Button onClick={() => void load()}>Retry</Button></Notice>
      </>
    );
  }

  const totals = register?.totals ?? null;
  const rows = register?.rows ?? [];
  const filtered = search !== "" || filters.phase_id !== "" || filters.commercial_status !== "";

  return (
    <>
      {header(
        <>
          <Button data-leaves-editor={open !== "none" || undefined} onClick={() => setOpen(open === "clients" ? "none" : "clients")} aria-expanded={open === "clients"}>
            Buyers
          </Button>
          {canSetPolicy ? (
            <Button data-leaves-editor={open !== "none" || undefined} onClick={() => setOpen(open === "policy" ? "none" : "policy")} aria-expanded={open === "policy"}>
              Sales gates
            </Button>
          ) : null}
        </>,
      )}

      <div className="stack">
        {error ? <Notice tone="error">{error}<Button onClick={() => void load()}>Retry</Button></Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}

        {/* The book, as a desk reads it: what has been agreed, what is being
            agreed, and what is still on the shelf. */}
        <div className="register-position"><Card
          tone={totals ? "command" : undefined}
          title="Commercial pipeline"
          description={totals ? "Authorized units and readable transactions matching the search and filters, across all pages." : undefined}
        >
          {totals === null ? (
            <Loading label="Loading sales…" shape="metrics" />
          ) : (
            <>
              <Position compact>
                <PositionFigure
                  lead
                  label="Contracted value"
                  value={
                    totals.mixed_currency
                      ? "Not summed"
                      : totals.currency_id === null
                        ? "No readable contract value"
                        : money(totals.contracted_value, currencyCodeOf(totals.currency_id))
                  }
                  note={totals.mixed_currency ? "Contracts in more than one currency" : "Live contracts, ex tax"}
                />
              </Position>
              <Disclosure title="Pipeline details" context={`Contracted: ${totals.contracted} of ${totals.units}`}>
              <Position compact>
                <PositionFigure
                  label="Contracted"
                  value={`${totals.contracted} of ${totals.units}`}
                  note="Units"
                />
                <PositionFigure label="Live reservations" value={totals.active_reservations} />
                <PositionFigure label="Available" value={totals.available} />
              </Position>
              <PositionSupport>
                <PositionSupportItem label="Contract pending" value={totals.contract_pending} />
                <PositionSupportItem label="Active contracts" value={totals.active_contracts} />
                <PositionSupportItem label="Returned" value={totals.returned} />
                <PositionSupportItem label="Open cancellations" value={totals.open_cancellations} />
              </PositionSupport>
              </Disclosure>
            </>
          )}
        </Card></div>

        {open === "clients" ? (
          <ClientsPanel projectId={projectId} canWrite={canWriteClients} onChanged={load} onClose={() => setOpen("none")} />
        ) : null}

        {auxError ? <Notice tone="error">{auxError}<Button onClick={() => void load()}>Retry sales filters and gates</Button></Notice> : null}
        {open === "policy" && policy ? (
          <DraftBoundary dirty={JSON.stringify(policy) !== JSON.stringify(savedPolicy)} busy={busy} onDiscard={() => setPolicy(savedPolicy)}><Card
            title="Sales gates"
            description="Choose the checks a sale must pass before activation."
            actions={<Button variant="quiet" data-leaves-editor onClick={() => setOpen("none")}>Close</Button>}
          >
            <form
              onSubmit={async (event) => {
                event.preventDefault();
                setBusy(true);
                try {
                  const saved = await sales.writePolicy(projectId, policy as unknown as Record<string, unknown>);
                  setPolicy(saved); setSavedPolicy(saved);
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
                      onChange={(event) => setPolicy({ ...policy, [entry.name]: event.target.checked })}
                    />
                    <span>{entry.label}</span>
                  </label>
                ))}
              </div>
              <FormActions>
                <Button variant="primary" type="submit" disabled={busy}>
                  Save gates
                </Button>
              </FormActions>
            </form>
          </Card></DraftBoundary>
        ) : null}

        {reserving ? (
          <Card
            title={`Reserve ${reserving.reference}`}
            description="Creating a reservation holds nothing. The unit stays on the market until the reservation is activated."
            actions={<Button variant="quiet" data-leaves-editor onClick={() => setReserving(null)}>Cancel</Button>}
          >
            <ReservationForm
              key={reserving.unitId}
              projectId={projectId} unitId={reserving.unitId} currencyId={reserving.currencyId}
              onCancel={() => setReserving(null)}
              onCreated={(reservationId) => {
                router.push(recordHref("reservation", reservationId));
                setReserving(null);
                void load();
              }}
            />
          </Card>
        ) : null}

        <DataToolbar
          framed
          activeSummary={[phases.find((phase) => phase.id === filters.phase_id)?.name, filters.commercial_status ? statusLabel(filters.commercial_status) : null, search ? `“${search}”` : null].filter(Boolean).join(" · ")}
          search={{ value: search, onChange: setSearch, placeholder: "Unit, buyer or contract", label: "Search all current sales" }}
          count={register ? { shown: rows.length, total: register.total, noun: "unit" } : undefined}
          onReset={
            filtered
              ? () => {
                  setSearch("");
                  setFilters({ phase_id: "", commercial_status: "" });
                }
              : undefined
          }
        >
          <ToolbarFilter label="Phase" active={filters.phase_id !== ""}>
            <select
              className="input"
              value={filters.phase_id}
              onChange={(event) => setFilters({ ...filters, phase_id: event.target.value })}
            >
              <option value="">Every phase</option>
              {phases.map((phase) => (
                <option key={phase.id} value={phase.id}>
                  {phase.code} — {phase.name}
                </option>
              ))}
            </select>
          </ToolbarFilter>
          <ToolbarFilter label="Commercial status" active={filters.commercial_status !== ""}>
            <select
              className="input"
              value={filters.commercial_status}
              onChange={(event) => setFilters({ ...filters, commercial_status: event.target.value })}
            >
              <option value="">Any status</option>
              {COMMERCIAL_FILTERS.map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
          </ToolbarFilter>
        </DataToolbar>

        <Card flush>
          {register === null ? (
            <Loading label="Loading the register…" shape="rows" rows={8} />
          ) : rows.length === 0 ? (
            <div className="card-body">
              <EmptyState
                title={filtered ? "No unit matches" : "Nothing to show"}
                hint={filtered ? "Widen the filter to see the rest." : "No unit in this project is visible to you yet."}
              />
            </div>
          ) : (
            <TableScroll label="Sales register" fixedFirst stickyHeader>
              <thead>
                <tr>
                  <th scope="col">Sale / reservation</th>
                  <th scope="col" className="num">
                    Contract price
                  </th>
                  <th scope="col">Commercial</th>
                  <th scope="col">Reservation</th>
                  <th scope="col">Contract</th>
                  <th scope="col">Legal</th>
                  <th scope="col">Next legal step</th>
                  <th scope="col">Handover</th>
                  <th scope="col">Delivery</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.unit_id}>
                    <th scope="row" className="sales-primary-cell">
                      {row.sale_id || row.reservation_id ? (
                        ownOnly && row.advisor_user_id !== userId ? (
                          <><IdentityCell icon="sales" name={row.spa_number ?? row.sale_number ?? row.reservation_number ?? "Transaction"} meta={row.client_display_name ?? undefined} /><span className="cell-secondary">Another advisor&rsquo;s buyer</span></>
                        ) : (
                          <RecordLink projectId={projectId} kind={row.sale_id ? "sale" : "reservation"} id={(row.sale_id ?? row.reservation_id)!}>
                            <IdentityCell icon="sales" name={`${row.sale_id ? "Open Sale" : "Open Reservation"} ${row.spa_number ?? row.sale_number ?? row.reservation_number ?? ""}`} meta={row.client_display_name ?? undefined} />
                          </RecordLink>
                        )
                      ) : (
                        <>
                          <IdentityCell icon="sales" name={row.unit_reference} meta={["reserved", "contract_pending", "contracted"].includes(row.commercial_status) ? "Transaction details unavailable" : "No current sale or reservation"} />
                          {canWriteClients && row.commercial_status === "available" ? (
                            <Button small onClick={() => setReserving({ unitId: row.unit_id, reference: row.unit_reference, currencyId: row.currency_id })}>Reserve {row.unit_reference}</Button>
                          ) : null}
                        </>
                      )}
                      <span className="cell-secondary"><RecordLink projectId={projectId} kind="unit" id={row.unit_id}>View unit {row.unit_reference}</RecordLink></span>
                    </th>
                    <td className="num">{money(row.total_contract_price, currencyCodeOf(row.currency_id))}</td>
                    <td>
                      <Badge tone={statusTone(row.commercial_status)}>{statusLabel(row.commercial_status)}</Badge>
                    </td>
                    <td>
                      {row.reservation_number ? (
                        <>
                          <span className="mono">{row.reservation_id && (!ownOnly || row.advisor_user_id === userId) ? <RecordLink projectId={projectId} kind="reservation" id={row.reservation_id}>{row.reservation_number}</RecordLink> : row.reservation_number}</span>
                          <span className="cell-secondary">
                            {row.closure_required ? (
                              <Badge tone="danger">Closure required</Badge>
                            ) : (
                              <StatusDot tone={reservationTone(row.reservation_status)}>
                                {reservationLabel(row.reservation_status)}
                                {row.reservation_expires_on ? ` · to ${businessDate(row.reservation_expires_on)}` : ""}
                              </StatusDot>
                            )}
                          </span>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      {row.sale_number ? (
                        <>
                          <span className="mono">{row.sale_id && (!ownOnly || row.advisor_user_id === userId) ? <RecordLink projectId={projectId} kind="sale" id={row.sale_id}>{row.spa_number ?? row.sale_number}</RecordLink> : row.spa_number ?? row.sale_number}</span>
                          <span className="cell-secondary">
                            <StatusDot tone={saleTone(row.sale_status)}>{saleLabel(row.sale_status)}</StatusDot>
                          </span>
                        </>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <StatusDot tone={statusTone(row.legal_status)}>{statusLabel(row.legal_status)}</StatusDot>
                    </td>
                    <td>{row.next_legal_step ? legalEventLabel(row.next_legal_step) : <span className="muted">—</span>}</td>
                    <td>
                      {row.handover_status ? (
                        <StatusDot tone={handoverTone(row.handover_status)}>{handoverLabel(row.handover_status)}</StatusDot>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td>
                      <StatusDot tone={statusTone(row.delivery_status)}>{statusLabel(row.delivery_status)}</StatusDot>
                    </td>
                  </tr>
                ))}
              </tbody>
            </TableScroll>
          )}
        </Card>
        {pageTotal > 0 || register ? <RegisterPagination offset={offset} total={pageTotal} busy={!register} onChange={setOffset} /> : null}
      </div>

    </>
  );
}
