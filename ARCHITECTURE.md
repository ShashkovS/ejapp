# ARCHITECTURE

## System Overview
`ejapp` is a client–server web application split into two projects housed in a single repository:
- A **FastAPI** backend that exposes RESTful endpoints for authentication and item management, persists data in SQLite via SQLAlchemy, and issues JWT access/refresh tokens.
- A **Vite + TypeScript** frontend that authenticates against the API, stores tokens in `localStorage`, and renders a protected workspace once the user signs in.

Both services are run independently during development. The frontend communicates with the backend through JSON over HTTPS (HTTP locally). Cross-origin requests from the dev server are permitted via CORS middleware. Authentication state is maintained with bearer tokens attached to requests, and refresh tokens are used to renew access tokens without re-entering credentials.

## Backend
### Application Composition
- **Entry point:** `backend/main.py` instantiates the FastAPI app, configures environment-derived settings via `python-dotenv`, registers CORS middleware, and defines the application lifespan hook used to reset the database when `E2E=1`.
- **Async database session:** SQLAlchemy's async engine (`create_async_engine`) targets the configured SQLite database. `AsyncSessionLocal` is provided for request-scoped sessions and reused inside route handlers.
- **Models:** `backend/db.py` defines two declarative models:
  - `User` with unique email, hashed password, and `is_active` flag.
  - `Item` linked to a `User` via `owner_id`.
- **Migrations:** Alembic is configured through `backend/alembic.ini` with scripts in `backend/migrations/` to evolve the schema.

### Authentication & Security
- Passwords are hashed using Passlib's bcrypt context (`pwd_context`).
- JWT helpers create access tokens (default 120-minute expiry) and refresh tokens (90-day expiry) using `PyJWT` and settings from `.env` (`SECRET_KEY`, `ALGORITHM`).
- `OAuth2PasswordBearer` extracts bearer tokens from the `Authorization` header for protected routes.
- Protected endpoints decode tokens, validate the `sub` claim (user email), and fetch the associated user record; missing or invalid tokens raise `401 Unauthorized` errors.
- A simulated Google OAuth callback (`/auth/google/callback`) creates or retrieves a hard-coded Google user for offline testing.

### API Surface
`backend/main.py` groups core routes:
- `GET /healthz` — lightweight health probe.
- `POST /auth/register` — creates a user and returns access + refresh tokens.
- `POST /auth/login` — verifies credentials and issues tokens.
- `POST /auth/refresh` — exchanges a valid refresh token for new tokens.
- `GET /auth/google/callback` — mock OAuth exchange that returns tokens.
- `GET /items` — returns the current user's items (requires access token).
- `POST /items` — creates an item for the authenticated user.

All handlers use async sessions to interact with the database. Responses are simple dictionaries (Pydantic models are defined for request/response validation).

## Frontend
### Structure
- **Entry HTML:** `frontend/index.html` loads the public landing page; Vite injects bundles from `frontend/src/main.ts`.
- **Public bundle (`frontend/src/main.ts`):** Implements registration, login, and simulated Google OAuth flows. On success, tokens are persisted to `localStorage` and the browser navigates to `/private/`.
- **Private area (`frontend/private/`):** Contains its own HTML and `main.ts`, which loads Tailwind styles, fetches the current user's items, submits new items, and performs automatic refresh-token flow when access tokens expire. It redirects to `/` if no access token is present.
- **Styling:** Tailwind CSS is configured through `tailwind.config.js` and processed via the `@tailwindcss/vite` plugin.

### Build & Tooling
- Vite handles dev server and production builds. The default `VITE_API_BASE` is `http://localhost:8000`; Playwright E2E runs set this to `http://localhost:18100` for preview mode.
- Unit tests run with Vitest, while Playwright scripts in `frontend/tests/` exercise the full stack via a headless browser. Global setup/teardown scripts in that directory coordinate preview server lifecycle when executing E2E suites.

## Data Flows
### Registration & Login
1. User submits the registration or login form from the public page.
2. Frontend issues a `POST` to `/auth/register` or `/auth/login` with JSON credentials.
3. Backend validates the request, hashes/verifies passwords, and returns JSON containing `access_token`, `refresh_token`, and `token_type`.
4. Frontend stores both tokens in `localStorage` and navigates to `/private/`.

### Authenticated Requests & Refresh
1. Private-area scripts call the helper `apiRequest`, which attaches `Authorization: Bearer <access_token>`.
2. Backend validates the token and services `/items` requests by querying the database for the authenticated user.
3. If the backend responds with `401` (expired/invalid access token), the frontend automatically calls `/auth/refresh` with the refresh token to obtain new credentials, updates `localStorage`, and retries the original request.
4. Logging out clears stored tokens and returns the user to `/`.

### Item Management
1. `GET /items` fetches the list of items owned by the current user (`Item.owner_id`).
2. `POST /items` adds a new item with the submitted title and associates it with the user.
3. Responses are rendered in the private UI as a simple list.

## Configuration & Environment
- `.env` at the repository root defines secrets and connection settings; `backend/main.py` loads it via `load_dotenv('../.env')`.
- `FRONTEND_ORIGIN` configures allowed CORS origins (defaults to `http://localhost:5173`). For development, localhost/127.0.0.1 aliases are automatically added.
- Setting `E2E=1` before starting the backend instructs the app to create a temporary SQLite database under `backend/.e2e-db/` and rebuild tables on startup, keeping end-to-end tests isolated and repeatable.

## Testing & Automation
- `backend/tests/` contains Pytest suites using HTTPX to call the API.
- `frontend/tests/e2e.spec.ts` drives the user journey (register → add item → logout) using Playwright.
- The repository Makefile orchestrates setup, linting (`make lint` for Ruff + Prettier), formatting (`make format`), unit tests (`make test-backend`, `make test-frontend-unit`), and end-to-end runs (`make test-e2e`).
- Playwright preview runs bind to port 63343; make targets ensure the correct preview lifecycle via `npm run e2e`.

## Persistence & Future Extensions
- SQLite is the default persistence layer; SQLAlchemy abstracts database interactions, easing migration to another RDBMS.
- Alembic migrations should accompany schema changes to keep environments consistent.
- Additional domains or services can be added by expanding FastAPI routers and augmenting the frontend with corresponding views; the modular separation between `src/` (public flows) and `private/` (authenticated area) supports incremental growth.
