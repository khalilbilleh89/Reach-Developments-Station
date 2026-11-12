# Site engineer reports

Delivery > Reports sits directly below Technical Specifications. Each project has
a separate report library, ordered by report date (newest first).

A report requires a title, a calendar report date, and exactly one source:

- A PDF up to 50 MiB (52,428,800 bytes), reviewed inside the application with
  page navigation and zoom. The original can also be downloaded.
- An HTTPS Google Drive or Google Docs sharing link, opened explicitly in a
  new tab. Viewers need access in Drive; the application does not fetch or
  duplicate that file.

Notes are optional. Edit details changes the title, report date and notes.
Add another report for a new file or link so the original source remains
evidence. Report dates never undergo timezone conversion.

The existing whole-project Design readers can view reports. Project managers
and Design / Engineering editors can create, edit and remove them. Selected-phase
access does not expose project-wide reports. Every operation is authorized by
the API; PDFs are not public assets.

Delete requires confirmation, a reason and the current record version. It
removes the report from the register while retaining its original source,
metadata and audit history. Reports do not certify a completion stage, approve
an invoice or record a contractor payment.

Storage is additive: migration 0068_site_reports follows 0067_email_rich_text.
Downgrade refuses a populated report table, including removed reports.
Roll application code back while retaining the table when evidence exists.
The new table is explicitly outside the legacy intake bundle.

API root: /api/v1/projects/{project_id}/technical-reports.
PDF creation uses a streamed raw body and query metadata; Drive creation uses
POST /links. Metadata updates and POST /{report_id}/delete use expected_version.
Authorized document and preview routes reuse the bounded Plans PDF worker.

## Presentation

The library leads with the latest report, the first row of the server's
newest-first order, with its date, source and notes and one Open action. Earlier
reports follow as card rows (date and source); Edit and Delete sit in each row's
menu. Search also matches the displayed date ("10 Nov") and, while applied, lists
every match without singling one out. A single report shows no empty register.
