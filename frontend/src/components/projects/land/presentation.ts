/** Group a recorded measurement without rounding or converting its units. */
export function measurement(value: string | null | undefined, unit?: string): string {
  if (value === null || value === undefined || value === "") return "Not recorded";
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return unit ? `${value} ${unit}` : value;
  const [, sign, integer, fraction = ""] = match;
  const decimals = fraction.replace(/0+$/, "");
  const figure = `${sign}${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}${decimals ? `.${decimals}` : ""}`;
  return unit ? `${figure} ${unit}` : figure;
}
