# Reports

Delivery > Reports sits directly below Technical Specifications. Each project has
three sections: Site reports, Completion certificates and Client charters.
Site reports retain the latest-visit-first layout.

A site report requires a title and calendar report date. An architect completion
certificate requires a name and either one whole building or selected units.
A client charter requires a title and exactly one unit. Dates are optional for
certificates and charters. All sections require exactly one source:

- A PDF up to 50 MiB (52,428,800 bytes), reviewed inside the application with
  page navigation and zoom. The original can also be downloaded.
- An HTTPS Google Drive or Google Docs sharing link, opened explicitly in a
  new tab. Viewers need access in Drive; the application does not fetch or
  duplicate that file.

Notes are optional. Edit details changes the title, date, notes and applicability.
The section and source are immutable. Only active buildings/units in this project
can be newly selected. An unchanged retained assignment remains editable after
inventory removal; saved labels preserve the original reference.
Add another report for a new file or link so the original source remains
evidence. Report dates never undergo timezone conversion.

The existing whole-project Design readers can view reports. Project managers
and Design / Engineering editors can create, edit and remove them. Selected-phase
access does not expose project-wide reports. Every operation is authorized by
the API; PDFs are not public assets.

Delete requires confirmation, a reason and the current record version. It
removes the report from the register while retaining its original source,
metadata, applicability and audit history. Architect completion certificates are
reference evidence from the main architect, distinct from contractor completion
and payment certificates. Uploading any document does not change unit delivery
status, certify a construction payment stage, approve
an invoice or record a contractor payment.

Storage is additive: migration 0068_site_reports follows 0067_email_rich_text.
Downgrade refuses a populated report table, including removed reports.
Roll application code back while retaining the table when evidence exists.
Migration 0071_report_sections follows 0070_operations_commissions and classifies
existing rows as site_report without changing their source or date. It adds
retained unit links with same-project foreign keys. A unit linked to a current or
removed document cannot be permanently deleted/purged; ordinary removal remains
available. Downgrade to 0070 refuses any certificate/charter, including removed
ones. Roll forward while retaining evidence. Both tables are outside legacy intake.

API root: /api/v1/projects/{project_id}/technical-reports.
GET defaults to kind=site_report for existing clients; architect_certificate and
client_charter select the other registers. GET /targets returns active project
buildings and units under the same whole-project Design permissions.
PDF creation uses a streamed raw body and query metadata; Drive creation uses
POST /links. Metadata updates and POST /{report_id}/delete use expected_version.
Authorized document and preview routes reuse the bounded Plans PDF worker.

## Presentation

The library leads with the latest report, the first row of the server's
newest-first order, with its date, source and notes and one Open action. Earlier
reports follow as card rows (date and source); Edit and Delete sit in each row's
menu. Search also matches the displayed date ("10 Nov") and, while applied, lists
every match without singling one out. A single report shows no empty register.

Certificates and charters use the same card-row register, full-page editor,
PDF preview and retained Delete action. Their rows show building/unit applicability;
search matches the saved reference as well as title, date, source filename and notes.
Dated records sort newest first, followed by undated records by upload time.
No completeness percentage or client handover state is inferred from uploads.
