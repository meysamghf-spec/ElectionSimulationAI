"""Request limits and optional bearer-token authentication."""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PUBLIC_PATHS = {
    "/api/v1/health",
    "/api/v1/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}

_ACCOUNT_PUBLIC_GET = {
    "/api/v1/meta",
    "/api/v1/imports/schemas",
    "/api/v1/auth/me",
}
_ACCOUNT_PUBLIC_POST = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
}


def is_anonymous_ok(path: str, method: str, auth_mode: str) -> bool:
    """Paths a caller may use without a session or deployment token."""

    if path in PUBLIC_PATHS:
        return True
    if auth_mode != "accounts":
        return False
    if method == "GET" and (path in _ACCOUNT_PUBLIC_GET or path.startswith("/api/v1/content/")):
        return True
    if method == "GET" and (path == "/api/v1/examples" or path.startswith("/api/v1/examples/")):
        return True
    return method == "POST" and path in _ACCOUNT_PUBLIC_POST


def token_matches(presented: str, expected: str) -> bool:
    return secrets.compare_digest(
        hashlib.sha256(presented.encode()).digest(),
        hashlib.sha256(expected.encode()).digest(),
    )


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            return True


def error_body(code: str, message: str, details: list[dict[str, str]] | None = None) -> dict[str, object]:
    return {"error": {"code": code, "message": message, "details": details or []}}


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        messages: list[Message] = []
        size = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                response = JSONResponse(
                    error_body("payload_too_large", f"Request body exceeds {self.max_bytes} bytes."),
                    status_code=413,
                )
                await response(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        index = 0

        async def replay() -> Message:
            nonlocal index
            if index < len(messages):
                message = messages[index]
                index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)
