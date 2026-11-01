"""FastAPI application factory."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    auth,
    budgets,
    expenses,
    export,
    insights,
    lifestyle,
    predictions,
)
from app.config import Settings, get_settings

logger = logging.getLogger("spendwise")


def _configure_logging(level: str) -> None:
    """Configure application logging once, at a non-verbose default level."""
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _validate_production_configuration(settings: Settings) -> None:
    """Fail fast when required production settings are missing or unsafe.

    Validates the passed-in ``settings`` rather than re-reading the environment,
    so the check always reflects the configuration the app was built with.
    Never logs the values themselves: only the name of the offending setting.
    """
    if settings.app_env == "development":
        return

    problems: list[str] = []

    secret = settings.jwt_secret.get_secret_value()
    if not secret or "CHANGE_ME" in secret:
        problems.append("JWT_SECRET is not set")

    if not settings.database_url or "CHANGE_ME" in settings.database_url:
        problems.append("DATABASE_URL is not set")

    if "*" in settings.cors_allow_origins:
        problems.append("CORS_ALLOW_ORIGINS must not contain a wildcard")

    if problems:
        # Raising stops the process before it can serve requests insecurely.
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


def create_app() -> FastAPI:
    """Build the FastAPI application instance."""
    settings = get_settings()
    _configure_logging(settings.log_level)
    _validate_production_configuration(settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description=(
            "SpendWise AI - Personal Expense & Lifestyle Intelligence System. "
            "Developed by Jaidul Islam."
        ),
        # Interactive docs are useful locally but expose the full API surface;
        # they are disabled in production unless explicitly re-enabled.
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
    )

    origins = settings.cors_origins
    if origins:
        # Only configured because a browser client calls the API directly.
        # Explicit origins only; credentials are permitted so a cookie or
        # Authorization header can flow, which is why "*" is rejected above.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "Accept"],
        )
        logger.info("CORS enabled for %d origin(s)", len(origins))

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        """Add conservative security headers to every response."""
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    app.include_router(auth.router, prefix="/api")
    app.include_router(expenses.router, prefix="/api")
    app.include_router(lifestyle.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(insights.router, prefix="/api")
    app.include_router(predictions.router, prefix="/api")
    app.include_router(predictions.simulation_router, prefix="/api")
    app.include_router(budgets.router, prefix="/api")
    app.include_router(export.router, prefix="/api")

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        """Liveness probe.

        Deliberately minimal: it must not disclose the environment, versions of
        dependencies, or any configuration detail.
        """
        return {"status": "ok"}

    return app


app = create_app()
