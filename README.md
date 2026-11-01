# SpendWise AI

**Personal Expense & Lifestyle Intelligence System**

SpendWise AI is a multi-user web application that helps people understand their
spending habits, relate spending to everyday lifestyle choices, and plan
expenses ahead of time.

> **Developed by Jaidul Islam.**

---

## Overview

Most budgeting tools stop at recording what was spent. SpendWise AI aims to
connect *what* people spend with *how* they live — meals out, transport
choices, coffee and snacks, shopping, sleep and stress — and to make honest,
data-grounded insights about those patterns.

The project is built incrementally. Each batch is small, testable and
shippable; nothing is presented as working until it has actually been built and
verified.

## Objectives

- Make daily expense entry quick and low-friction.
- Turn recorded data into clear visual analytics.
- Explore associations between lifestyle choices and spending, while
  distinguishing correlation from causation.
- Forecast daily and weekly expenses **only when the user's data supports it**.
- Let users explore "what if" scenarios (e.g. bus instead of taxi) with clearly
  labelled calculated versus estimated results.
- Flag unusual expenses without making unsupported claims.
- Protect each user's data through strict, testable per-user isolation.

## Features

| Area | Feature |
| --- | --- |
| Expenses | Daily expense entry, editing, deletion, categories, optional spending context |
| Lifestyle | Optional daily check-in: meals out, transport, coffee/snacks, shopping, sleep, stress |
| Budgets | Monthly limits overall or per category, with spending, remaining and % used |
| Analytics | Totals, category breakdowns, trends, weekday patterns |
| Insights | Cautious correlation analysis, spending-behaviour segments, unusual-expense flags |
| Prediction | Descriptive baselines first; statistical baselines; models only when evaluation shows improvement |
| Simulation | What-if scenarios for transport, restaurant visits, coffee, shopping and category reductions |
| Account | Registration, login, profile and password management, CSV data export, account deletion |

## Technology stack

| Layer | Technology |
| --- | --- |
| Backend API | Python, FastAPI, Pydantic |
| Frontend | Streamlit |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Analysis / ML | Pandas, NumPy, scikit-learn |
| Auth | JWT, password hashing |
| Testing | Pytest |
| Quality | Ruff (lint + format) |
| Tooling | Git, GitHub, Docker (later batch) |

## High-level architecture

```
┌──────────────────┐   HTTPS / JSON (JWT)   ┌──────────────────────────┐
│   Streamlit UI   │ ─────────────────────► │        FastAPI           │
│  (presentation)  │ ◄───────────────────── │  API + insights/ML pkg   │
└──────────────────┘                        └────────────┬─────────────┘
                                                         │ SQLAlchemy
                                                 ┌───────▼────────┐
                                                 │   PostgreSQL   │
                                                 └────────────────┘
```

Key architectural rules:

- **Streamlit never talks to PostgreSQL directly.** All data access goes
  through the FastAPI backend, so authorization lives in exactly one place.
- **The insights/ML code is a package inside the backend**, called in-process.
  There are no microservices, queues or workers.
- **Each user's data is isolated by `user_id` taken from the verified token**,
  never from the request payload.
- **The MVP is single-currency**: each user has one primary currency and no
  cross-currency arithmetic is performed.
- **No caching** is used until performance measurements justify it.

### Expense date contract

- `spent_at` is stored as a **UTC** timestamp and is always timezone-aware.
- `expense_date` is the calendar date in the **user's IANA timezone** and is
  what all analytics group by.
- Sending `expense_date` only stores local noon of that day as the timestamp.
- Sending `spent_at` only derives `expense_date` from it in the user's timezone.
- Sending both requires them to agree; otherwise the API returns **422**.
- A PATCH that does not mention either field never changes the dates.

The Streamlit form collects a date only, so it never sends a contradictory
timestamp.

## Development roadmap

| Batch | Scope |
| --- | --- |
| 1 | Foundations + project configuration *(done)* |
| 2 | Database + models + migrations *(done)* |
| 3 | Authentication + user isolation *(done)* |
| 4 | Expense management + lifestyle logging *(done)* |
| 5 | Dashboard + analytics *(done)* |
| 6 | Insights + anomaly detection *(done)* |
| 7 | Prediction baselines + evaluation *(done)* |
| 8 | Advanced ML + what-if simulator *(done)* |
| 9 | Testing + security + data export/deletion *(done)* |
| 10 | Docker + deployment + documentation |

## Production notes

- `GET /health` returns only `{"status": "ok"}` — it deliberately exposes no
  environment name, version, or configuration detail.
- The JWT secret is held as a Pydantic `SecretStr`, so it never appears in
  `repr()` output or model dumps.
- With `APP_ENV` set to anything other than `development`, startup fails if
  `JWT_SECRET` is still the placeholder.
- Only HMAC algorithms (`HS256`/`HS384`/`HS512`) are accepted; `none` and
  asymmetric algorithms are rejected to prevent algorithm-confusion attacks.
- A failed request rolls its database transaction back before the connection
  returns to the pool.

## Local setup

Requires **Python 3.11+**.

```bash
# 1. Clone the repository
git clone <repository-url>
cd spendwise-ai

# 2. Create and activate a virtual environment
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install the runtime dependencies (backend + frontend)
pip install -r requirements.txt

# 4. Install the development tools (Ruff, Pytest)
pip install -r requirements-dev.txt
```

`pyproject.toml` is the dependency source of truth; install it without `-e`
because the project is not packaged as a distributable module (there is no
`[build-system]` and no top-level importable package). `requirements.txt`
mirrors the runtime dependencies:

| Area | Contents |
| --- | --- |
| API + auth | FastAPI, uvicorn, pydantic-settings, PyJWT, Argon2 (primary), bcrypt (fallback) |
| Database | SQLAlchemy, Alembic, psycopg |
| Analytics / ML | pandas, numpy, scikit-learn |
| Frontend | Streamlit, httpx |

```bash
# 5. Create your local environment file
cp .env.example .env   # then fill in your PostgreSQL password and a JWT secret
```

### Local PostgreSQL configuration

The project targets a local PostgreSQL instance (developed against
PostgreSQL 18 on Windows). The connection string uses the **psycopg 3**
driver:

```
postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
```

Expected local values:

| Setting | Value |
| --- | --- |
| Host | `localhost` |
| Port | `5432` |
| Database | `spendwise_db` |
| Username | `postgres` |
| Password | set by you during installation |

Edit `.env` (never `.env.example`) and replace the `CHANGE_ME` placeholder:

```ini
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/spendwise_db
```

Notes:

- `.env` is git-ignored; never commit real credentials.
- If your password contains `@`, `:`, `/` or `%`, percent-encode it
  (for example `@` becomes `%40`).
- `DATABASE_URL` and `JWT_SECRET` are read from the project-root `.env`
  regardless of the directory you run commands from.
- If `DATABASE_URL` still contains `CHANGE_ME`, the application raises a clear
  configuration error instead of attempting a connection.

```bash
# 6. Create the database (skip if you already created spendwise_db)
createdb -U postgres spendwise_db

# 7. Apply migrations (from the backend directory)
cd backend
alembic upgrade head
cd ..

# 8. Run the API (from the backend directory)
cd backend
uvicorn app.main:app --reload
# Interactive docs: http://127.0.0.1:8000/docs

# 9. Run the frontend (in a second terminal, from the frontend directory)
cd frontend
streamlit run streamlit_app.py
# Opens http://localhost:8501

# 10. Run lint and tests
ruff check .
ruff format --check .
pytest
```

The migration enables the **CITEXT** extension
(`CREATE EXTENSION IF NOT EXISTS citext`) because `users.email` uses it for
case-insensitive uniqueness. On a standard PostgreSQL 18 install this succeeds
without extra steps when the migration runs as a superuser (the `postgres`
user is one). If the app user is not a superuser, create the extension once as
a superuser first:

```sql
CREATE EXTENSION IF NOT EXISTS citext;
```

The frontend talks to the backend over HTTP at `BACKEND_API_URL`
(default `http://localhost:8000`). It never connects to PostgreSQL directly,
so all authorization stays in one place.

Database-backed tests use a separate database. `backend/tests/db_guard.py`
derives its name by appending `_test` to the database in `DATABASE_URL`, so the
default `spendwise_db` means the suite needs **`spendwise_db_test`**. Create it
with `createdb -U postgres spendwise_db_test`, or point `TEST_DATABASE_URL` at
any database whose name ends in `_test` — names without that suffix are
rejected, so a real database can never be used. When the test database is not
reachable those tests are **skipped**, not passed.

## Run SpendWise AI in GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jaidulislamalvi7-hue/spendwise-ai)

**What this is.** GitHub Codespaces gives you a **private, disposable development
environment** for this repository, running in the cloud against your own browser.
It is *not* a permanent public demo: each person who opens the repository gets
their own separate containers, their own database, and their own data. Nothing
you enter is shared with anyone else, and the environment is deleted when you
stop it (subject to your retention settings).

### 1. Open the environment

Click the badge above, or visit <https://codespaces.new/jaidulislamalvi7-hue/spendwise-ai>
and choose **Create codespace**. The first start takes a few minutes while the
containers build and Python dependencies install.

### 2. What happens automatically

The environment initialises in three ordered stages:

| Stage | Hook | What it does |
| --- | --- | --- |
| 1. Before containers exist | `initializeCommand` → `init-env.sh` | Generates `.devcontainer/.env` with **random** secrets (`openssl`, 48/96 hex chars). This must run on the host *before* Compose starts, because Compose interpolates `${POSTGRES_PASSWORD}` and `${JWT_SECRET}` while parsing its own file. |
| 2. After the workspace is mounted | `postCreateCommand` → `setup.sh` | Creates `.venv` and installs `requirements.txt` + `requirements-dev.txt` into it. |
| 3. Every container start | `postStartCommand` → `start.sh` | Starts FastAPI on 8000 and Streamlit on 8501, waits for each to become reachable, and fails loudly if one does not. |

Secrets exist only inside your Codespace, are git-ignored, and are never printed.
An existing `.devcontainer/.env` is never overwritten.

None of these stages creates the database **schema**. On a brand-new Codespace,
apply migrations once (step 4) before registering an account — otherwise both
services start and listen normally, but every database call fails.

### 3. Environment variables

**You do not need to provide any secrets.** They are generated for you.

To override a setting, edit `.devcontainer/.env` inside the Codespace (it is
already git-ignored) and rebuild the container. That file holds the
`POSTGRES_*`, `JWT_*`, `APP_ENV` and `LOG_LEVEL` values listed above — **not**
a `DATABASE_URL`. Compose builds `DATABASE_URL` from those parts and aims it at
the Codespaces PostgreSQL service (`db:5432`) instead of your local machine, so
a Codespace and a local install can never collide.

Because `POSTGRES_PASSWORD` is consumed only when PostgreSQL initialises an
empty data directory, editing it afterwards does **not** change the running
database's password. See "Rotating Codespaces credentials" below.

If organisation policy blocks generated files, you can instead add Codespaces
secrets under **Settings → Codespaces → Secrets**, using the names from
`.env.example`. Never commit real values.

### 4. Database migrations

Migrations are **never** run automatically. Apply them once, and again after
pulling schema changes:

```bash
cd /workspaces/spendwise-ai/backend
../.venv/bin/python -m alembic upgrade head
```

Run this **from `backend/`**. `alembic.ini` sets `script_location = alembic`,
which Alembic resolves relative to the current working directory rather than to
the `.ini` file, so running it from the repository root fails with
`Path doesn't exist: alembic`. The database URL comes from `DATABASE_URL`,
which the dev container receives from Compose.

### 5. Start the application manually

The environment starts the app automatically. If you stopped the processes or
the automatic start failed, run:

```bash
bash .devcontainer/start.sh
```

It is safe to re-run: a service already listening on its port is left alone, and
a failure prints the tail of that service's log.

To run each service in its own terminal instead:

```bash
# Terminal 1 - API (port 8000)
cd /workspaces/spendwise-ai/backend
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - UI (port 8501)
cd /workspaces/spendwise-ai/frontend
../.venv/bin/python -m streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0
```

### 6. Access the application

- **Streamlit (the app):** the **Ports** tab → port **8501** → open in browser.
  Codespaces normally opens it automatically.
- **API docs:** port **8000**, path `/docs` (development only; disabled when
  `APP_ENV=production`).
- **Health check:** `curl http://localhost:8000/health` → `{"status":"ok"}`.

### 7. Create a test account

There are no seed accounts and no real financial data. On the Streamlit login
page use the **Create account** tab. Password must be at least 8 characters.
Currency and timezone are chosen at registration.

### 8. Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `POSTGRES_PASSWORD variable is not set` | `.devcontainer/.env` was not generated. Run `bash .devcontainer/init-env.sh` on the host, then rebuild the container. |
| API exits immediately; log mentions `JWT_SECRET` or `DATABASE_URL` | The placeholder guard fired. Confirm `.devcontainer/.env` exists, then rebuild (Compose reads it at creation time). |
| `ERROR: .../bin/python not found` from `start.sh` | The virtualenv is missing. Run `bash .devcontainer/setup.sh`. |
| `Cannot reach the backend` in the UI | API is not running. Run `bash .devcontainer/start.sh`; it prints the log tail on failure. |
| `start.sh` reports a port never became ready | Read `.devcontainer/logs/backend.log` or `streamlit.log` — the last 40 lines are printed for you. |
| Port 8501 shows a "not found" page | You are on the wrong port. Use 8501 for Streamlit, 8000 for the API. |
| Port changes after a rebuild | Codespaces sometimes changes the forwarded URL. Use the **Ports** tab rather than an old bookmark. |
| `alembic: command not found` | Use the virtualenv: `../.venv/bin/python -m alembic upgrade head`, run from `backend/`. |
| `Path doesn't exist: alembic` | Alembic was started from the repository root. `script_location` resolves relative to the working directory, so `cd backend` first. |
| Registration or any API call fails with a database error on a fresh Codespace | The schema was never created. Run the migration command in step 4. |
| Database authentication fails after changing `.devcontainer/.env` | PostgreSQL stored its superuser password in the persistent volume on first initialisation and ignores new values. Deleting `.devcontainer/.env` alone does **not** rotate credentials. See the note below. |
| Tests all skip | The test database is absent. That is the safety guard working; see the note below. |

Database-backed tests never use the application database. `backend/tests/db_guard.py`
derives a separate one by appending `_test` to the database name in
`DATABASE_URL`, so with the Codespaces default (`spendwise_db`) the suite needs
**`spendwise_db_test`** — not `spendwise_test`. When that database is
unreachable the database-backed tests are **skipped**, never counted as passed,
and `db_guard` refuses any destructive operation against a database whose name
does not end in `_test`.

Create it once. The `dev` container does not receive `POSTGRES_*`, so run `psql`
inside the `db` service and let that container's own environment supply the
credentials:

```bash
docker compose -f .devcontainer/docker-compose.yml --env-file .devcontainer/.env \
  exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE DATABASE spendwise_db_test;"'
```

`POSTGRES_USER` and `POSTGRES_DB` are defined inside the `db` container, so no
secret is typed on the command line. The test database lives inside the
Codespaces PostgreSQL volume only; it never touches any local system.

Then run the suite from the repository root. No paths are needed: `pytest.ini`
already sets `testpaths` (both packages) and `pythonpath`.

```bash
cd /workspaces/spendwise-ai
.venv/bin/python -m pytest -q
```

Lint and formatting need no database at all:

```bash
cd /workspaces/spendwise-ai
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

A run with no reachable test database is expected to report skips for the
database-backed tests while the unit tests still pass.

#### Rotating Codespaces credentials

PostgreSQL applies `POSTGRES_PASSWORD` **only when it initialises an empty data
directory**. After the first start it stores its own credentials in the
persistent volume (`spendwise_codespaces_pgdata`) and ignores any new value.

Consequently, deleting `.devcontainer/.env` and rebuilding regenerates the
secrets in that file, but **does not change the database password** — the
mismatch causes authentication failures.

Rotating credentials therefore requires a deliberate, isolated reset:

```bash
# 1. Stop the Codespaces stack and remove only the volumes it declares.
#    "-v" is scoped to this Compose project ("spendwise-codespaces", set by the
#    name: key in .devcontainer/docker-compose.yml), so it cannot reach the root
#    stack's "spendwise_pgdata" volume.
docker compose -f .devcontainer/docker-compose.yml --env-file .devcontainer/.env down -v

# 2. Regenerate the environment file with fresh secrets.
rm .devcontainer/.env
bash .devcontainer/init-env.sh

# 3. Recreate the stack and re-apply migrations.
docker compose -f .devcontainer/docker-compose.yml --env-file .devcontainer/.env up -d
cd backend && ../.venv/bin/python -m alembic upgrade head
```

If you would rather delete the volume yourself, remember that Compose prefixes it
with the project name, so the bare `spendwise_codespaces_pgdata` does not exist
as such. List first and copy the exact name — do not guess:

```bash
docker volume ls | grep spendwise-codespaces
# spendwise-codespaces_spendwise_codespaces_pgdata
```

This destroys the Codespaces database only. It never touches a local database or
the root stack's `spendwise_pgdata` volume, and it must never be run against a
volume belonging to another environment.


### What stays the same

The architecture is unchanged: **Streamlit → FastAPI → PostgreSQL**. Streamlit
never connects to PostgreSQL directly, the database is not published publicly,
and authentication, password hashing, and per-user data isolation are identical
to a local run. The Codespaces stack lives entirely in `.devcontainer/`; the
root `docker-compose.yml` is untouched.

## Docker (local development)

The stack is: **PostgreSQL container → FastAPI container → Streamlit container**.
The frontend reaches the backend at `http://backend:8000` on the compose
network; the browser never talks to the backend directly.

```bash
# 1. Provide the two required values
cp .env.example .env
#    set POSTGRES_PASSWORD and generate a JWT_SECRET:
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. Build and start
docker compose up --build -d

# 3. Apply migrations explicitly (never automatic)
docker compose exec backend alembic upgrade head

# 4. Open the app
#    Streamlit: http://localhost:8501
#    API docs:  http://localhost:8000/docs
```

Notes:

- The database container publishes **no host port**; it is reachable only on
  the compose network.
- Migrations are **never** run automatically at container start, so a restart
  cannot alter the schema.
- The upstream URL for the `db` service is `db:5432`, not `localhost`.
- Stop with `docker compose down`. Add `-v` **only** if you intend to delete
  the database volume.

## Production deployment

The backend and frontend are separate services. Deploy them independently and
give them a managed PostgreSQL instance.

**Required environment variables** (see `deploy.env.example`):

| Variable | Required | Notes |
| --- | --- | --- |
| `APP_ENV` | yes | `production` (or `staging`) |
| `DATABASE_URL` | yes | Full DSN for the managed database, e.g. `...?sslmode=require` |
| `JWT_SECRET` | yes | Random 32+ byte secret; startup fails if missing |
| `JWT_ALGORITHM` | no | Defaults to `HS256`; only HMAC algorithms accepted |
| `JWT_EXPIRE_MINUTES` | no | Defaults to 60 |
| `CORS_ALLOW_ORIGINS` | no | Comma-separated explicit origins; wildcards rejected |
| `LOG_LEVEL` | no | Defaults to `INFO` |
| `BACKEND_API_URL` | frontend | Where **Streamlit** reaches the API |

**Startup safety.** With `APP_ENV` set to anything other than `development`,
the backend refuses to start if `JWT_SECRET` or `DATABASE_URL` is missing, or
if `CORS_ALLOW_ORIGINS` contains a wildcard. The failure names the offending
setting but never prints its value.

**API documentation** (`/docs`, `/openapi.json`) is disabled automatically when
`APP_ENV=production`, so the full API surface is not publicly enumerable.

**CORS.** Streamlit calls the API server-side, so CORS is not needed and stays
disabled. Configure `CORS_ALLOW_ORIGINS` only if a browser client calls the API
directly.

### Applying migrations safely

```bash
# Always back up first. Migrations are forward-only in practice.
pg_dump "$DATABASE_URL" > backup_before_migrate.sql

# From the backend directory, or via the container:
cd backend && alembic upgrade head

# Check what would run without applying it:
alembic upgrade head --sql
```

Never run `alembic downgrade base`, `drop_all`, or any destructive reset
against a production database. The test suite is guarded: it refuses to run
destructive tests against any database whose name does not end in `_test`.

## Production checklist

- [ ] `APP_ENV=production` (or `staging`) is set.
- [ ] `DATABASE_URL` points at a managed database with automated backups.
- [ ] `JWT_SECRET` is a fresh, randomly generated value, not reused elsewhere.
- [ ] `alembic upgrade head` has been applied and `alembic current` matches head.
- [ ] `GET /health` returns `{"status": "ok"}` from the deployed backend.
- [ ] The frontend's `BACKEND_API_URL` points at the deployed backend.
- [ ] TLS terminates at a reverse proxy in front of both services.
- [ ] `/docs` returns 404 on the production backend.
- [ ] No `.env` / `.env.production` file is committed.


## Project structure

```
spendwise-ai/
├── backend/
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py                    # migration environment
│   │   ├── script.py.mako
│   │   └── versions/0001_initial_schema.py
│   ├── app/
│   │   ├── main.py                   # FastAPI app factory
│   │   ├── config.py                 # settings from environment
│   │   ├── constants.py              # categories, currencies, enums, limits
│   │   ├── database.py               # engine, session, get_db
│   │   ├── api/
│   │   │   ├── deps.py               # current user from JWT
│   │   │   └── routes/               # auth, expenses, lifestyle, analytics,
│   │   │                             # insights, predictions
│   │   ├── ml/                       # pure analytics/ML package (no DB/HTTP)
│   │   ├── models/{user,expense,lifestyle_log,budget}.py
│   │   ├── schemas/{common,user,expense,lifestyle,analytics}.py
│   │   ├── security/{passwords,tokens}.py
│   │   └── services/                 # user, expense, lifestyle, analytics
│   └── tests/
├── frontend/
│   ├── streamlit_app.py              # entry point and routing
│   ├── api_client.py                 # HTTP client for the backend
│   ├── app_state.py                  # session, auth and formatting helpers
│   ├── components/ui.py              # design system and shared widgets
│   ├── views/                        # one module per page
│   ├── config.py                     # constants and attribution
│   └── tests/
├── docs/                             # Project documentation
├── .env.example                      # Environment template (no secrets)
├── pyproject.toml
├── pytest.ini
├── ruff.toml
└── README.md
```

Folders and modules for future features are created only when the batch that
needs them begins.

## Documentation

- [Architecture summary](docs/architecture.md)

## Contributor

**Developed by Jaidul Islam.**
