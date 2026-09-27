"use client";

import { useEffect, useState } from "react";
import { ApiError, projects, settings } from "@/lib/api";
import type { CountryPack, Currency, ProjectDetail } from "@/lib/api";
import { Button, Field, FieldRow, FormDialog, Loading, Notice, RecordPage } from "@/components/ui";
import { EditForm, asValue } from "./EditForm";
import type { EditField } from "./EditForm";
import { PROJECT_STATUSES, projectStatusLabel } from "./projectStatus";

export function projectFields(project: ProjectDetail, packs: CountryPack[], currencies: Currency[]): EditField[] {
  const basis = project.status === "setup";
  return [
    { name: "code", label: "Project code", group: "Identity", hint: "Letters, digits, hyphen or underscore; 2 to 32 characters." },
    { name: "name", label: "Name", group: "Identity" },
    { name: "developer_entity", label: "Developer entity", group: "Identity" },
    { name: "project_type_code", label: "Project type", hint: "A configured code.", group: "Identity", width: "medium" },
    {
      name: "status",
      label: "Status",
      kind: "select",
      group: "Identity",
      options: PROJECT_STATUSES.filter(value => project.status === "setup" || value !== "setup").map((value) => ({ value, label: projectStatusLabel(value) })),
      // Setup is the opening state only: the backend refuses a return to it,
      // so it is not offered once the project has left it.
      hint: project.status === "setup" ? undefined : "A project cannot return to setup.",
    },
    { name: "country_pack_id", label: "Country configuration", group: "Financial basis", kind: "select", visible: basis,
      options: packs.filter(p => p.is_active || p.id === project.country_pack_id).map(p => ({ value: p.id, label: `${p.name} (${p.country_code})` })) },
    { name: "base_currency_id", label: "Base currency", group: "Financial basis", kind: "select", visible: basis,
      options: currencies.filter(c => c.is_active || c.id === project.base_currency_id).map(c => ({ value: c.id, label: `${c.code}${c.symbol ? ` (${c.symbol})` : ""} — ${c.name}` })) },
    { name: "reporting_currency_id", label: "Reporting currency", group: "Financial basis", kind: "select",
      options: currencies.filter(c => c.is_active || c.id === project.reporting_currency_id).map(c => ({ value: c.id, label: `${c.code}${c.symbol ? ` (${c.symbol})` : ""} — ${c.name}` })) },
    { name: "city", label: "City", group: "Location", width: "medium" },
    { name: "location", label: "Location", group: "Location" },
    { name: "latitude", label: "Latitude", kind: "number", hint: "Decimal degrees.", group: "Location" },
    { name: "longitude", label: "Longitude", kind: "number", group: "Location" },
    { name: "planned_start", label: "Planned start", kind: "date", group: "Programme" },
    { name: "planned_completion", label: "Planned completion", kind: "date", group: "Programme" },
    {
      name: "fiscal_year_start_month",
      label: "Fiscal year starts",
      kind: "number",
      hint: "Month number, 1 to 12.",
      group: "Financial basis",
    },
  ];
}

export function ProjectEdit({ project, canConfigure, onSaved, onClose }: {
  project: ProjectDetail; canConfigure: boolean; onSaved: () => Promise<void>; onClose: () => void;
}) {
  const [configuration, setConfiguration] = useState<{ packs: CountryPack[]; currencies: Currency[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [currencyDialog, setCurrencyDialog] = useState<"add" | "symbol" | null>(null);
  const [correcting, setCorrecting] = useState(false);
  const [deletingCurrency, setDeletingCurrency] = useState(false);
  const [deleteCurrencyId, setDeleteCurrencyId] = useState("");
  const [deleteReason, setDeleteReason] = useState("");
  const [targetCurrencyId, setTargetCurrencyId] = useState("");
  const [correctionReason, setCorrectionReason] = useState("");
  const [keepAmounts, setKeepAmounts] = useState(false);
  const [currencyForm, setCurrencyForm] = useState({ code: "", name: "", symbol: "", minor_units: "2" });
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    Promise.all([settings.countryPacks(), settings.currencies()]).then(([packs, currencies]) => {
      if (active) setConfiguration({ packs, currencies });
    }).catch(caught => {
      if (active) setError(caught instanceof ApiError ? caught.message : "Could not load country and currency options. Close and reopen the editor to retry.");
    });
    return () => { active = false; };
  }, []);
  const fields = configuration ? projectFields(project, configuration.packs, configuration.currencies) : [];
  const initial = Object.fromEntries(fields.map(field => [field.name, asValue(project[field.name as keyof ProjectDetail]) ]));
  const currentCurrency = configuration?.currencies.find(currency => currency.id === project.base_currency_id);
  const saveCurrency = async () => {
    setBusy(true);
    setError(null);
    try {
      if (currencyDialog === "add") {
        await settings.createCurrency({ code: currencyForm.code, name: currencyForm.name, symbol: currencyForm.symbol || null, minor_units: Number(currencyForm.minor_units) });
      } else if (currentCurrency) {
        await settings.updateCurrency(currentCurrency.id, { symbol: currencyForm.symbol || null });
      }
      const currencies = await settings.currencies();
      setConfiguration(current => current ? { ...current, currencies } : current);
      setCurrencyDialog(null);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not save the currency.");
    } finally {
      setBusy(false);
    }
  };
  const correctCurrency = async () => {
    setBusy(true);
    setError(null);
    try {
      await projects.correctCurrency(project.id, targetCurrencyId, correctionReason.trim());
      await onSaved();
      setCorrecting(false);
      setCorrectionReason("");
      setKeepAmounts(false);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not correct the base currency.");
    } finally {
      setBusy(false);
    }
  };
  const removeCurrency = async () => {
    setBusy(true);
    setError(null);
    try {
      await settings.deleteCurrency(deleteCurrencyId, deleteReason.trim());
      const currencies = await settings.currencies();
      setConfiguration(current => current ? { ...current, currencies } : current);
      setDeletingCurrency(false);
      setDeleteCurrencyId("");
      setDeleteReason("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not remove the currency.");
    } finally {
      setBusy(false);
    }
  };
  return <RecordPage title="Edit project" subtitle={project.name} onClose={onClose}>
    {!configuration ? (error ? <Notice tone="error">{error}</Notice> : <Loading label="Loading project options…" />) : <>
      {error && !currencyDialog && !correcting && !deletingCurrency ? <Notice tone="error">{error}</Notice> : null}
      <Notice tone="info">Reporting currency and currency symbols can be corrected at any project stage. Base currency: {project.base_currency_code}. A base currency correction keeps every recorded number unchanged and retains an audit trail. The country configuration remains fixed after setup.</Notice>
      {canConfigure ? <div className="button-row">
        <Button small onClick={() => { setCurrencyForm({ code: "", name: "", symbol: "", minor_units: "2" }); setCurrencyDialog("add"); }}>Add currency</Button>
        {currentCurrency ? <Button small onClick={() => { setCurrencyForm({ code: currentCurrency.code, name: currentCurrency.name, symbol: currentCurrency.symbol ?? "", minor_units: String(currentCurrency.minor_units) }); setCurrencyDialog("symbol"); }}>Edit {currentCurrency.code} symbol</Button> : null}
        <Button small onClick={() => { setDeleteCurrencyId(""); setDeleteReason(""); setError(null); setDeletingCurrency(true); }}>Remove unused currency</Button>
        {project.status !== "setup" ? <Button small onClick={() => { setTargetCurrencyId(""); setCorrectionReason(""); setKeepAmounts(false); setCorrecting(true); }}>Correct base currency</Button> : null}
      </div> : null}
      <EditForm key={project.base_currency_id} fields={fields} initial={initial} onCancel={onClose} onSave={async changes => {
        await projects.update(project.id, changes);
        await onSaved();
      }} />
      {currencyDialog ? <FormDialog title={currencyDialog === "add" ? "Add currency" : `Edit ${currentCurrency?.code} symbol`} description={currencyDialog === "symbol" ? "This symbol belongs to the shared currency and will change wherever that currency is shown." : "The new currency will be available to all projects."} confirmLabel="Save currency" busy={busy} disabled={currencyDialog === "add" && (!currencyForm.code || !currencyForm.name)} onCancel={() => setCurrencyDialog(null)} onSubmit={() => void saveCurrency()}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        {currencyDialog === "add" ? <FieldRow><Field label="Currency code"><input className="input input-short" maxLength={3} value={currencyForm.code} onChange={event => setCurrencyForm({ ...currencyForm, code: event.target.value })} /></Field><Field label="Name"><input className="input" value={currencyForm.name} onChange={event => setCurrencyForm({ ...currencyForm, name: event.target.value })} /></Field></FieldRow> : null}
        <Field label="Symbol" optional><input className="input input-short" maxLength={8} value={currencyForm.symbol} onChange={event => setCurrencyForm({ ...currencyForm, symbol: event.target.value })} /></Field>
        {currencyDialog === "add" ? <Field label="Minor units"><input className="input input-short" type="number" min={0} max={6} value={currencyForm.minor_units} onChange={event => setCurrencyForm({ ...currencyForm, minor_units: event.target.value })} /></Field> : null}
      </FormDialog> : null}
      {correcting ? <FormDialog title="Correct base currency" description={`All amounts currently recorded as ${project.base_currency_code} will keep their numeric values and be labeled with the new currency. The original denominations remain in the audit history.`} confirmLabel="Correct currency" busy={busy} disabled={!targetCurrencyId || correctionReason.trim().length < 8 || !keepAmounts} onCancel={() => setCorrecting(false)} onSubmit={() => void correctCurrency()}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="New base currency"><select className="input" value={targetCurrencyId} onChange={event => setTargetCurrencyId(event.target.value)}><option value="">Choose…</option>{configuration.currencies.filter(currency => currency.is_active && currency.id !== project.base_currency_id).map(currency => <option key={currency.id} value={currency.id}>{currency.code}{currency.symbol ? ` (${currency.symbol})` : ""} — {currency.name}</option>)}</select></Field>
        <Field label="Reason for correction"><textarea className="input" required minLength={8} maxLength={500} value={correctionReason} onChange={event => setCorrectionReason(event.target.value)} /></Field>
        <label className="project-currency-confirm"><input type="checkbox" checked={keepAmounts} onChange={event => setKeepAmounts(event.target.checked)} />Keep every recorded numeric amount unchanged</label>
      </FormDialog> : null}
      {deletingCurrency ? <FormDialog title="Remove unused currency" description="A currency can be removed only when no project or financial record uses it." confirmLabel="Remove currency" busy={busy} disabled={!deleteCurrencyId || deleteReason.trim().length < 8} onCancel={() => { setDeletingCurrency(false); setError(null); }} onSubmit={() => void removeCurrency()}>
        {error ? <Notice tone="error">{error}</Notice> : null}
        <Field label="Currency"><select className="input" value={deleteCurrencyId} onChange={event => setDeleteCurrencyId(event.target.value)}><option value="">Choose…</option>{configuration.currencies.filter(currency => currency.id !== project.base_currency_id && currency.id !== project.reporting_currency_id).map(currency => <option key={currency.id} value={currency.id}>{currency.code} — {currency.name}</option>)}</select></Field>
        <Field label="Reason for removal"><textarea className="input" required minLength={8} maxLength={500} value={deleteReason} onChange={event => setDeleteReason(event.target.value)} /></Field>
      </FormDialog> : null}
    </>}
  </RecordPage>;
}
