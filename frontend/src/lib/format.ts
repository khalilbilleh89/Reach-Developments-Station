/**
 * Presentation-only formatting for values the server has already computed.
 *
 * Money arrives as exact Decimal strings and stays a string end to end: the
 * helpers below group digits and attach the currency code without ever
 * constructing a JavaScript Number, because a float is an approximation and
 * nothing on a contract screen may be approximate. No arithmetic, no rounding,
 * no scale change, no currency conversion happens here or anywhere else in the
 * browser.
 */

/** `-?digits[.digits]` — the only shape the server sends for a decimal. */
const DECIMAL = /^(-?)(\d+)(\.\d+)?$/;

/**
 * Present a server decimal as money: `money("228000.00", "JOD")` is
 * `"JOD 228,000.00"`, and a negative amount keeps its sign after the code:
 * `"JOD -5,000.00"`. Every digit is the server's; only commas are added.
 *
 * With no code the figure is grouped but not denominated — used only where the
 * response genuinely establishes no currency. A value that is not a plain
 * decimal is returned untouched rather than mangled.
 */
export function money(
  value: string | null | undefined,
  code?: string | null,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const match = DECIMAL.exec(value);
  if (!match) return code ? `${code} ${value}` : value;
  const [, sign, integer, fraction] = match;
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const figure = `${sign}${grouped}${fraction ?? ""}`;
  return code ? `${code} ${figure}` : figure;
}

const MONTHS: Record<string, string> = {
  "01": "Jan",
  "02": "Feb",
  "03": "Mar",
  "04": "Apr",
  "05": "May",
  "06": "Jun",
  "07": "Jul",
  "08": "Aug",
  "09": "Sep",
  "10": "Oct",
  "11": "Nov",
  "12": "Dec",
};

/**
 * Present a business date: `businessDate("2026-08-30")` is `"30 Aug 2026"`.
 *
 * A business date is a calendar fact with no time and no timezone, so it is
 * never fed through `new Date(...)` — a Date would pin it to an instant and
 * could render it as the previous day in another timezone. The string is read
 * as calendar components and those components are formatted.
 *
 * For system timestamps (`created_at` and friends) use the timestamp treatment,
 * not this: a timestamp is an instant, and pretending it is a calendar date
 * loses the time and the timezone that make it one.
 */
export function businessDate(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  const name = MONTHS[month];
  if (!name) return value;
  return `${day.startsWith("0") ? day.slice(1) : day} ${name} ${year}`;
}

/**
 * Present a stored fraction as a percentage: `percent("0.055000")` is
 * `"5.5%"`. The decimal point is moved two places by string manipulation —
 * never by multiplying, because `0.145 * 100` is already not `14.5` in
 * floating point and a tax rate must not depend on how badly a float rounds.
 */
export function percent(fraction: string | null | undefined): string {
  if (fraction === null || fraction === undefined || fraction === "") return "—";
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(fraction);
  if (!match) return fraction;
  const [, sign, integer, decimals = ""] = match;
  const digits = integer + decimals;
  const point = integer.length + 2;
  const padded = digits.padEnd(point, "0");
  const whole = padded.slice(0, point).replace(/^0+(?=\d)/, "");
  const rest = padded.slice(point).replace(/0+$/, "");
  return `${sign}${whole}${rest ? `.${rest}` : ""}%`;
}

/**
 * Today, as the calendar date the person in front of the screen would name.
 *
 * `new Date().toISOString().slice(0, 10)` is the obvious way to do this and it
 * is wrong: `toISOString` converts to UTC first, so anyone east of Greenwich
 * late in the evening — or west of it early in the morning — gets yesterday or
 * tomorrow. For a business date that difference is not cosmetic; it is the
 * wrong day written onto a contractual record.
 *
 * The local components are read straight off the Date and padded, so the
 * result is the date on the wall behind the user.
 */
export function todayISO(): string {
  const now = new Date();
  const month = `${now.getMonth() + 1}`.padStart(2, "0");
  const day = `${now.getDate()}`.padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/**
 * Is this server decimal greater than zero?
 *
 * Needed because the browser has to decide whether to *offer* an action —
 * whether an instalment still has room, whether a receipt has cash left — and
 * `Number(value) > 0` would put a float in the path of a monetary decision.
 * The sign and the digits are read as text instead, so a value the server sent
 * exactly is judged exactly.
 *
 * This is a presentational predicate, not arithmetic. Whether the action then
 * succeeds is still the server's to decide, against the same figures under
 * lock; a stale screen offering a button is expected, and is refused with a
 * message that says what is actually left.
 */
export function isPositive(value: string | null | undefined): boolean {
  if (value === null || value === undefined || value === "") return false;
  const match = DECIMAL.exec(value);
  if (!match) return false;
  const [, sign, integer, fraction] = match;
  if (sign === "-") return false;
  return /[1-9]/.test(integer) || /[1-9]/.test(fraction ?? "");
}
