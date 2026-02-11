import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta

import jwt

from src.config import settings
from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def create_access_token(user_id: str, tenant_id: str, role: str) -> tuple[str, int]:
    """Create a JWT access token. Returns (token, expires_in_seconds)."""
    expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(expires_delta.total_seconds())


def create_refresh_token(user_id: str, device_info: dict | None = None) -> str:
    """Create and store a refresh token. Returns the raw token string."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)).isoformat()

    sb = get_supabase()
    sb.table("refresh_tokens").insert({
        "token_hash": token_hash,
        "user_id": user_id,
        "device_info": device_info or {},
        "expires_at": expires_at,
    }).execute()

    return raw_token


def create_token_pair(user_id: str, tenant_id: str, role: str, device_info: dict | None = None) -> dict:
    """Create both access and refresh tokens."""
    access_token, expires_in = create_access_token(user_id, tenant_id, role)
    refresh_token = create_refresh_token(user_id, device_info)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }


def verify_access_token(token: str) -> dict:
    """Verify and decode an access token. Returns payload dict."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token expired")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"Invalid token: {e}")

    if payload.get("type") != "access":
        raise ValueError("Not an access token")

    return payload


def rotate_refresh_token(raw_token: str) -> dict:
    """
    Rotate a refresh token: revoke old one, create new pair.
    Returns new token pair dict.
    """
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .select("*")
        .eq("token_hash", token_hash)
        .eq("is_revoked", False)
        .execute()
    )

    if not resp.data:
        raise ValueError("Invalid or revoked refresh token")

    row = resp.data[0]

    # Check expiration
    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        sb.table("refresh_tokens").update({"is_revoked": True}).eq("id", row["id"]).execute()
        raise ValueError("Refresh token expired")

    # Revoke old token
    sb.table("refresh_tokens").update({"is_revoked": True}).eq("id", row["id"]).execute()

    # Lookup user to get tenant_id and role
    user_resp = sb.table("tenant_users").select("*").eq("id", row["user_id"]).execute()
    if not user_resp.data:
        raise ValueError("User not found")

    user = user_resp.data[0]

    # Create new pair
    return create_token_pair(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        role=user["role"],
        device_info=row.get("device_info"),
    )


def revoke_refresh_token(raw_token: str) -> bool:
    """Revoke a single refresh token."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .update({"is_revoked": True})
        .eq("token_hash", token_hash)
        .eq("is_revoked", False)
        .execute()
    )
    return len(resp.data) > 0


def revoke_all_user_tokens(user_id: str) -> int:
    """Revoke all refresh tokens for a user. Returns count revoked."""
    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .select("id")
        .eq("user_id", user_id)
        .eq("is_revoked", False)
        .execute()
    )
    count = 0
    for row in resp.data:
        sb.table("refresh_tokens").update({"is_revoked": True}).eq("id", row["id"]).execute()
        count += 1
    return count


def get_user_sessions(user_id: str) -> list[dict]:
    """Get all active (non-revoked, non-expired) refresh tokens for a user."""
    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .select("id,device_info,created_at,expires_at")
        .eq("user_id", user_id)
        .eq("is_revoked", False)
        .order("created_at", desc=True)
        .execute()
    )
    now = datetime.now(timezone.utc)
    sessions = []
    for row in resp.data:
        expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if expires_at > now:
            sessions.append(row)
    return sessions


def revoke_session(session_id: str, user_id: str) -> bool:
    """Revoke a specific session (refresh token) by its ID, scoped to user."""
    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .update({"is_revoked": True})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .eq("is_revoked", False)
        .execute()
    )
    return len(resp.data) > 0


def revoke_other_sessions(user_id: str, current_token_hash: str) -> int:
    """Revoke all sessions except the current one."""
    sb = get_supabase()
    resp = (
        sb.table("refresh_tokens")
        .select("id,token_hash")
        .eq("user_id", user_id)
        .eq("is_revoked", False)
        .execute()
    )
    count = 0
    for row in resp.data:
        if row["token_hash"] != current_token_hash:
            sb.table("refresh_tokens").update({"is_revoked": True}).eq("id", row["id"]).execute()
            count += 1
    return count
