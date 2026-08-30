"use client";

/**
 * Which currency a `currency_id` names.
 *
 * The records that carry money — price versions, reservations, contracts, tax
 * lines, benchmarks — identify their denomination by currency id, and the
 * screens showing them need the code. The project workspace loads the currency
 * register once (any signed-in user may read it), seeds it with the project's
 * own base and reporting pair as a fallback, and provides the mapping here so
 * every screen resolves the row's REAL currency rather than assuming the
 * project's.
 *
 * An id the map cannot resolve yields no code: the figure is then shown
 * undenominated rather than labelled with a guess.
 */

import { createContext, useContext } from "react";
import type { ReactNode } from "react";

const CurrencyContext = createContext<Record<string, string>>({});

export function CurrencyProvider({
  codes,
  children,
}: {
  codes: Record<string, string>;
  children: ReactNode;
}) {
  return <CurrencyContext.Provider value={codes}>{children}</CurrencyContext.Provider>;
}

/** A resolver from currency id to code, or null where the id is unknown. */
export function useCurrencyCode(): (id: string | null | undefined) => string | null {
  const codes = useContext(CurrencyContext);
  return (id) => (id ? (codes[id] ?? null) : null);
}
