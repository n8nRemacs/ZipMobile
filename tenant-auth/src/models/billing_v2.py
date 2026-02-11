from pydantic import BaseModel


class ServicePlanResponse(BaseModel):
    id: str
    slug: str
    name: str
    price_monthly: float
    limits: dict
    features: dict


class PlatformServiceResponse(BaseModel):
    id: str
    slug: str
    name: str
    description: str | None
    icon: str | None
    plans: list[ServicePlanResponse]


class SeatPackageResponse(BaseModel):
    id: str
    slug: str
    name: str
    max_seats: int
    price_monthly: float
    price_per_seat: float | None


class TenantSubscriptionResponse(BaseModel):
    service_slug: str
    service_name: str
    plan_slug: str
    plan_name: str
    price_monthly: float
    limits: dict
    status: str


class TenantBillingSummary(BaseModel):
    subscriptions: list[TenantSubscriptionResponse]
    seat_package: SeatPackageResponse | None
    seats_used: int
    seats_total: int
    total_monthly: float


class UsageCounterInfo(BaseModel):
    used: int
    limit: int | str  # int or "unlimited"


class UsageResponse(BaseModel):
    service_slug: str
    counters: dict[str, UsageCounterInfo]


class CheckLimitRequest(BaseModel):
    service: str
    counter: str


class CheckLimitResponse(BaseModel):
    allowed: bool
    used: int
    limit: int | str  # int or "unlimited"
