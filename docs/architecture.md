# Architecture

**SpendWise AI — Developed by Jaidul Islam.**

This document summarises the approved v3 architecture. Detailed design
documents for the database, security and ML approach are added alongside the
batches that implement them.

## Components

| Component | Responsibility |
| --- | --- |
| Streamlit frontend | Presentation only. Calls the backend API over HTTP. Never accesses the database. |
| FastAPI backend | Validation, authorization, business logic, and the in-process insights/ML package. |
| PostgreSQL | Single source of truth, accessed through SQLAlchemy with Alembic migrations. |

## Data rules

- Every expense belongs to exactly one user, stored in that user's primary
  currency. No cross-currency arithmetic is performed.
- Dates are derived from timestamps using the user's IANA timezone.
- Lifestyle choices are captured both per expense (optional context flags) and
  per day (optional check-in), at distinct grains without duplicated fields.

## Analysis and ML principles

1. Descriptive analytics come first and are always available.
2. Statistical baselines come next, once a user has enough history (the
   7-day/28-day figures are initial heuristics, not guarantees).
3. More complex models are promoted only after time-ordered evaluation shows
   they beat the baseline.
4. Correlation is never presented as causation; sample sizes are always shown.
5. No performance is claimed without measurement, and no dataset is assumed.

## Security principles

- Passwords are always hashed; secrets come from the environment only.
- `user_id` is taken from the verified JWT, never from the request body.
- Cross-user access is covered by mandatory tests.
- CORS is not configured because Streamlit calls the API server-side.
