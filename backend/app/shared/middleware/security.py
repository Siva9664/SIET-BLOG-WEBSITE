import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import Environment, settings

# In-memory sliding window rate-limiter: client_ip -> list of timestamps
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)

# Rate limits: (max_requests, window_seconds)
RATE_LIMIT_RULES: Dict[str, Tuple[int, int]] = {
    "/api/v1/auth/login": (10, 60),  # Max 10 login attempts per minute per IP
    "/api/v1/admin/magazine/upload": (15, 60),  # Max 15 magazine uploads per minute per IP
    "/api/v1/admin/media/upload": (20, 60),  # Max 20 media uploads per minute per IP
}


def _is_rate_limited(ip: str, path: str) -> bool:
    rule = RATE_LIMIT_RULES.get(path)
    if not rule:
        return False
    max_reqs, window = rule
    now = time.time()
    key = f"{ip}:{path}"
    
    # Filter timestamps within window
    timestamps = [t for t in _rate_limit_store[key] if now - t < window]
    _rate_limit_store[key] = timestamps

    if len(timestamps) >= max_reqs:
        return True

    _rate_limit_store[key].append(now)
    return False


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "127.0.0.1"
        path = request.url.path

        # Check Rate Limiting on sensitive routes
        if _is_rate_limited(client_ip, path):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please wait a minute before retrying."},
            )

        response: Response = await call_next(request)

        # Apply Hardened Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        if settings.ENV == Environment.production or request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
