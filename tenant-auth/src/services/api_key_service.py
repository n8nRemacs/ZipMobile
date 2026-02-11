import hashlib
import secrets
import logging
from datetime import datetime, timezone

from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (plaintext, hash)."""
    plaintext = f"ak_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, key_hash


def create_api_key(tenant_id: str, name: str) -> dict:
    """Create a new API key for a tenant. Returns dict with plaintext_key."""
    plaintext, key_hash = generate_api_key()

    sb = get_supabase()
    resp = sb.table("api_keys").insert({
        "tenant_id": tenant_id,
        "key_hash": key_hash,
        "name": name,
        "is_active": True,
    }).execute()

    if not resp.data:
        raise ValueError("Failed to create API key")

    row = resp.data[0]
    return {
        "id": row["id"],
        "tenant_id": row["tenant_id"],
        "name": row.get("name"),
        "is_active": row["is_active"],
        "last_used_at": row.get("last_used_at"),
        "created_at": row.get("created_at"),
        "plaintext_key": plaintext,
    }


def list_api_keys(tenant_id: str) -> list[dict]:
    """List all API keys for a tenant (without hashes)."""
    sb = get_supabase()
    resp = (
        sb.table("api_keys")
        .select("id,tenant_id,name,is_active,last_used_at,created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data


def update_api_key(key_id: str, tenant_id: str, data: dict) -> dict | None:
    """Update an API key's name or status."""
    sb = get_supabase()
    # Verify ownership
    check = sb.table("api_keys").select("id").eq("id", key_id).eq("tenant_id", tenant_id).execute()
    if not check.data:
        return None

    resp = sb.table("api_keys").update(data).eq("id", key_id).execute()
    return resp.data[0] if resp.data else None


def delete_api_key(key_id: str, tenant_id: str) -> bool:
    """Deactivate an API key."""
    sb = get_supabase()
    check = sb.table("api_keys").select("id").eq("id", key_id).eq("tenant_id", tenant_id).execute()
    if not check.data:
        return False

    sb.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()
    return True


def rotate_api_key(key_id: str, tenant_id: str) -> dict | None:
    """Revoke old key and create a new one with the same name."""
    sb = get_supabase()
    old_resp = sb.table("api_keys").select("*").eq("id", key_id).eq("tenant_id", tenant_id).execute()
    if not old_resp.data:
        return None

    old_key = old_resp.data[0]

    # Deactivate old
    sb.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()

    # Create new with same name
    return create_api_key(tenant_id, old_key.get("name", "Rotated key"))
