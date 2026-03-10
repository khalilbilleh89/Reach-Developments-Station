# Coding Standards

## Status

Initial standards defined. To be extended as implementation begins.

## Overview

These coding standards apply to all Python code in the `app/` directory.

## Key Standards

### Python Style
- Follow PEP 8
- Use type hints on all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

### Naming
- Files and modules: `snake_case`
- Classes: `PascalCase`
- Functions and variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Database models: `PascalCase` (e.g., `Project`, `SalesContract`)
- Pydantic schemas: `PascalCase` with suffix (e.g., `ProjectCreate`, `ProjectRead`)

### Module Structure
- Each module follows the standard internal structure: `api.py`, `models.py`, `schemas.py`, `service.py`, `repository.py`
- Service layer handles business logic — no business logic in `api.py` or `repository.py`
- Repository layer handles all database queries — no raw SQL in service or api layers

### Testing
- All business logic in `service.py` and `*_engine.py` files must have unit tests
- API endpoints must have integration tests using `httpx` + `pytest`
- Test files mirror the module structure under `tests/`

### Documentation
- All public functions and classes must have docstrings
- Architecture decisions must be recorded in `docs/04-decisions/`

## Open Questions

- Async vs. sync service layer: use async throughout for consistency with FastAPI
