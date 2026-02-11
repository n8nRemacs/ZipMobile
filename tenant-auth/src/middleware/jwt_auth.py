import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.services.jwt_service import verify_access_token
from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def _error(status: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail})


# Paths that don't require JWT
PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
}

PUBLIC_PREFIXES = [
    "/auth/v1/register",
    "/auth/v1/login",
    "/auth/v1/verify-otp",
    "/auth/v1/refresh",
    "/auth/v1/billing/plans",
    "/auth/v1/billing/v2/services",
    "/auth/v1/billing/v2/seats",
    "/auth/v1/team/invites/",  # accept invite (token in URL)
    "/auth/v1/telegram/",  # Telegram Mini App auth (initData-based)
]


class JwtAuthMiddleware(BaseHTTPMiddleware):
    """Resolve JWT Bearer token -> user context on protected endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)

        # Skip auth for public API prefixes
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Skip auth for internal API (uses X-Internal-Secret)
        if path.startswith("/auth/v1/tenants/"):
            return await call_next(request)

        # Require JWT for all other /auth/v1/* paths
        if not path.startswith("/auth/v1/"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return _error(401, "Missing or invalid Authorization header")

        token = auth_header[7:]

        try:
            payload = verify_access_token(token)
        except ValueError as e:
            return _error(401, str(e))

        # Load user from DB
        sb = get_supabase()
        user_resp = sb.table("tenant_users").select("*").eq("id", payload["sub"]).execute()
        if not user_resp.data:
            return _error(401, "User not found")

        user = user_resp.data[0]
        if not user.get("is_active", True):
            return _error(403, "User is deactivated")

        request.state.current_user = user
        request.state.jwt_payload = payload

        return await call_next(request)
