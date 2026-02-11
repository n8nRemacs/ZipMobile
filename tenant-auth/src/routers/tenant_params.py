from fastapi import APIRouter, HTTPException, Depends, Request

from src.dependencies import require_internal_secret
from src.storage.supabase import get_supabase

router = APIRouter(prefix="/auth/v1/tenants", tags=["Internal"])


@router.get("/{tenant_id}/params")
async def get_tenant_params(tenant_id: str, request: Request):
    """Internal API: Get tenant parameters for xapi. Protected by X-Internal-Secret."""
    require_internal_secret(request)

    sb = get_supabase()
    tenant_resp = sb.table("tenants").select("*").eq("id", tenant_id).limit(1).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Tenant not found")

    tenant = tenant_resp.data[0]

    # Get toolkit if assigned
    toolkit = None
    if tenant.get("toolkit_id"):
        tk_resp = sb.table("toolkits").select("*").eq("id", tenant["toolkit_id"]).execute()
        if tk_resp.data:
            toolkit = tk_resp.data[0]

    # Get billing plan
    plan = None
    if tenant.get("billing_plan_id"):
        plan_resp = sb.table("billing_plans").select("*").eq("id", tenant["billing_plan_id"]).execute()
        if plan_resp.data:
            plan = plan_resp.data[0]

    return {
        "tenant": tenant,
        "toolkit": toolkit,
        "billing_plan": plan,
    }


@router.get("/by-api-key-hash/{key_hash}")
async def get_tenant_by_key_hash(key_hash: str, request: Request):
    """Internal API: Resolve tenant by API key hash. Protected by X-Internal-Secret."""
    require_internal_secret(request)

    sb = get_supabase()

    # Lookup API key
    key_resp = sb.table("api_keys").select("*").eq("key_hash", key_hash).eq("is_active", True).execute()
    if not key_resp.data:
        raise HTTPException(status_code=404, detail="API key not found")

    key_row = key_resp.data[0]

    # Lookup tenant
    tenant_resp = sb.table("tenants").select("*").eq("id", key_row["tenant_id"]).execute()
    if not tenant_resp.data:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return {
        "tenant": tenant_resp.data[0],
        "api_key": {
            "id": key_row["id"],
            "tenant_id": key_row["tenant_id"],
            "name": key_row.get("name"),
            "is_active": key_row["is_active"],
        },
    }
