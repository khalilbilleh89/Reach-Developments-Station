# VAT / Tax per installment

Owner amendment, 2026-09-12. Governed by ENGINEERING_RULES.md.

In the full-page Payment Plan editor, choose **VAT / Tax % per instalment**.
Enter a percentage next to every installment (19 means 19%, 5 means 5%, and
0 explicitly means zero VAT). Save schedule calculates each row's VAT and gross
total on the server. Saved values are labelled; unsaved inputs do not claim a
recalculated amount. Plan totals sum the independently rounded installment taxes.

Tax = principal amount × tax_rate_fraction, rounded half up to cents.
Buyer fees continue to spread pro rata. The percentage applies to principal,
not fees or the gross amount. Rates carry six decimal fraction precision.
Missing rates, negative rates, rates above 100%, and excess precision are refused.
The rate is selected by the operator; the app does not determine tax eligibility.

The original sale tax and buyer-total snapshots stay intact as contract reference.
For the new mode, reconciliation instead checks tax against the row rates, and the
buyer total against contract principal + calculated tax + frozen buyer fees.
Principal and fee coverage still reconcile exactly. Legacy pro-rata/manual
schedules retain their previous behavior and amounts; a null rate means legacy
allocation, not zero VAT.

Submitted/approved/active versions cannot be edited. Prepare, approve and activate
a revision with a change reason. Once collections have started, use the existing
Collections restructure to carry allocations; rates never mutate receipt history.
Collections scheduled/outstanding and cashflow amounts consume the existing
principal + tax + fee row contract. SPA-reference metrics retain the sale basis.

Migration 0026_installment_tax adds a nullable rate with range and amount checks,
and extends the charge mode. Upgrade changes no prior amount or source snapshot.
Downgrade works before use; once any rate or rate-mode version exists, it refuses
to discard tax history. Retain the schema and roll forward after use.

No new entity/create endpoint is added. Draft rows retain Remove + Save schedule;
governed rows retain revision/restructure. Existing plan/version deletion gaps
remain recorded in deletion_contracts.json and are not claimed as resolved.
