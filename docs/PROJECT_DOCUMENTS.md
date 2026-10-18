# Project Documents

The existing Documents register accepts either an external HTTP(S) link or an immutable PDF up to 10 MiB. Project, parcel and permit support links remain available. Land's Documents view downloads uploaded PDFs through the same authorized endpoint.

Document types are read through the project's effective jurisdiction choices, rather than an unrestricted Settings list. Technical writers can add project-owned types directly from Documents without administrator-only Settings writes; the new type is selected automatically. Existing jurisdiction choices retain their labels and inactive state. Project choices never become global Settings configuration. Unused project types can be deleted with a reason; any reference, including removed evidence, blocks their deletion.

PDF creation streams a bounded request body, checks the filename and PDF signature, and commits metadata, bytes, SHA-256 and audit together. List responses never include bytes. Downloads require current project access and use attachment disposition, nosniff and private/no-store headers. Files are immutable: record a replacement and supersede or remove the old entry. Metadata edits and all writes retain the existing technical-writer permissions.

Delete removes the document from registers and disables its file endpoint while retaining the original bytes, identity, hash and audit. Supersede/Restore remains available separately. Removal requires a nonblank reason. Writes lock the project so creation, type deletion and evidence removal cannot race around dependency checks.

Migration 0045 follows 0044. Upgrade preserves all existing link references, adds nullable file columns, a false removal marker and project type configuration. Clean downgrade is tested; downgrade refuses after project choices, PDF evidence or removal history exists. Roll forward after use. No production data is seeded.

Governance: docs/ENGINEERING_RULES.md and docs/DELETION_POLICY.md.
