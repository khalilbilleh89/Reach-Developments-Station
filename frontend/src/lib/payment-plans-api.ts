/**
 * payment-plans-api.ts — centralized API wrapper for the payment plans and
 * collections UI.
 *
 * This module is the normalization boundary between the backend API contract
 * and the frontend UI model. Raw backend responses are composed and normalized
 * here so that components can rely on stable, UI-friendly types.
 *
 * No business logic calculations are performed here — all financial values
 * are sourced directly from the backend.
 *
 * Backend endpoints used:
 *   GET /projects                                          → project list
 *   GET /projects/{id}/units                               → unit list
 *   GET /units/{unitId}                                    → unit detail
 *   GET /sales/contracts?unit_id={unitId}                  → contract list
 *   GET /payment-plans/contracts/{contractId}/schedule     → payment schedule
 *   GET /collections/contracts/{contractId}/receivables    → receivables summary
 */

import { apiFetch, ApiError } from "./api-client";
import { getProjects as getProjectsRaw, getUnitsByProject, getUnitById } from "./units-api";
import type { Project } from "./units-types";
import type {
  CollectionSummary,
  InstallmentRow,
  OverdueInstallment,
  PaymentPlanDetail,
  PaymentPlanFiltersState,
  PaymentPlanListItem,
  ReceivableStatus,
} from "./payment-plans-types";

export { getProjectsRaw as getProjects };
export type { Project };

// ---------- Concurrency limiter ------------------------------------------

async function runWithConcurrencyLimit<T>(
  tasks: (() => Promise<T>)[],
  limit: number,
): Promise<T[]> {
  if (tasks.length === 0) return [];
  const results: T[] = Array(tasks.length).fill(undefined);
  let next = 0;

  async function worker(): Promise<void> {
    while (next < tasks.length) {
      const i = next++;
      results[i] = await tasks[i]();
    }
  }

  await Promise.all(
    Array.from({ length: Math.min(limit, tasks.length) }, worker),
  );
  return results;
}

const ENRICHMENT_CONCURRENCY = 5;

// ---------- Raw backend response types (internal) ------------------------

interface ContractItem {
  id: string;
  unit_id: string;
  buyer_id: string;
  reservation_id: string | null;
  contract_number: string;
  contract_date: string;
  contract_price: number;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface ContractListResponse {
  total: number;
  items: ContractItem[];
}

interface ScheduleItem {
  id: string;
  contract_id: string;
  template_id: string | null;
  installment_number: number;
  due_date: string;
  due_amount: number;
  status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

interface ScheduleListResponse {
  contract_id: string;
  items: ScheduleItem[];
  total: number;
  total_due: number;
}

interface ReceivableLine {
  schedule_id: string;
  installment_number: number;
  due_date: string;
  due_amount: number;
  total_received: number;
  outstanding_amount: number;
  receivable_status: ReceivableStatus;
}

interface ContractReceivablesResponse {
  contract_id: string;
  items: ReceivableLine[];
  total_due: number;
  total_received: number;
  total_outstanding: number;
}

// ---------- Error discrimination -----------------------------------------

function isNotFoundError(err: unknown): boolean {
  return err instanceof ApiError && err.status === 404;
}

// ---------- Internal helpers ---------------------------------------------

async function fetchContractsForUnit(unitId: string): Promise<ContractItem[]> {
  try {
    const data = await apiFetch<ContractListResponse>(
      `/sales/contracts?unit_id=${unitId}&limit=500`,
    );
    return data.items;
  } catch (err: unknown) {
    if (isNotFoundError(err)) return [];
    throw err;
  }
}

async function fetchSchedule(
  contractId: string,
): Promise<ScheduleListResponse | null> {
  try {
    return await apiFetch<ScheduleListResponse>(
      `/payment-plans/contracts/${contractId}/schedule`,
    );
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

async function fetchReceivables(
  contractId: string,
): Promise<ContractReceivablesResponse | null> {
  try {
    return await apiFetch<ContractReceivablesResponse>(
      `/collections/contracts/${contractId}/receivables`,
    );
  } catch (err: unknown) {
    if (isNotFoundError(err)) return null;
    throw err;
  }
}

/**
 * Derive days overdue for display purposes only.
 * Calculated from due date vs. current date — not an accounting truth.
 */
function daysOverdueFromDueDate(dueDate: string): number {
  const due = new Date(dueDate);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  due.setHours(0, 0, 0, 0);
  const diffMs = today.getTime() - due.getTime();
  return Math.max(0, Math.floor(diffMs / (1000 * 60 * 60 * 24)));
}

/**
 * Build installment rows by combining schedule items with receivable lines.
 * When receivables are available they are matched by installment number;
 * otherwise schedule-only rows are returned with zero collected amounts.
 */
function buildInstallmentRows(
  schedule: ScheduleListResponse,
  receivables: ContractReceivablesResponse | null,
): InstallmentRow[] {
  const receivableMap = new Map<number, ReceivableLine>();
  if (receivables) {
    for (const line of receivables.items) {
      receivableMap.set(line.installment_number, line);
    }
  }

  return schedule.items.map((item): InstallmentRow => {
    const receivable = receivableMap.get(item.installment_number);
    const collected = receivable ? receivable.total_received : 0;
    const outstanding = receivable ? receivable.outstanding_amount : item.due_amount;
    const status: ReceivableStatus = receivable
      ? receivable.receivable_status
      : (item.status as ReceivableStatus) ?? "pending";

    return {
      installmentNumber: item.installment_number,
      dueDate: String(item.due_date),
      scheduledAmount: item.due_amount,
      collectedAmount: collected,
      remainingAmount: outstanding,
      status,
    };
  });
}

/**
 * Build a collection summary from the receivables response.
 */
function buildCollectionSummary(
  contractId: string,
  receivables: ContractReceivablesResponse,
): CollectionSummary {
  const paidInstallments = receivables.items.filter(
    (r) => r.receivable_status === "paid",
  ).length;
  const overdueInstallments = receivables.items.filter(
    (r) => r.receivable_status === "overdue",
  ).length;

  return {
    contractId,
    totalDue: receivables.total_due,
    totalReceived: receivables.total_received,
    totalOutstanding: receivables.total_outstanding,
    paidInstallments,
    overdueInstallments,
    totalInstallments: receivables.items.length,
  };
}

/**
 * Build overdue installment entries from the receivables list.
 */
function buildOverdueInstallments(
  receivables: ContractReceivablesResponse,
): OverdueInstallment[] {
  return receivables.items
    .filter((r) => r.receivable_status === "overdue" && r.outstanding_amount > 0)
    .map((r): OverdueInstallment => ({
      installmentNumber: r.installment_number,
      dueDate: String(r.due_date),
      overdueAmount: r.outstanding_amount,
      daysOverdue: daysOverdueFromDueDate(String(r.due_date)),
    }))
    .sort((a, b) => a.dueDate.localeCompare(b.dueDate));
}

// ---------- Public query functions ---------------------------------------

/**
 * Fetch the payment plan list for a project.
 *
 * Loads all units for the project, finds their active/draft contracts, then
 * fetches receivables for each contract to build the queue items.
 *
 * Performance: concurrency-bounded to avoid request storms.
 */
export async function getPaymentPlans(
  projectId: string,
  projectName: string,
): Promise<PaymentPlanListItem[]> {
  const units = await getUnitsByProject(projectId);
  if (units.length === 0) return [];

  const tasks = units.map((unit) => async (): Promise<PaymentPlanListItem[]> => {
    const contracts = await fetchContractsForUnit(unit.id);
    if (contracts.length === 0) return [];

    const contractTasks = contracts
      .filter((c) => c.status === "active" || c.status === "draft")
      .map((contract) => async (): Promise<PaymentPlanListItem | null> => {
        const receivables = await fetchReceivables(contract.id);

        if (!receivables) {
          // Contract exists but no payment schedule/receivables yet
          return null;
        }

        const overdueItems = receivables.items.filter(
          (r) => r.receivable_status === "overdue",
        );
        const overdueAmount = overdueItems.reduce(
          (sum, r) => sum + r.outstanding_amount,
          0,
        );

        // Find next due date from items that are not yet paid
        const unpaid = receivables.items
          .filter((r) => r.receivable_status !== "paid")
          .sort((a, b) => String(a.due_date).localeCompare(String(b.due_date)));
        const nextDueDate = unpaid.length > 0 ? String(unpaid[0].due_date) : null;

        const collectionPercent =
          receivables.total_due > 0
            ? (receivables.total_received / receivables.total_due) * 100
            : 0;

        return {
          contractId: contract.id,
          contractNumber: contract.contract_number,
          contractPrice: contract.contract_price,
          contractStatus: contract.status,
          unitId: unit.id,
          unitNumber: unit.unit_number,
          project: projectName,
          totalCollected: receivables.total_received,
          totalOutstanding: receivables.total_outstanding,
          totalDue: receivables.total_due,
          nextDueDate,
          overdueAmount,
          overdueCount: overdueItems.length,
          collectionPercent,
        };
      });

    const results = await runWithConcurrencyLimit(contractTasks, 3);
    return results.filter((r): r is PaymentPlanListItem => r !== null);
  });

  const nestedResults = await runWithConcurrencyLimit(tasks, ENRICHMENT_CONCURRENCY);
  return nestedResults.flat();
}

/**
 * Fetch the full payment plan detail for a contract.
 *
 * Combines contract data, payment schedule, and receivables into a single
 * PaymentPlanDetail object for the contract-level detail page.
 */
export async function getContractPaymentPlan(
  contractId: string,
): Promise<PaymentPlanDetail> {
  // Fetch contract to get unit_id for unit detail
  const contractData = await apiFetch<ContractItem>(
    `/sales/contracts/${contractId}`,
  );

  const [unit, schedule, receivables] = await Promise.all([
    getUnitById(contractData.unit_id),
    fetchSchedule(contractId),
    fetchReceivables(contractId),
  ]);

  const installmentRows =
    schedule
      ? buildInstallmentRows(schedule, receivables)
      : [];

  const emptySummary: CollectionSummary = {
    contractId,
    totalDue: 0,
    totalReceived: 0,
    totalOutstanding: 0,
    paidInstallments: 0,
    overdueInstallments: 0,
    totalInstallments: 0,
  };

  const collectionSummary = receivables
    ? buildCollectionSummary(contractId, receivables)
    : emptySummary;

  const overdueInstallments = receivables
    ? buildOverdueInstallments(receivables)
    : [];

  return {
    contractId,
    contractNumber: contractData.contract_number,
    contractPrice: contractData.contract_price,
    contractStatus: contractData.status,
    contractDate: String(contractData.contract_date),
    unitId: unit.id,
    unitNumber: unit.unit_number,
    project: "",
    buyerId: contractData.buyer_id,
    schedule: installmentRows,
    collectionSummary,
    overdueInstallments,
  };
}

/**
 * Apply UI filter state to a list of payment plan items.
 * All filtering is client-side after the initial API fetch.
 */
export function filterPaymentPlans(
  items: PaymentPlanListItem[],
  filters: PaymentPlanFiltersState,
): PaymentPlanListItem[] {
  return items.filter((item) => {
    if (
      filters.collectionStatus === "has_overdue" &&
      item.overdueCount === 0
    ) {
      return false;
    }
    if (
      filters.collectionStatus === "fully_paid" &&
      item.totalOutstanding !== 0
    ) {
      return false;
    }
    if (
      filters.collectionStatus === "in_progress" &&
      (item.totalOutstanding === 0 || item.overdueCount > 0)
    ) {
      return false;
    }
    if (
      filters.contractStatus !== "" &&
      item.contractStatus !== filters.contractStatus
    ) {
      return false;
    }
    if (filters.minOutstanding !== "") {
      const min = parseFloat(filters.minOutstanding);
      if (!isNaN(min) && item.totalOutstanding < min) return false;
    }
    if (filters.maxOutstanding !== "") {
      const max = parseFloat(filters.maxOutstanding);
      if (!isNaN(max) && item.totalOutstanding > max) return false;
    }
    return true;
  });
}
