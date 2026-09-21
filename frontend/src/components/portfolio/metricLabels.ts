/** Names shared by live positions and immutable historical documents. */
export const metricLabels: Record<string, string> = {
  contracted_value: "Active contracted value",
  confirmed_receipts: "Confirmed receipts",
  refunds: "Confirmed refunds (legacy)",
  refund_due: "Refund due",
  refund_confirmed: "Refund paid",
  refund_outstanding: "Refund still to pay",
  unapplied_cash: "Unapplied confirmed cash",
  overdue_outstanding: "Overdue outstanding",
  total_cash: "Total actual cash",
  restricted_cash: "Restricted cash",
  unrestricted_cash: "Unrestricted cash",
  forecast_peak_deficit: "Forecast peak deficit",
  construction_control_budget: "Construction control budget",
  construction_eac: "Construction EAC",
  construction_commitment: "Construction commitment (ex tax)",
  construction_paid: "Construction paid (gross)",
  land_acquisition: "Land acquisition",
  commission_released: "Released commissions (non-cash)",
};

export const metricLabel = (code: string) => metricLabels[code] ?? code.replaceAll("_", " ");
