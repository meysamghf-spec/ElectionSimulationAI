"""FastAPI application."""

from __future__ import annotations

import logging
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.auth.bootstrap import ensure_initial_admin
from app.auth.sessions import CSRF_HEADER, SESSION_COOKIE, authenticated_user
from app.config import Settings, get_settings, validate_production
from app.db.migrate import mark_interrupted, upgrade_database
from app.db.session import build_session_factory
from app.errors import AppError
from app.security import BodyLimitMiddleware, error_body, is_anonymous_ok, token_matches
from app.services.executor import SimulationExecutor

logger = logging.getLogger("electionsim")
_UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def _attach_account(request: Request) -> None:
    factory = getattr(request.app.state, "session_factory", None)
    token = request.cookies.get(SESSION_COOKIE, "")
    if factory is None or not token:
        return
    db = factory()
    try:
        found = authenticated_user(db, token)
    finally:
        db.close()
    if found is None:
        return
    user, auth_row = found
    request.state.owner_id = user.id
    request.state.user_email = user.email
    request.state.csrf_token = auth_row.csrf_token


def _csrf_ok(request: Request) -> bool:
    presented = request.headers.get(CSRF_HEADER, "")
    expected = request.state.csrf_token or ""
    if not presented or not expected or len(presented) != len(expected):
        return False
    return secrets.compare_digest(presented, expected)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.normalized_auth_mode not in {"development", "private", "accounts"}:
        raise RuntimeError("AUTH_MODE must be development, private, or accounts.")
    validate_production(settings)
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        upgrade_database(settings)
        engine, factory = build_session_factory(settings)
        app.state.engine = engine
        app.state.session_factory = factory
        app.state.executor = SimulationExecutor(factory, settings)
        from app.security import RateLimiter

        app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
        app.state.auth_rate_limiter = RateLimiter(settings.auth_rate_limit_per_minute)
        session = factory()
        try:
            interrupted = mark_interrupted(session)
            if interrupted:
                logger.warning("Marked %s interrupted simulations as failed", interrupted)
            ensure_initial_admin(session, settings)
        finally:
            session.close()
        if settings.normalized_auth_mode == "private" and not settings.api_token:
            logger.warning("AUTH_MODE=private but API_TOKEN is empty. Data routes will reject every request.")
        yield
        app.state.executor.shutdown()
        engine.dispose()

    app = FastAPI(
        title="ElectionSimulationAI",
        version="1.0.0",
        summary="Hypothetical election simulation and statistical analysis.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes)

    @app.middleware("http")
    async def protect(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())
        path = request.url.path
        method = request.method
        request.state.owner_id = None
        request.state.user_email = None
        request.state.csrf_token = None

        def deny(status_code: int, code: str, message: str) -> JSONResponse:
            response = JSONResponse(error_body(code, message), status_code=status_code)
            response.headers["X-Request-ID"] = request_id
            return response

        if method != "OPTIONS":
            mode = settings.normalized_auth_mode
            if mode == "accounts":
                _attach_account(request)
                if not is_anonymous_ok(path, method, mode):
                    if request.state.owner_id is None:
                        return deny(401, "unauthorized", "Sign in to continue.")
                    if method in _UNSAFE and not _csrf_ok(request):
                        return deny(
                            403,
                            "csrf",
                            "The security token did not match. Refresh the page and try again.",
                        )
            elif mode == "private" or settings.api_token:
                if not is_anonymous_ok(path, method, "private"):
                    header = request.headers.get("authorization", "")
                    presented = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
                    expected = settings.api_token or ""
                    if not expected or not presented or not token_matches(presented, expected):
                        return deny(401, "unauthorized", "A valid API token is required.")
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            error_body(exc.code, exc.message, exc.details),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            error_body("validation_error", "The request was rejected.", details),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            error_body("internal_error", "The server could not complete the request."),
            status_code=500,
        )

    app.include_router(router)

    @app.get("/health")
    def root_health(request: Request) -> JSONResponse:
        """Unauthenticated liveness plus database check for proxies and uptime monitors."""
        from sqlalchemy import text

        database = "ok"
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception:
            database = "unavailable"
        healthy = database == "ok"
        return JSONResponse(
            {"status": "ok" if healthy else "degraded", "database": database},
            status_code=200 if healthy else 503,
        )

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "ElectionSimulationAI",
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
