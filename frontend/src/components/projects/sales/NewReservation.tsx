"use client";

import { useId, useState } from "react";
import type { SalesUnitOption } from "@/lib/api";
import { Button, Card } from "@/components/ui";
import { money } from "@/lib/format";
import { useCurrencyCode } from "@/lib/currency";
import { RegisterBuyerSaleForm } from "./RegisterBuyerSaleForm";
import { ReservationForm } from "./ReservationForm";
import { SalesUnitPicker } from "./SalesUnitPicker";

export function NewReservation({projectId, onCreated, onSaleCreated, allowOwner, onCancel, clientId}: {
  clientId?: string;
  allowOwner: boolean; onSaleCreated: (id: string) => void;
  projectId: string; onCreated: (id: string) => void; onCancel: () => void;
}) {
  const id = useId();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [owner, setOwner] = useState(Boolean(clientId && allowOwner));
  const [selected, setSelected] = useState<SalesUnitOption | null>(null);
  const changeUnit = () => { setSelected(null); setPickerOpen(true); };
  const codeOf = useCurrencyCode();
  return <Card title={clientId ? "Connect buyer to unit" : "New Reservation"} description="Choose an available unit, agree the price and prepare the buyer’s reservation.">
    {!selected ? <SalesUnitPicker key={projectId} initiallyOpen={pickerOpen} projectId={projectId} onSelect={setSelected} onCancel={onCancel} /> : <>
      <div className="sales-unit-picker">
        <span className="field-label" id={`${id}-label`}>Unit</span>
        <button type="button" className="sales-unit-picker-trigger" data-leaves-editor autoFocus
          aria-labelledby={`${id}-label ${id}-value`} aria-expanded={false} onClick={changeUnit}>
          <span className="sales-unit-picker-details" id={`${id}-value`}>
            <strong>{[selected.unit_reference, selected.unit_type, selected.floor_name].filter(Boolean).join(" · ")}</strong>
            <span className="subtle">Inventory list price: {money(selected.reference_price_ex_tax, codeOf(selected.currency_id))} excluding tax</span>
          </span><span aria-hidden="true">▾</span>
        </button>
        <p className="subtle">{[selected.phase_name, selected.building_name, selected.gross_area === null ? null : `${selected.gross_area} ${selected.area_unit ?? ""}`].filter(Boolean).join(" · ")}</p>
      </div>
      {allowOwner ? <Button data-leaves-editor onClick={() => setOwner(!owner)}>{owner ? "Prepare standard reservation" : "Owner: register buyer & mark sold"}</Button> : null}
      {owner ? <RegisterBuyerSaleForm clientId={clientId} projectId={projectId} unitId={selected.unit_id} unitOption={selected} onSaved={onSaleCreated} onCancel={() => setOwner(false)} /> : <ReservationForm clientId={clientId} projectId={projectId} unitId={selected.unit_id} currencyId={selected.currency_id} unitOption={selected} onCreated={onCreated} onCancel={onCancel} onChangeUnit={changeUnit} />}
    </>}
  </Card>;
}
