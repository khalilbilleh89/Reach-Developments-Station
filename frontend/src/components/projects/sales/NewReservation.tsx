"use client";

import { useState } from "react";
import type { SalesUnitOption } from "@/lib/api";
import { Button, Card } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { RegisterBuyerSaleForm } from "./RegisterBuyerSaleForm";
import { ReservationForm } from "./ReservationForm";
import { SalesUnitPicker } from "./SalesUnitPicker";

export function NewReservation({projectId, onCreated, onSaleCreated, allowOwner, onCancel}: {
  allowOwner: boolean; onSaleCreated: (id: string) => void;
  projectId: string; onCreated: (id: string) => void; onCancel: () => void;
}) {
  const [owner, setOwner] = useState(false);
  const [selected, setSelected] = useState<SalesUnitOption | null>(null);
  const codeOf = useCurrencyCode();
  return <Card title="New Reservation" description="Choose an available unit, agree the price and prepare the buyer’s reservation.">
    {!selected ? <SalesUnitPicker projectId={projectId} onSelect={setSelected} onCancel={onCancel} /> : <>
      <p><strong>{selected.unit_reference}</strong> · {selected.building_name} · {selected.floor_name}</p>
      <p className="subtle">{selected.unit_type ?? "Unit type not recorded"} · {selected.gross_area === null ? "Gross area not confirmed" : `${selected.gross_area} ${selected.area_unit ?? ""}`}</p>
      <p className="subtle">Inventory list price: {money(selected.reference_price_ex_tax, codeOf(selected.currency_id))} excluding tax</p>
      {allowOwner ? <Button data-leaves-editor onClick={() => setOwner(!owner)}>{owner ? "Prepare standard reservation" : "Owner: register buyer & mark sold"}</Button> : null}
      {owner ? <RegisterBuyerSaleForm projectId={projectId} unitId={selected.unit_id} unitOption={selected} onSaved={onSaleCreated} onCancel={() => setOwner(false)} /> : <ReservationForm projectId={projectId} unitId={selected.unit_id} currencyId={selected.currency_id} unitOption={selected} onCreated={onCreated} onCancel={onCancel} onChangeUnit={() => {setSelected(null);}} />}
    </>}
  </Card>;
}
