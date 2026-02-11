from fastapi import APIRouter, HTTPException, Request

from src.dependencies import get_current_user, require_role, require_email_verified
from src.models.invite import InviteCreate, InviteResponse, InviteAcceptRequest, TeamMemberResponse, RoleUpdateRequest
from src.services import invite_service, user_service

router = APIRouter(prefix="/auth/v1/team", tags=["Team"])


@router.get("", response_model=list[TeamMemberResponse])
async def list_team(request: Request):
    user = get_current_user(request)
    members = user_service.get_team_members(user["tenant_id"])
    return [TeamMemberResponse(**m) for m in members]


@router.post("/invite", response_model=InviteResponse)
async def create_invite(body: InviteCreate, request: Request):
    user = require_role("owner", "admin")(request)
    require_email_verified(request)

    # Проверить лимит тарифа
    from src.services import billing_service
    usage = billing_service.get_usage(user["tenant_id"])
    if usage["sub_users_used"] >= usage["sub_users_limit"]:
        raise HTTPException(status_code=403, detail=f"Team member limit reached ({usage['sub_users_limit']}). Upgrade your plan.")

    try:
        result = invite_service.create_invite(
            tenant_id=user["tenant_id"],
            invited_by=user["id"],
            phone=body.phone,
            email=body.email,
            role=body.role,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return InviteResponse(
        id=result["id"],
        tenant_id=result["tenant_id"],
        invited_by=result["invited_by"],
        phone=result.get("phone"),
        email=result.get("email"),
        role=result["role"],
        status=result["status"],
        expires_at=result.get("expires_at"),
        created_at=result.get("created_at"),
    )


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(request: Request):
    user = require_role("owner", "admin")(request)
    invites = invite_service.list_invites(user["tenant_id"])
    return [InviteResponse(**i) for i in invites]


@router.delete("/invites/{invite_id}")
async def cancel_invite(invite_id: str, request: Request):
    user = require_role("owner", "admin")(request)
    cancelled = invite_service.cancel_invite(invite_id, user["tenant_id"])
    if not cancelled:
        raise HTTPException(status_code=404, detail="Invite not found or already processed")
    return {"message": "Invite cancelled"}


@router.post("/invites/{token}/accept")
async def accept_invite(token: str, body: InviteAcceptRequest):
    """Accept an invite (public endpoint — no JWT required)."""
    try:
        user = invite_service.accept_invite(token, body.phone, body.name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "Invite accepted", "user_id": user["id"], "tenant_id": user["tenant_id"]}


@router.patch("/{user_id}/role")
async def update_role(user_id: str, body: RoleUpdateRequest, request: Request):
    user = require_role("owner", "admin")(request)
    try:
        updated = user_service.update_role(user_id, user["tenant_id"], body.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail="User not found in your team")

    return {"message": "Role updated", "role": body.role}


@router.delete("/{user_id}")
async def remove_member(user_id: str, request: Request):
    user = require_role("owner", "admin")(request)
    try:
        removed = user_service.remove_team_member(user_id, user["tenant_id"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not removed:
        raise HTTPException(status_code=404, detail="User not found in your team")

    return {"message": "Team member removed"}
