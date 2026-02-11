from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str | None = None
    is_active: bool = True
    last_used_at: str | None = None
    created_at: str | None = None


class ApiKeyCreatedResponse(ApiKeyResponse):
    """Returned only on creation — plaintext key is shown once."""
    plaintext_key: str
