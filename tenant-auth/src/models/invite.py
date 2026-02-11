from pydantic import BaseModel, Field


class InviteCreate(BaseModel):
    phone: str | None = Field(None, pattern=r"^\+\d{10,15}$")
    email: str | None = None
    role: str = Field(default="viewer", pattern=r"^(admin|manager|viewer)$")


class InviteResponse(BaseModel):
    id: str
    tenant_id: str
    invited_by: str
    phone: str | None = None
    email: str | None = None
    role: str
    status: str
    expires_at: str | None = None
    created_at: str | None = None


class InviteAcceptRequest(BaseModel):
    phone: str = Field(..., pattern=r"^\+\d{10,15}$")
    name: str = Field(..., min_length=1, max_length=200)


class TeamMemberResponse(BaseModel):
    id: str
    tenant_id: str
    phone: str
    email: str | None = None
    name: str | None = None
    role: str
    is_active: bool
    created_at: str | None = None


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|manager|viewer)$")
