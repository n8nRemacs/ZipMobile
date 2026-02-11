import logging
from datetime import datetime, timezone

from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def get_user_by_phone(phone: str) -> dict | None:
    """Lookup user by phone number."""
    sb = get_supabase()
    resp = sb.table("tenant_users").select("*").eq("phone", phone).limit(1).execute()
    return resp.data[0] if resp.data else None


def get_user_by_id(user_id: str) -> dict | None:
    """Lookup user by ID."""
    sb = get_supabase()
    resp = sb.table("tenant_users").select("*").eq("id", user_id).limit(1).execute()
    return resp.data[0] if resp.data else None


def _get_default_supervisor_id() -> str:
    """Получить ID dev-supervisor, создать если не существует."""
    sb = get_supabase()
    DEFAULT_ID = "a0000000-0000-0000-0000-000000000001"
    resp = sb.table("supervisors").select("id").eq("id", DEFAULT_ID).limit(1).execute()
    if resp.data:
        return DEFAULT_ID
    # Создаём если нет (seed не выполнялся)
    sb.table("supervisors").insert({
        "id": DEFAULT_ID,
        "name": "DefaultSupervisor",
        "email": "dev@zipmobile.ru",
    }).execute()
    return DEFAULT_ID


def create_tenant_and_user(phone: str, email: str, name: str) -> dict:
    """
    Create a new tenant and its owner user.
    Returns the created user dict.
    """
    sb = get_supabase()

    # Get free plan
    plan_resp = sb.table("billing_plans").select("id").eq("name", "free").limit(1).execute()
    billing_plan_id = plan_resp.data[0]["id"] if plan_resp.data else None

    # Create tenant
    tenant_data = {
        "name": name,
        "phone": phone,
        "email": email,
        "is_active": True,
        "billing_plan_id": billing_plan_id,
        "supervisor_id": _get_default_supervisor_id(),
    }
    tenant_resp = sb.table("tenants").insert(tenant_data).execute()
    if not tenant_resp.data:
        raise ValueError("Failed to create tenant")

    tenant = tenant_resp.data[0]

    # Create owner user
    user_data = {
        "tenant_id": tenant["id"],
        "phone": phone,
        "email": email,
        "name": name,
        "role": "owner",
        "phone_verified": False,
        "email_verified": False,
    }
    user_resp = sb.table("tenant_users").insert(user_data).execute()
    if not user_resp.data:
        raise ValueError("Failed to create user")

    return user_resp.data[0]


def update_user(user_id: str, data: dict) -> dict | None:
    """Update user fields. Returns updated user or None."""
    sb = get_supabase()
    resp = sb.table("tenant_users").update(data).eq("id", user_id).execute()
    return resp.data[0] if resp.data else None


def set_phone_verified(user_id: str) -> None:
    """Mark user's phone as verified."""
    sb = get_supabase()
    sb.table("tenant_users").update({"phone_verified": True}).eq("id", user_id).execute()


def set_email_verified(user_id: str) -> None:
    """Mark user's email as verified."""
    sb = get_supabase()
    sb.table("tenant_users").update({"email_verified": True}).eq("id", user_id).execute()


def change_phone(user_id: str, new_phone: str) -> None:
    """Update user's phone number."""
    sb = get_supabase()
    sb.table("tenant_users").update({"phone": new_phone, "phone_verified": True}).eq("id", user_id).execute()


def change_email(user_id: str, new_email: str) -> None:
    """Update user's email address and mark as verified."""
    sb = get_supabase()
    sb.table("tenant_users").update({"email": new_email, "email_verified": True}).eq("id", user_id).execute()


def get_team_members(tenant_id: str) -> list[dict]:
    """Get all users belonging to a tenant."""
    sb = get_supabase()
    resp = (
        sb.table("tenant_users")
        .select("id,tenant_id,phone,email,name,role,is_active,created_at")
        .eq("tenant_id", tenant_id)
        .order("created_at")
        .execute()
    )
    return resp.data


def remove_team_member(user_id: str, tenant_id: str) -> bool:
    """Deactivate a team member. Cannot remove the owner."""
    sb = get_supabase()
    user_resp = sb.table("tenant_users").select("role").eq("id", user_id).eq("tenant_id", tenant_id).execute()
    if not user_resp.data:
        return False
    if user_resp.data[0]["role"] == "owner":
        raise ValueError("Cannot remove the tenant owner")
    sb.table("tenant_users").update({"is_active": False}).eq("id", user_id).execute()
    return True


def update_role(user_id: str, tenant_id: str, role: str) -> dict | None:
    """Update a user's role within the tenant."""
    sb = get_supabase()
    user_resp = sb.table("tenant_users").select("role").eq("id", user_id).eq("tenant_id", tenant_id).execute()
    if not user_resp.data:
        return None
    if user_resp.data[0]["role"] == "owner":
        raise ValueError("Cannot change the owner's role")
    resp = sb.table("tenant_users").update({"role": role}).eq("id", user_id).execute()
    return resp.data[0] if resp.data else None
