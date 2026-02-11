from fastapi import APIRouter, HTTPException, Request

from src.dependencies import get_current_user, require_role
from src.models.billing import PlanInfo, CurrentPlanResponse, UsageStats, UpgradeRequest
from src.services import billing_service

router = APIRouter(prefix="/auth/v1/billing", tags=["Billing"])


@router.get("/plans", response_model=list[PlanInfo])
async def list_plans():
    """List all available billing plans (public)."""
    plans = billing_service.list_plans()
    return [
        PlanInfo(
            id=p["id"],
            name=p["name"],
            price_monthly=float(p["price_monthly"]),
            max_api_keys=p["max_api_keys"],
            max_sessions=p["max_sessions"],
            max_sub_users=p["max_sub_users"],
            features=p.get("features") or {},
        )
        for p in plans
    ]


@router.get("/current", response_model=CurrentPlanResponse)
async def get_current(request: Request):
    """Get current plan and usage (JWT required)."""
    user = get_current_user(request)
    plan = billing_service.get_current_plan(user["tenant_id"])
    if not plan:
        raise HTTPException(status_code=404, detail="No billing plan assigned")

    usage_data = billing_service.get_usage(user["tenant_id"])

    return CurrentPlanResponse(
        plan=PlanInfo(
            id=plan["id"],
            name=plan["name"],
            price_monthly=float(plan["price_monthly"]),
            max_api_keys=plan["max_api_keys"],
            max_sessions=plan["max_sessions"],
            max_sub_users=plan["max_sub_users"],
            features=plan.get("features") or {},
        ),
        usage=UsageStats(**usage_data),
    )


@router.post("/upgrade")
async def upgrade(body: UpgradeRequest, request: Request):
    """Upgrade billing plan (owner only)."""
    user = require_role("owner")(request)
    try:
        billing_service.upgrade_plan(user["tenant_id"], body.plan_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Plan upgraded"}


@router.get("/usage", response_model=UsageStats)
async def get_usage(request: Request):
    """Get detailed usage statistics."""
    user = get_current_user(request)
    usage_data = billing_service.get_usage(user["tenant_id"])
    return UsageStats(**usage_data)
