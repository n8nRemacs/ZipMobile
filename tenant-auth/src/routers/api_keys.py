from fastapi import APIRouter, HTTPException, Request, Depends

from src.dependencies import get_current_user, require_role, require_email_verified
from src.models.api_key import ApiKeyCreate, ApiKeyUpdate, ApiKeyResponse, ApiKeyCreatedResponse
from src.services import api_key_service

router = APIRouter(prefix="/auth/v1/api-keys", tags=["API Keys"])


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(request: Request):
    user = require_role("owner", "admin")(request)
    keys = api_key_service.list_api_keys(user["tenant_id"])
    return [ApiKeyResponse(**k) for k in keys]


@router.post("", response_model=ApiKeyCreatedResponse)
async def create_key(body: ApiKeyCreate, request: Request):
    user = require_role("owner", "admin")(request)
    require_email_verified(request)

    # Проверить лимит тарифа
    from src.services import billing_service
    usage = billing_service.get_usage(user["tenant_id"])
    if usage["api_keys_used"] >= usage["api_keys_limit"]:
        raise HTTPException(status_code=403, detail=f"API key limit reached ({usage['api_keys_limit']}). Upgrade your plan.")

    try:
        result = api_key_service.create_api_key(user["tenant_id"], body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ApiKeyCreatedResponse(**result)


@router.patch("/{key_id}", response_model=ApiKeyResponse)
async def update_key(key_id: str, body: ApiKeyUpdate, request: Request):
    user = require_role("owner", "admin")(request)
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    result = api_key_service.update_api_key(key_id, user["tenant_id"], update_data)
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyResponse(**result)


@router.delete("/{key_id}")
async def delete_key(key_id: str, request: Request):
    user = require_role("owner", "admin")(request)
    deleted = api_key_service.delete_api_key(key_id, user["tenant_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"message": "API key revoked"}


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_key(key_id: str, request: Request):
    user = require_role("owner", "admin")(request)
    require_email_verified(request)

    result = api_key_service.rotate_api_key(key_id, user["tenant_id"])
    if not result:
        raise HTTPException(status_code=404, detail="API key not found")

    return ApiKeyCreatedResponse(**result)
