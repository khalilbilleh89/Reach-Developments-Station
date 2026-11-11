# Company Accounting & Tax — proposed fields

As at 11 November 2026. [stated] The owner requested country-based company accounting
information covering income tax, dividends, VAT and related taxes. [inferred] The fields
below are a proposed product design; they are not confirmed obligations for any company.
[GAP] Company tax residency, activities, registrations, recipient status and applicable
exemptions must be confirmed by its accountant. No rates or business facts are prefilled.
This document proposes the section; this PR does not implement storage or tax calculations.

## Profile and jurisdiction

Use the project's country as the initial checklist jurisdiction and show it explicitly.
Keep country of incorporation, tax residency and additional operating jurisdictions separate;
a company can have obligations in more than one country. A country change must preserve
existing records and flag them for review, never silently overwrite rates or registrations.

Optional profile fields: tax residency country, tax authority, income-tax registration number,
VAT/sales-tax registration number and effective date, financial year-end, reporting currency,
accountant/tax adviser name and contact, auditor, last reviewed date and reviewed-by person.
Do not store portal passwords or access tokens.

## Recommended checklist

| Area | Information to record |
| --- | --- |
| Corporate income tax | Regime, taxable activity, confirmed rate/bands, instalments, annual return/payment dates, losses carried forward, exemptions and supporting basis |
| VAT / sales tax | Registration status, effective date, return frequency, rates by activity/transaction, exempt/zero-rated treatment, input-tax recovery, reverse charge and property-specific treatment |
| Dividends / distributions | Paid versus received, recipient type and tax residency, applicable withholding or other charge, treaty/exemption basis, gross/net basis, declaration/payment dates |
| Other withholding taxes | Interest, royalties, services, contractor/non-resident payments; payee country, confirmed treatment and remittance dates |
| Property and development taxes | Acquisition/transfer charges, recurring property/local charges, disposal/capital-gains treatment, transaction date and linked land/project record |
| Payroll and employer obligations | Employer registration, payroll withholding, social contributions and reporting/payment frequency |
| Related-party transactions | Linked parent/group company, transaction type, transfer-pricing documentation, intercompany financing and review date |
| Other country-specific charges | Accountant-defined tax/levy name, jurisdiction, applicability and official reference |

Each item needs an applicability choice: **Needs review / Applicable / Exempt / Not applicable**.
Blank or Needs review must never appear as zero tax. Rates must be optional exact decimals,
with effective-from/to dates, source URL/document and review date. Exemption needs a reason
and optional expiry. Rate bands and distinct activities must not be compressed into one
misleading company-wide rate.

Separate filing due date from payment due date. Also record period covered, filing frequency,
responsible person, filing/payment status, submission reference and reminder date. Notifications
should only be labelled as sent when a notification mechanism is actually implemented.

Reuse labelled PDF uploads or Google Drive links for registration certificates, tax residency
certificates, returns, assessments, payment receipts and adviser confirmations. Link to the
existing document record rather than duplicating its bytes. Keep tax records editable and
reasoned removal available, with server authorization, project scope and retained audit.
Finance/administrator editing and separately defined read access need server enforcement.

## Country checklist sources

These are starting points for professional review, not automatic applicability or rate rules.

- **Cyprus:** review corporate income tax, VAT, property disposal/transfer treatment and the
  treatment of distributions/interest under the relevant tax year. The official department
  publishes a 2026 reform section, so legacy rates/rules should not be copied forward.
  Sources: [Tax Department](https://www.gov.cy/mof-tax/en/),
  [VAT guidance](https://www.gov.cy/mof-tax/en/document_topic/value-added-tax-vat/),
  [tax registration](https://www.businessincyprus.gov.cy/doing-business-in-cyprus/start-your-business/registering-for-income-tax-and-value-added-tax/).
- **Jordan:** label the indirect-tax checklist **General sales tax** and review the company's
  income-tax treatment against its activity and any applicable special-zone regime.
  Source: [Income and Sales Tax Department laws](https://www.istd.gov.jo/En/List/Laws).
- **Other project countries:** start with the same review checklist, obtain the relevant tax
  authority's sources, and have the accountant confirm additions or exclusions before use.
  An unsupported country must remain explicitly unreviewed, rather than inherit another
  country's rates or deadlines.

Recommended UI: a separate Accounting & Tax card below Company Information, showing
jurisdiction, reviewer/date and unresolved items; a full-page editor grouped into Tax profile,
Tax obligations and Filing calendar. Keep every descriptive field optional and distinguish
unknown, exempt and not applicable. Start with records and evidence; automated liability
calculations would require a separate, tested accounting specification.
