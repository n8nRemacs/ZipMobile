from pydantic import BaseModel
from typing import Any


class PlanInfo(BaseModel):
    id: str
    name: str
    price_monthly: float
    max_api_keys: int
    max_sessions: int
    max_sub_users: int
    features: dict[str, Any] = {}


class CurrentPlanResponse(BaseModel):
    plan: PlanInfo
    usage: "UsageStats"


class UsageStats(BaseModel):
    api_keys_used: int = 0
    api_keys_limit: int = 1
    sessions_used: int = 0
    sessions_limit: int = 1
    sub_users_used: int = 0
    sub_users_limit: int = 1


class UpgradeRequest(BaseModel):
    plan_id: str
