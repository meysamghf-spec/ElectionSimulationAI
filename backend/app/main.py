"""FastAPI application."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import Settings, get_settings
from app.db.migrate import mark_interrupted, upgrade_database
from app.db.session import build_session_factory
from app.errors import AppError
from app.security import PUBLIC_PATHS, BodyLimitMiddleware, error_body, token_matches
from app.services.executor import SimulationExecutor

logger = logging.getLogger("electionsim")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
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
        session = factory()
        try:
            interrupted = mark_interrupted(session)
            if interrupted:
                logger.warning("Marked %s interrupted simulations as failed", interrupted)
        finally:
            session.close()
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
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload_bytes)

    @app.middleware("http")
    async def protect(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = str(uuid.uuid4())
        path = request.url.path
        if settings.api_token and request.method != "OPTIONS" and path not in PUBLIC_PATHS:
            header = request.headers.get("authorization", "")
            presented = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
            if not presented or not token_matches(presented, settings.api_token):
                response = JSONResponse(
                    error_body("unauthorized", "A valid API token is required."),
                    status_code=401,
                )
                response.headers["X-Request-ID"] = request_id
                return response
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

    @app.get("/")
    def root() -> dict[str, str]:
        return {
            "name": "ElectionSimulationAI",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    return app


app = create_app()
