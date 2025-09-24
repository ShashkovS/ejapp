# AGENTS

This document provides the essential context and operating rules for AI coding agents working on **ejapp**. Review it at the start of every session and update it (along with `ARCHITECTURE.md`) when project conventions change.

## Build & Run Checklist
- **Setup everything**: `make setup`
  - Installs/updates the Python virtualenv (`backend/.venv`), backend dependencies (editable install with dev extras), frontend npm packages, and pre-commit hooks.
- **Backend (dev)**: `make run-backend`
  - Starts Uvicorn at `http://localhost:8000` with auto-reload. Supports `E2E=1` for an ephemeral SQLite database under `backend/.e2e-db/`.
- **Frontend (dev)**: `make run-frontend`
  - Launches the Vite dev server at `http://localhost:5173`. The client reads `VITE_API_BASE` (defaults to the backend dev URL).
- **Tests**:
  - Unit suites: `make test-backend` (Pytest) and `make test-frontend-unit` (Vitest).
  - All fast checks: `make test` (backend + frontend unit).
  - End-to-end: `make test-e2e` (builds the frontend, runs Vite preview on port 63343, then executes Playwright).
- **Quality gates**: `make lint` (Ruff + Prettier) and `make format`.
- **Database migrations**:
  - Create: `make migrate-new m="description"`
  - Apply: `make migrate-up`
  - Revert last: `make migrate-down`

## Project Map
- `backend/main.py` — FastAPI app setup, settings, routes for `/auth/*`, `/items`, and health check.
- `backend/db.py` — SQLAlchemy `User` and `Item` models plus declarative base.
- `backend/migrations/` — Alembic revision scripts (keep in sync with model changes).
- `backend/tests/` — Pytest coverage for authentication and items.
- `frontend/src/` — Public landing page logic (register/login + Google simulation) and shared styles.
- `frontend/private/` — Authenticated experience (token refresh, item CRUD UI).
- `frontend/tests/` — Playwright end-to-end flow and global setup/teardown scripts.
- `Makefile` — Canonical entry point for setup, testing, linting, formatting, and migrations.

### Conventions & Expectations
- Backend code is fully async; use `AsyncSession` and avoid blocking operations inside request handlers.
- Use Pydantic models for request/response validation where appropriate. Token payloads must include a `sub` claim (user email).
- Attach JWT access tokens via the `Authorization: Bearer <token>` header when calling protected routes in tests or new client code.
- Respect CORS origins derived from `FRONTEND_ORIGIN`; do not hard-code additional origins.
- Secrets and configuration belong in `.env` (root). Never commit real credentials.
- When adding database fields or new tables, create an Alembic migration and ensure tests cover the change.
- Always add or update tests (Pytest, Vitest, and/or Playwright) relevant to your changes. Keep coverage for the happy path and key error states.
- Run `make lint` and the relevant test commands before finishing work. Fix or document any failures you cannot resolve.
- Update documentation (`README.md`, `ARCHITECTURE.md`, and this file) when you change behaviours, endpoints, or workflows.
- Prefer small, focused commits and leave the git tree clean (no untracked files) before requesting review.
