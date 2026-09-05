/**
 * The role sets the interface uses to decide what is worth showing.
 *
 * Each set mirrors a `frozenset` in the backend's `permissions.py` for the
 * same module, and is named after the same question: who may read this, who
 * may prepare it, who may sanction it. They are affordances, never security.
 * A navigation item is hidden from a role because the server would refuse
 * every request behind it, and offering a screen that always fails is worse
 * than offering none — but the server checks again on every call regardless
 * of what was on screen.
 *
 * Kept in one file so that a role is never spelled two ways in two screens,
 * and so that the one thing a reviewer has to compare against the backend is
 * short.
 */

export type Roles = ReadonlySet<string>;

export const ROLE_SYSTEM_ADMIN = "system_admin";

/** Roles that may change project identity and the land record. */
export const PROJECT_WRITERS: Roles = new Set([
  "system_admin",
  "project_manager",
]);

/** Roles that may maintain planning, permits and document references. */
export const TECHNICAL_WRITERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "design_engineering",
]);

/** Roles cleared to see development cost: land price and permit fees. */
export const PROJECT_FINANCIAL_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Roles that may prepare pricing: build a policy, price units, submit. */
export const PRICING_WRITERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
]);

/**
 * The one role that may sanction a price. Deliberately not the administrator:
 * configuring a system is not the authority to approve what it charges.
 */
export const PRICING_APPROVERS: Roles = new Set(["approver_cfo"]);

/**
 * Roles that may read a unit's live list price at all. The internal readers
 * below, plus the two sales roles that quote from it all day. Mirrors the
 * union of the backend's INTERNAL_PRICE_ROLES and QUOTE_PREVIEW_ROLES: a role
 * outside it — Legal, Collections — is refused the price, so the browser does
 * not ask.
 */
export const LIST_PRICE_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
  "sales_operations",
  "sales_advisor",
]);

/** Roles that may see anything other than the live list price. */
export const INTERNAL_PRICE_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Roles that may open the sales workspace. Everyone with a stake in a sale. */
export const SALES_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "sales_operations",
  "sales_advisor",
  "legal",
  "collections",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Roles that may read a payment schedule, and the same set for the cash against it. */
export const PLAN_READERS: Roles = SALES_READERS;
export const COLLECTION_READERS: Roles = SALES_READERS;

/**
 * Roles that may read what the build costs the developer.
 *
 * Design / Engineering is here and is deliberately absent from
 * `ECONOMICS_READERS`: the people running the build need the build's cost, and
 * do not need the margin a unit earns. Sales, Legal and Collections are absent
 * from both — each can already see the unit and in some cases the contract, and
 * an advisor who knows what a unit cost to build has an argument for a discount
 * the company never agreed to make available.
 *
 * This mirrors `CONSTRUCTION_READER_ROLES` on the server. It decides which door
 * is drawn, not who gets in: every request is authorised again server-side.
 */
export const CONSTRUCTION_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "design_engineering",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Roles that may read unit cost, margin and the allocation basis behind them. */
export const ECONOMICS_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/**
 * Roles that may read the project's cash: what it holds, expects and must raise.
 *
 * Mirrors `CASHFLOW_READER_ROLES` on the server. Collections is deliberately
 * absent and is the one omission worth explaining: it keeps every collections
 * surface it has, because chasing a buyer needs that buyer's ledger — and does
 * not need the project's development spend, its equity return or the month it
 * runs short of cash. Sales, Legal and Design / Engineering are absent for the
 * same reason in the other direction: none of them acts on a bank balance.
 */
export const CASHFLOW_READERS: Roles = new Set([
  "system_admin",
  "project_manager",
  "finance",
  "approver_cfo",
  "executive_viewer",
  "auditor",
]);

/** Roles that may prepare a cashflow forecast and record the cash this module owns. */
export const CASHFLOW_PREPARERS: Roles = new Set([
  "finance",
  "project_manager",
]);

/** Roles that may record a movement, a restriction or a release. Finance alone. */
export const CASHFLOW_RECORDERS: Roles = new Set(["finance"]);

/**
 * Roles that may confirm somebody else's movement — the second pair of eyes.
 *
 * Being in this set is not permission to confirm a particular row: the server
 * compares the confirmer against the recorder by user identifier, so one person
 * holding both Finance and Approver / CFO is still one person and is refused.
 */
export const CASHFLOW_CONFIRMERS: Roles = new Set(["finance", "approver_cfo"]);

/** The one role that may sanction a cashflow forecast. */
export const CASHFLOW_APPROVERS: Roles = new Set(["approver_cfo"]);

/** Roles that may put an approved forecast in force. */
export const CASHFLOW_ACTIVATORS: Roles = new Set(["finance", "approver_cfo"]);

/** Roles that may read the audit history. */
export const AUDIT_READERS: Roles = new Set(["system_admin", "auditor"]);

/**
 * Whether this person sees only their own buyers.
 *
 * Mirrors the backend's `restricts_clients_to_own`: true for a Sales Advisor
 * who is nothing else. An advisor who is also Sales Operations is doing the
 * desk's job and sees the desk's book. Used to offer a deal file only where
 * the server would open it, so a register never offers a record that answers
 * "not found".
 */
export function restrictedToOwnClients(roles: Roles): boolean {
  const wider = [
    "system_admin",
    "project_manager",
    "sales_operations",
    "legal",
    "collections",
    "finance",
    "approver_cfo",
    "executive_viewer",
    "auditor",
  ];
  if (wider.some((role) => roles.has(role))) return false;
  return roles.has("sales_advisor");
}

/** Whether the person holds at least one of the roles named. */
export function hasAnyRole(roles: Roles, allowed: Roles): boolean {
  for (const role of roles) if (allowed.has(role)) return true;
  return false;
}

/** The person's roles as a set, from the session's list of role objects. */
export function roleSet(roles: { key: string }[]): Set<string> {
  return new Set(roles.map((role) => role.key));
}
