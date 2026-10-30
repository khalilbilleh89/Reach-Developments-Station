# Buyer and Agent Excel imports

Buyers and Agents each offer **Import from Excel** beside registration. Download
the project-specific template, fill the named sheet starting at row 2, choose the
completed file, validate, then import. Up to 1,000 records and 5 MB per file.

Buyer columns match Register buyer: display_name, email, phone, sole_purchaser,
and agent_id. Blank sole_purchaser means TRUE, creating the named 100% purchaser.
FALSE leaves joint parties to the existing party editor. The Agent reference sheet
lists active project Agents with country, branch and leader; copy their ID into
agent_id. Import Agents first when necessary. Numbers and identifiers are formatted
as text to preserve leading zeros. Unit connection remains the existing separate step.

Agent columns match Add agent: display_name, country, branch, branch_leader.
New Agents are active, as in manual registration. Only display_name is required.

The importer calls the existing create services and request schemas, retaining
permissions, advisor ownership, active project-agent checks, audit events and
sole-purchaser creation. Templates are versioned and project-bound. Formula cells,
macros, old/encrypted formats, malformed headers, empty files and excessive package
sizes are refused. All ZIP members are bounded before workbook parsing.

Validation stages the domain writes in savepoints and rolls the whole transaction
back, including audit and attribution records. Apply reparses and repeats validation
under the project lock, then commits once only if every row succeeds. No persistent
import batch record or uploaded workbook is stored. Matching visible records and
repeated rows are skipped and counted using trimmed, case-insensitive buyer name/email/phone
or Agent name/country/branch/leader. Buyer checks honor existing advisor visibility;
this is not a global identity-matching or deduplication feature. After ambiguous
network failures, refresh the register before retrying.

Imported records appear in the normal registers and reuse their deletion controls.
Administrators may delete unused buyers; buyer transaction history blocks deletion.
Authorized writers may delete unused Agents; attribution, buyer, transaction or
commission history requires deactivation. Existing audit retention remains intact.

No schema migration, new dependency, price calculation, sale activation, payment,
KYC clearance, privacy attestation or deployment configuration is introduced.

Tests: tests/modules/test_sales_import.py covers atomic validation/apply, retry,
manual-equivalent ownership/attribution, read redaction, scope, role denial,
malformed files, stale Agent state and existing removal contracts.
frontend/tests/salesImport.test.mjs covers file-change invalidation, failed apply,
row errors, refresh and repeat-submission prevention.

## Re-importing an expanding list

Keep existing rows in the project template and append new names. Validate reports
new_count and duplicate_count separately. Apply reparses under the project lock,
creates only the new rows and reports created_count plus duplicate_count, with
Excel row numbers and whether each match already existed or repeated a file row.
A file containing only duplicates succeeds with zero new records. Existing records
are never changed or reactivated, and skipped rows create no audit/ownership rows.
Real validation errors still roll back all new records. Matching remains exact
after trimming and case folding: Agents use name/country/branch/leader; Buyers
use name/email/phone within the caller’s visible buyers. Changing these identity
fields is a new record, not an update. If another user imports the same names between validation and apply, apply
rechecks the current state and skips those names too.
