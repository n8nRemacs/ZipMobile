from fastapi import APIRouter, Request

from src.dependencies import get_current_user
from src.models.billing_v2 import (
    PlatformServiceResponse,
    SeatPackageResponse,
    TenantBillingSummary,
    TenantSubscriptionResponse,
    UsageResponse,
    UsageCounterInfo,
    CheckLimitRequest,
    CheckLimitResponse,
)
from src.services import billing_v2_service

router = APIRouter(prefix="/auth/v1/billing/v2", tags=["billing-v2"])


@router.get("/services", response_model=list[PlatformServiceResponse])
def list_services():
    """List all platform services with their plans. Public endpoint."""
    return billing_v2_service.get_platform_services()


@router.get("/seats", response_model=list[SeatPackageResponse])
def list_seat_packages():
    """List all seat packages with prices. Public endpoint."""
    return billing_v2_service.get_seat_packages()


@router.get("/my", response_model=TenantBillingSummary)
def my_billing(request: Request):
    """Get billing summary for the current tenant. Requires JWT."""
    user = get_current_user(request)
    summary = billing_v2_service.get_tenant_billing_summary(user["tenant_id"])
    return summary


@router.get("/usage", response_model=list[UsageResponse])
def my_usage(request: Request):
    """Get today's usage counters for all services. Requires JWT."""
    user = get_current_user(request)
    raw = billing_v2_service.get_usage_today(user["tenant_id"])
    result = []
    for item in raw:
        counters = {}
        for k, v in item["counters"].items():
            counters[k] = UsageCounterInfo(used=v["used"], limit=v["limit"])
        result.append(UsageResponse(service_slug=item["service_slug"], counters=counters))
    return result


@router.post("/check-limit", response_model=CheckLimitResponse)
def check_limit(body: CheckLimitRequest, request: Request):
    """Check if a daily limit allows one more usage. Requires JWT."""
    user = get_current_user(request)
    result = billing_v2_service.check_limit(user["tenant_id"], body.service, body.counter)
    return result
