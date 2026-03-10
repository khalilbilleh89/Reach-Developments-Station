# ADR-004: Document Storage Strategy

**Date:** 2026-03-10  
**Status:** Accepted  
**Decision By:** Development Director / Architecture Baseline

---

## Context

The project involves two distinct categories of documents:

1. **Planning and architecture documents** — markdown files that define the system architecture, domain logic, product scope, and technical standards. These are created by the team and should live in the repository.

2. **Source research documents** — PDFs, reports, and reference materials that informed the architecture decisions. These are typically large binary files that are not appropriate for long-term version control storage.

A decision must be made about how to handle each category.

---

## Decision

### Planning Documents (Markdown)

All planning and architecture documentation lives in the `/docs` directory of this repository. This includes:
- Overview documents (`docs/00-overview/`)
- Domain module definitions (`docs/01-domain/`)
- Product scope documents (`docs/02-product/`)
- Technical architecture documents (`docs/03-technical/`)
- Architecture Decision Records (`docs/04-decisions/`)
- Reference index and findings (`docs/reference/`)

These documents are committed to version control and are subject to the same review process as code.

### Source Research Documents (PDFs and Reports)

Raw PDF source files are **references**, not core repository dependencies.

- They are **not** committed to the repository root or to random folders
- A small selection of the most important PDFs may be stored in `docs/reference/selected-pdfs/` — but only if they are directly needed as reference during implementation
- The primary reference for source documents is the index at `docs/reference/source-index.md`
- The key findings from source documents are summarized in `docs/reference/key-findings-summary.md`

### Future: Runtime Document Storage

When the Document Intelligence module is built (Phase 3), uploaded documents (customer documents, registration documents, etc.) will be stored in a cloud object storage service (e.g., AWS S3, Cloudflare R2). They will not be stored in the database or in the repository.

---

## Rationale

- Keeping planning docs in the repo ensures they are versioned alongside code and are always accessible to any developer or agent working on the codebase
- Keeping raw PDFs out of the repo prevents repository bloat and avoids binary file conflicts
- Summarizing key findings in markdown ensures the insights from research are accessible without requiring large file downloads
- Cloud object storage for runtime documents is the industry standard and scales appropriately

---

## Consequences

- Agents and developers must consult `docs/reference/source-index.md` to understand what source documents exist and what they cover
- The `docs/reference/selected-pdfs/` folder is intentionally small — bulk PDF storage is not the purpose of this repository
- `.gitignore` must exclude any accidentally downloaded raw research files from the root directory
