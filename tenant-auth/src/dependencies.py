from fastapi import Request, HTTPException


def get_current_user(request: Request) -> dict:
    """Extract current user from request state (set by JWT middleware)."""
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_role(*allowed_roles: str):
    """Returns a dependency that checks user role."""
    def checker(request: Request) -> dict:
        user = get_current_user(request)
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Requires one of roles: {', '.join(allowed_roles)}",
            )
        return user
    return checker


def require_email_verified(request: Request) -> dict:
    """Dependency that ensures the user's email is verified."""
    user = get_current_user(request)
    if not user.get("email_verified", False):
        raise HTTPException(
            status_code=403,
            detail="Email verification required for this action",
        )
    return user


def require_internal_secret(request: Request) -> None:
    """Validate X-Internal-Secret header for internal API calls."""
    from src.config import settings
    secret = request.headers.get("X-Internal-Secret")
    if not secret or secret != settings.internal_secret:
        raise HTTPException(status_code=401, detail="Invalid internal secret")
