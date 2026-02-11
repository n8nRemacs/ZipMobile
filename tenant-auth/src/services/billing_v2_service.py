import logging
from datetime import date

from src.storage.supabase import get_supabase

logger = logging.getLogger("tenant-auth")


def get_platform_services() -> list[dict]:
    """Return all active platform services with their plans."""
    sb = get_supabase()
    services_resp = sb.table("platform_services").select("*").eq("is_active", True).order("sort_order").execute()
    services = services_resp.data

    for svc in services:
        plans_resp = (
            sb.table("service_plans")
            .select("*")
            .eq("service_id", svc["id"])
            .eq("is_active", True)
            .order("sort_order")
            .execute()
        )
        svc["plans"] = plans_resp.data

    return services


def get_service_plans(service_slug: str) -> list[dict]:
    """Return plans for a specific service by slug."""
    sb = get_supabase()
    svc_resp = sb.table("platform_services").select("id").eq("slug", service_slug).limit(1).execute()
    if not svc_resp.data:
        return []
    service_id = svc_resp.data[0]["id"]
    plans_resp = (
        sb.table("service_plans")
        .select("*")
        .eq("service_id", service_id)
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return plans_resp.data


def get_seat_packages() -> list[dict]:
    """Return all active seat packages."""
    sb = get_supabase()
    resp = sb.table("seat_packages").select("*").eq("is_active", True).order("sort_order").execute()
    return resp.data


def get_tenant_subscriptions(tenant_id: str) -> list[dict]:
    """Return all subscriptions for a tenant with service and plan info."""
    sb = get_supabase()
    subs_resp = sb.table("tenant_subscriptions").select("*").eq("tenant_id", tenant_id).execute()
    result = []
    for sub in subs_resp.data:
        # Get service info
        svc_resp = sb.table("platform_services").select("slug,name").eq("id", sub["service_id"]).limit(1).execute()
        svc = svc_resp.data[0] if svc_resp.data else {}
        # Get plan info
        plan_resp = sb.table("service_plans").select("slug,name,price_monthly,limits").eq("id", sub["plan_id"]).limit(1).execute()
        plan = plan_resp.data[0] if plan_resp.data else {}
        result.append({
            "service_slug": svc.get("slug", ""),
            "service_name": svc.get("name", ""),
            "plan_slug": plan.get("slug", ""),
            "plan_name": plan.get("name", ""),
            "price_monthly": float(plan.get("price_monthly", 0)),
            "limits": plan.get("limits", {}),
            "status": sub["status"],
        })
    return result


def get_tenant_seat_info(tenant_id: str) -> dict:
    """Return seat package info and usage for a tenant."""
    sb = get_supabase()

    # Get seat subscription
    seat_sub_resp = sb.table("tenant_seat_subscriptions").select("*").eq("tenant_id", tenant_id).limit(1).execute()

    if not seat_sub_resp.data:
        # No seat subscription — default free (1 seat)
        return {
            "package": None,
            "seats_used": 1,
            "seats_total": 1,
        }

    seat_sub = seat_sub_resp.data[0]
    pkg_resp = sb.table("seat_packages").select("*").eq("id", seat_sub["package_id"]).limit(1).execute()
    package = pkg_resp.data[0] if pkg_resp.data else None

    # Count team members
    members_resp = sb.table("tenant_users").select("id").eq("tenant_id", tenant_id).eq("is_active", True).execute()
    seats_used = len(members_resp.data)

    return {
        "package": package,
        "seats_used": seats_used,
        "seats_total": package["max_seats"] if package else 1,
    }


def create_free_subscriptions(tenant_id: str) -> None:
    """Create free-plan subscriptions for all services + free seat package for a new tenant."""
    sb = get_supabase()

    # Get all services
    services_resp = sb.table("platform_services").select("id").eq("is_active", True).execute()

    for svc in services_resp.data:
        # Find free plan for this service
        plan_resp = (
            sb.table("service_plans")
            .select("id")
            .eq("service_id", svc["id"])
            .eq("slug", "free")
            .limit(1)
            .execute()
        )
        if not plan_resp.data:
            continue

        # Create subscription (ignore conflict if already exists)
        try:
            sb.table("tenant_subscriptions").insert({
                "tenant_id": tenant_id,
                "service_id": svc["id"],
                "plan_id": plan_resp.data[0]["id"],
                "status": "active",
            }).execute()
        except Exception as e:
            logger.debug("Subscription already exists or error: %s", e)

    # Create free seat subscription
    free_pkg_resp = sb.table("seat_packages").select("id").eq("slug", "free").limit(1).execute()
    if free_pkg_resp.data:
        try:
            sb.table("tenant_seat_subscriptions").insert({
                "tenant_id": tenant_id,
                "package_id": free_pkg_resp.data[0]["id"],
                "status": "active",
            }).execute()
        except Exception as e:
            logger.debug("Seat subscription already exists or error: %s", e)

    logger.info("Created free subscriptions for tenant %s", tenant_id)


def check_limit(tenant_id: str, service_slug: str, counter_name: str) -> dict:
    """Check daily limit. Returns {"allowed": bool, "used": int, "limit": int|"unlimited"}."""
    sb = get_supabase()

    # Find service
    svc_resp = sb.table("platform_services").select("id").eq("slug", service_slug).limit(1).execute()
    if not svc_resp.data:
        return {"allowed": False, "used": 0, "limit": 0}
    service_id = svc_resp.data[0]["id"]

    # Find tenant subscription for this service
    sub_resp = (
        sb.table("tenant_subscriptions")
        .select("plan_id")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    if not sub_resp.data:
        return {"allowed": False, "used": 0, "limit": 0}

    # Get plan limits
    plan_resp = sb.table("service_plans").select("limits").eq("id", sub_resp.data[0]["plan_id"]).limit(1).execute()
    if not plan_resp.data:
        return {"allowed": False, "used": 0, "limit": 0}

    limits = plan_resp.data[0]["limits"]
    max_limit = limits.get(counter_name, 0)

    # -1 means unlimited
    if max_limit == -1:
        return {"allowed": True, "used": 0, "limit": "unlimited"}

    # Get today's usage
    today = date.today().isoformat()
    usage_resp = (
        sb.table("usage_counters")
        .select("used")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .eq("counter_name", counter_name)
        .eq("date", today)
        .limit(1)
        .execute()
    )
    used = usage_resp.data[0]["used"] if usage_resp.data else 0

    return {
        "allowed": used < max_limit,
        "used": used,
        "limit": max_limit,
    }


def increment_usage(tenant_id: str, service_slug: str, counter_name: str) -> dict:
    """Increment daily usage counter by 1. Returns {"used": int, "limit": int|"unlimited"}."""
    sb = get_supabase()

    # Find service
    svc_resp = sb.table("platform_services").select("id").eq("slug", service_slug).limit(1).execute()
    if not svc_resp.data:
        raise ValueError(f"Service not found: {service_slug}")
    service_id = svc_resp.data[0]["id"]

    today = date.today().isoformat()

    # Try to get existing counter
    usage_resp = (
        sb.table("usage_counters")
        .select("id,used")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .eq("counter_name", counter_name)
        .eq("date", today)
        .limit(1)
        .execute()
    )

    if usage_resp.data:
        # Update existing
        row = usage_resp.data[0]
        new_used = row["used"] + 1
        sb.table("usage_counters").update({"used": new_used}).eq("id", row["id"]).execute()
    else:
        # Insert new
        new_used = 1
        sb.table("usage_counters").insert({
            "tenant_id": tenant_id,
            "service_id": service_id,
            "counter_name": counter_name,
            "date": today,
            "used": 1,
        }).execute()

    # Get limit from plan
    sub_resp = (
        sb.table("tenant_subscriptions")
        .select("plan_id")
        .eq("tenant_id", tenant_id)
        .eq("service_id", service_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )
    limit_val: int | str = 0
    if sub_resp.data:
        plan_resp = sb.table("service_plans").select("limits").eq("id", sub_resp.data[0]["plan_id"]).limit(1).execute()
        if plan_resp.data:
            raw = plan_resp.data[0]["limits"].get(counter_name, 0)
            limit_val = "unlimited" if raw == -1 else raw

    return {"used": new_used, "limit": limit_val}


def get_usage_today(tenant_id: str) -> list[dict]:
    """Return today's usage counters grouped by service."""
    sb = get_supabase()
    today = date.today().isoformat()

    # Get all tenant subscriptions
    subs = get_tenant_subscriptions(tenant_id)

    result = []
    for sub in subs:
        svc_resp = sb.table("platform_services").select("id").eq("slug", sub["service_slug"]).limit(1).execute()
        if not svc_resp.data:
            continue
        service_id = svc_resp.data[0]["id"]

        # Get all counters for this service today
        counters_resp = (
            sb.table("usage_counters")
            .select("counter_name,used")
            .eq("tenant_id", tenant_id)
            .eq("service_id", service_id)
            .eq("date", today)
            .execute()
        )

        limits = sub["limits"]
        counters = {}
        # Include all limit keys, even if no usage yet
        for key, max_val in limits.items():
            used = 0
            for c in counters_resp.data:
                if c["counter_name"] == key:
                    used = c["used"]
                    break
            counters[key] = {
                "used": used,
                "limit": "unlimited" if max_val == -1 else max_val,
            }

        result.append({
            "service_slug": sub["service_slug"],
            "counters": counters,
        })

    return result


def get_tenant_billing_summary(tenant_id: str) -> dict:
    """Return full billing summary: subscriptions, seats, total monthly cost."""
    subscriptions = get_tenant_subscriptions(tenant_id)
    seat_info = get_tenant_seat_info(tenant_id)

    total = sum(s["price_monthly"] for s in subscriptions)
    if seat_info["package"]:
        total += float(seat_info["package"].get("price_monthly", 0))

    return {
        "subscriptions": subscriptions,
        "seat_package": seat_info["package"],
        "seats_used": seat_info["seats_used"],
        "seats_total": seat_info["seats_total"],
        "total_monthly": total,
    }
