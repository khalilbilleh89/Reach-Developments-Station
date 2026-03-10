# Database Architecture

## Status

Conceptual model defined. SQL schema and migrations are deferred to implementation phases.

## Overview

The database for Reach Developments Station uses PostgreSQL. The ORM is SQLAlchemy (async mode). Database migrations are managed with Alembic.

This document describes the database design principles. The full entity list and their attributes are defined in [`../00-overview/core-data-model.md`](../00-overview/core-data-model.md).

## Key Decisions

- **PostgreSQL**: Chosen for reliability, rich JSON support, and strong support for financial data integrity
- **SQLAlchemy async**: Enables non-blocking database operations with FastAPI
- **Alembic**: Migration management — all schema changes must go through migrations, never manual DDL
- **Integer for money**: All monetary amounts stored as integers (smallest currency unit, e.g., fils or cents) to avoid floating point errors
- **UUID primary keys**: All entities use UUID primary keys for security and distributed compatibility
- **Soft deletes**: No hard deletes on financial records — use `is_deleted` flag and `deleted_at` timestamp

## Standards

- All tables have: `id` (UUID), `created_at`, `updated_at`, `created_by`, `updated_by`
- Financial records also have: `is_deleted`, `deleted_at`, `deleted_by`
- Foreign keys are always indexed
- Enum values stored as strings (not integers) for readability
- All timestamps stored as UTC

## Open Questions

- Multi-currency support: deferred to Phase 2. Base currency is defined per project.
- Partitioning strategy: evaluate if needed once data volume is understood.
