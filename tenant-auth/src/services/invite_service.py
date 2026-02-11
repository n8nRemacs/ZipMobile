import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta

from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def create_invite(tenant_id: str, invited_by: str, phone: str | None, email: str | None, role: str) -> dict:
    """Create an invitation for a sub-user."""
    if not phone and not email:
        raise ValueError("Either phone or email is required")

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    sb = get_supabase()
    resp = sb.table("tenant_invites").insert({
        "tenant_id": tenant_id,
        "invited_by": invited_by,
        "phone": phone,
        "email": email,
        "role": role,
        "status": "pending",
        "token_hash": token_hash,
        "expires_at": expires_at,
    }).execute()

    if not resp.data:
        raise ValueError("Failed to create invite")

    row = resp.data[0]
    row["invite_token"] = raw_token
    return row


def list_invites(tenant_id: str) -> list[dict]:
    """List pending invites for a tenant."""
    sb = get_supabase()
    resp = (
        sb.table("tenant_invites")
        .select("id,tenant_id,invited_by,phone,email,role,status,expires_at,created_at")
        .eq("tenant_id", tenant_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data


def cancel_invite(invite_id: str, tenant_id: str) -> bool:
    """Cancel a pending invite."""
    sb = get_supabase()
    resp = (
        sb.table("tenant_invites")
        .update({"status": "cancelled"})
        .eq("id", invite_id)
        .eq("tenant_id", tenant_id)
        .eq("status", "pending")
        .execute()
    )
    return len(resp.data) > 0


def accept_invite(token: str, phone: str, name: str) -> dict:
    """
    Accept an invite by token.
    Creates a new tenant_user linked to the invite's tenant.
    Returns the created user.
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    sb = get_supabase()

    resp = (
        sb.table("tenant_invites")
        .select("*")
        .eq("token_hash", token_hash)
        .eq("status", "pending")
        .execute()
    )

    if not resp.data:
        raise ValueError("Invalid or expired invite")

    invite = resp.data[0]

    # Check expiration
    expires_at = datetime.fromisoformat(invite["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        sb.table("tenant_invites").update({"status": "expired"}).eq("id", invite["id"]).execute()
        raise ValueError("Invite has expired")

    # Check if phone is already registered
    existing = sb.table("tenant_users").select("id").eq("phone", phone).execute()
    if existing.data:
        raise ValueError("Phone number already registered")

    # Create user
    user_resp = sb.table("tenant_users").insert({
        "tenant_id": invite["tenant_id"],
        "phone": phone,
        "email": invite.get("email"),
        "name": name,
        "role": invite["role"],
        "phone_verified": False,
        "email_verified": False,
    }).execute()

    if not user_resp.data:
        raise ValueError("Failed to create user")

    # Mark invite as accepted
    sb.table("tenant_invites").update({"status": "accepted"}).eq("id", invite["id"]).execute()

    return user_resp.data[0]
