# Sales workbook drafts

Boss can download a project-specific Excel template from Sales > Import Sales / review drafts, validate it, and create unposted drafts. Each sale has a unique `sale_key`; repeat that key in the relevant section sheets. Use project reference sheets for units and existing buyer/agent IDs.

The template includes Sales, Buyer, Agent, EOI, Reservation, SPA, Parties, Adjustments, Legal, Payment plan, Schedule, Installments, Receipts, Allocations, Collection actions, Disputes, Waivers, Refunds, Cancellation and Handover. The Field guide lists the writable fields and constraints of the owning input contracts. Computed balances and binary attachments are not imported. EOI timestamps require a timezone and preserve time of day.

Import validates all rows before saving anything. Identical repeated keys are skipped; conflicting data for an existing key must be corrected on its draft. Maximum upload: 5 MB, 1,000 sales, 10,000 total section rows. Formulas, invalid headers, foreign project templates and unknown sections are rejected.

Review each draft, correct fields, add/remove section rows, and save corrections with a reason. Export retains all supplied sections. A stale version cannot be edited, deleted or added. Unposted drafts can be deleted by Boss; their deletion audit is retained.

## Adding a reviewed draft

The explicit Add action creates a PREPARING reservation using the existing Sales service, with a new buyer/agent/parties when supplied and reservation adjustments. Alternatively, link an existing buyer by client_id; existing buyer data is never silently overwritten. Use an existing client_id when several unit purchases belong to the same already registered buyer. Missing commercial requirements must be completed before adding. All changes are atomic.

EOI, SPA, legal, payment-plan, schedule, collection and handover sections remain attached as unposted source information, accessible from the Sales transaction. They do not automatically create native records, approve schedules, confirm cash, attest signatures or complete handover. This is a draft intake feature, not historical financial migration. Document references do not upload document bytes. Existing normal workflows remain responsible for posting those events.

Added sources cannot be edited/deleted separately. Their preparing transaction uses existing correction/cancellation controls. Explicit confirmed Inventory history purge includes the unit-owned source drafts in its preview and deletion; shared buyers and agents remain protected. No change to cash calculation, rounding or currency conversion is introduced.

## Deployment

Migration 0058 adds sales_import_drafts without a backfill. Downgrade refuses while records remain to avoid loss of source evidence. No environment variables or dependencies are added.
