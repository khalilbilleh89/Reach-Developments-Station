# Project amendments

Overview / Edit project now provides a full-page form with all creation inputs:
code, name, developer, type, status, country configuration, base/reporting currency,
fiscal year, location/coordinates and planned dates. Existing values are prefilled.
Save sends only changed fields and refreshes the project. Unsaved edits are guarded.

Existing project writers can correct codes. The API normalizes to uppercase, validates
the creation format, rejects duplicates (including races), and retains old/new values
in project.updated audit evidence. The UUID and linked records remain unchanged.

Country/currencies retain the existing setup-only policy; operational projects show
their current basis and an explanation. Existing linked records can block corrections
even during setup. Changing currency does not perform FX conversion. Projects cannot
return to setup after leaving it. All other creation fields remain editable.

No new record type or deletion endpoint is introduced. Existing project removal stays
on the project register. Manager assignments remain in the existing access workflow.

Backend tests cover identity/audit preservation, code uniqueness and validation,
permissions and basis protections. Frontend tests cover all creation fields, current
inactive selections and operational restrictions.
