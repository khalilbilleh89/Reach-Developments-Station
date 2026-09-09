"use client";
import type { Reservation, SaleContract } from "@/lib/api";
import type { Answer } from "@/lib/answer";
import { CommitmentSnapshot } from "./UnitSummary";
export type Commitment = { reservation: Reservation | null; sale: { sale: SaleContract } | null };
export function UnitCommitment({ commercialStatus, answer }: { projectId: string; commercialStatus: string; answer: Answer<Commitment>; roles: Set<string> }) {
  return <section className="stack"><h2>Commercial commitment</h2><CommitmentSnapshot answer={answer} commercialStatus={commercialStatus} /></section>;
}
