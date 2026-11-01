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

Database-backed tests use a separate database (default `spendwise_test`).
Create it with `createdb -U postgres spendwise_test` or override the URL with
the `TEST_DATABASE_URL` environment variable. When PostgreSQL is not reachable
those tests are **skipped**, not passed.

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
