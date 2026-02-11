import logging
from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def list_plans() -> list[dict]:
    """List all active billing plans."""
    sb = get_supabase()
    resp = (
        sb.table("billing_plans")
        .select("*")
        .eq("is_active", True)
        .order("price_monthly")
        .execute()
    )
    return resp.data


def get_plan(plan_id: str) -> dict | None:
    """Get a specific billing plan."""
    sb = get_supabase()
    resp = sb.table("billing_plans").select("*").eq("id", plan_id).limit(1).execute()
    return resp.data[0] if resp.data else None


def get_current_plan(tenant_id: str) -> dict | None:
    """Get the current plan for a tenant."""
    sb = get_supabase()
    tenant_resp = sb.table("tenants").select("billing_plan_id").eq("id", tenant_id).limit(1).execute()
    if not tenant_resp.data or not tenant_resp.data[0].get("billing_plan_id"):
        return None

    plan_id = tenant_resp.data[0]["billing_plan_id"]
    return get_plan(plan_id)


def get_usage(tenant_id: str) -> dict:
    """Get current resource usage for a tenant."""
    sb = get_supabase()

    # Count API keys
    keys_resp = sb.table("api_keys").select("id").eq("tenant_id", tenant_id).eq("is_active", True).execute()
    api_keys_used = len(keys_resp.data)

    # Count active avito sessions
    sessions_resp = sb.table("avito_sessions").select("id").eq("tenant_id", tenant_id).eq("is_active", True).execute()
    sessions_used = len(sessions_resp.data)

    # Count sub-users
    users_resp = sb.table("tenant_users").select("id").eq("tenant_id", tenant_id).eq("is_active", True).execute()
    sub_users_used = len(users_resp.data)

    # Get plan limits
    plan = get_current_plan(tenant_id)
    if plan:
        return {
            "api_keys_used": api_keys_used,
            "api_keys_limit": plan.get("max_api_keys", 1),
            "sessions_used": sessions_used,
            "sessions_limit": plan.get("max_sessions", 1),
            "sub_users_used": sub_users_used,
            "sub_users_limit": plan.get("max_sub_users", 1),
        }

    return {
        "api_keys_used": api_keys_used,
        "api_keys_limit": 1,
        "sessions_used": sessions_used,
        "sessions_limit": 1,
        "sub_users_used": sub_users_used,
        "sub_users_limit": 1,
    }


def upgrade_plan(tenant_id: str, plan_id: str) -> bool:
    """Upgrade a tenant's billing plan."""
    plan = get_plan(plan_id)
    if not plan:
        raise ValueError("Plan not found")

    sb = get_supabase()
    resp = sb.table("tenants").update({"billing_plan_id": plan_id}).eq("id", tenant_id).execute()
    return len(resp.data) > 0
