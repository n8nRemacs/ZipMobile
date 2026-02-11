from fastapi import APIRouter
from src.models.common import HealthResponse, ReadyResponse
from src.storage.supabase import get_supabase

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready():
    try:
        sb = get_supabase()
        sb.table("tenant_users").select("id").limit(1).execute()
        return ReadyResponse(status="ready", supabase=True)
    except Exception as e:
        return ReadyResponse(status="degraded", supabase=False, detail=str(e))
