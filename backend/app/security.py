"""Request limits and optional bearer-token authentication."""

from __future__ import annotations

import hashlib
import ipaddress
import secrets
import threading
import time
from collections import defaultdict, deque

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PUBLIC_PATHS = {
    "/health",
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


def trusted_proxy_problems(raw: str) -> list[str]:
    """Reject missing, invalid, or world-wide proxy networks."""

    if not raw.strip():
        return [
            "TRUSTED_PROXY_CIDRS must list the Docker networks allowed to send X-Forwarded-For. "
            "An empty list ignores that header."
        ]
    problems: list[str] = []
    networks = 0
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            network = ipaddress.ip_network(item, strict=False)
        except ValueError:
            problems.append("TRUSTED_PROXY_CIDRS contains an invalid network.")
            continue
        networks += 1
        if network.prefixlen == 0:
            problems.append(
                "TRUSTED_PROXY_CIDRS must not include a world-wide network such as 0.0.0.0/0 or ::/0."
            )
    if networks == 0 and not problems:
        problems.append("TRUSTED_PROXY_CIDRS must list at least one network.")
    return problems


def parse_trusted_networks(raw: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        networks.append(ipaddress.ip_network(item, strict=False))
    return networks


def single_forwarded_ip(header: str | None) -> str | None:
    """Accept exactly one IP. A chain, a blank, or garbage is not a client address."""

    if header is None:
        return None
    value = header.strip()
    if not value or "," in value or any(character.isspace() for character in value):
        return None
    candidate = value[1:-1] if value.startswith("[") and value.endswith("]") else value
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def peer_is_trusted(peer: str | None, networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network]) -> bool:
    if not peer or not networks:
        return False
    try:
        address = ipaddress.ip_address(peer)
    except ValueError:
        return False
    return any(address in network for network in networks)


def rate_limit_identity(peer: str | None, forwarded_header: str | None, trusted_cidrs: str) -> str:
    """Use a forwarded client IP only when the TCP peer is on a trusted proxy network.

    The limiter is in-memory and per process. This function does not make it distributed.
    """

    try:
        networks = parse_trusted_networks(trusted_cidrs)
    except ValueError:
        networks = []
    if peer_is_trusted(peer, networks):
        forwarded = single_forwarded_ip(forwarded_header)
        if forwarded is not None:
            return forwarded
    if peer:
        return peer
    return "unknown"


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
