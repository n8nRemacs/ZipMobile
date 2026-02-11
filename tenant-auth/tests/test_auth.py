import pytest
from unittest.mock import patch, MagicMock, call
from fastapi.testclient import TestClient


def _make_client(mock_sb):
    """Helper to create TestClient with mocked supabase."""
    with patch("src.storage.supabase.get_supabase", return_value=mock_sb):
        with patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb):
            with patch("src.services.otp_service.get_supabase", return_value=mock_sb):
                with patch("src.services.user_service.get_supabase", return_value=mock_sb):
                    with patch("src.services.jwt_service.get_supabase", return_value=mock_sb):
                        from src.main import app
                        yield TestClient(app)


def _mock_supabase():
    """Create a chainable mock supabase client."""
    mock = MagicMock()
    mock_query = MagicMock()
    mock_result = MagicMock()
    mock_result.data = []
    mock_result.count = 0

    mock_query.select.return_value = mock_query
    mock_query.insert.return_value = mock_query
    mock_query.update.return_value = mock_query
    mock_query.delete.return_value = mock_query
    mock_query.eq.return_value = mock_query
    mock_query.neq.return_value = mock_query
    mock_query.gte.return_value = mock_query
    mock_query.order.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = mock_result

    mock.table.return_value = mock_query
    return mock, mock_query, mock_result


def test_register_sends_otp():
    """Test that registration creates tenant+user and sends OTP."""
    mock_sb, mock_query, mock_result = _mock_supabase()

    # Set up responses for the chain of calls
    call_count = {"n": 0}
    original_execute = mock_query.execute

    def side_effect_execute():
        call_count["n"] += 1
        result = MagicMock()
        # Call 1: check existing user by phone -> not found
        if call_count["n"] == 1:
            result.data = []
        # Call 2: get free billing plan
        elif call_count["n"] == 2:
            result.data = [{"id": "plan-free-id"}]
        # Call 3: create tenant
        elif call_count["n"] == 3:
            result.data = [{"id": "tenant-123", "name": "Test"}]
        # Call 4: create user
        elif call_count["n"] == 4:
            result.data = [{"id": "user-123", "tenant_id": "tenant-123", "phone": "+79991234567", "role": "owner"}]
        # Call 5+: OTP-related (rate limit check, invalidate old, insert new)
        else:
            result.data = []
        result.count = len(result.data)
        return result

    mock_query.execute.side_effect = side_effect_execute

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.otp_service.get_supabase", return_value=mock_sb), \
         patch("src.services.user_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.post("/auth/v1/register", json={
            "phone": "+79991234567",
            "email": "test@example.com",
            "name": "Test User",
            "otp_channel": "console",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "OTP sent for registration"
        assert "channel" in data
        assert "expires_in" in data


def test_register_duplicate_phone():
    """Test that registering with existing phone returns 409."""
    mock_sb, mock_query, mock_result = _mock_supabase()

    # First call: user lookup returns existing user
    mock_result.data = [{"id": "existing-user", "phone": "+79991234567"}]

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.user_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.post("/auth/v1/register", json={
            "phone": "+79991234567",
            "email": "test@example.com",
            "name": "Test User",
        })

        assert resp.status_code == 409


def test_login_unknown_phone():
    """Test that login with unknown phone returns 404."""
    mock_sb, mock_query, mock_result = _mock_supabase()
    mock_result.data = []

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.user_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.post("/auth/v1/login", json={
            "phone": "+79990000000",
        })

        assert resp.status_code == 404


def test_verify_otp_invalid_code():
    """Test that wrong OTP code returns 400."""
    mock_sb, mock_query, mock_result = _mock_supabase()

    # Return a verification code that doesn't match
    mock_result.data = [{
        "id": "vc-1",
        "target": "+79991234567",
        "code": "123456",
        "purpose": "login",
        "attempts": 0,
        "max_attempts": 5,
        "is_used": False,
        "expires_at": "2099-01-01T00:00:00+00:00",
    }]

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.otp_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.post("/auth/v1/verify-otp", json={
            "phone": "+79991234567",
            "code": "000000",
            "purpose": "login",
        })

        assert resp.status_code == 400
        assert "Invalid code" in resp.json()["detail"]


def test_refresh_invalid_token():
    """Test that invalid refresh token returns 401."""
    mock_sb, mock_query, mock_result = _mock_supabase()
    mock_result.data = []

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.jwt_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.post("/auth/v1/refresh", json={
            "refresh_token": "invalid-token",
        })

        assert resp.status_code == 401


def test_protected_endpoint_requires_jwt():
    """Test that protected endpoints require JWT."""
    mock_sb, mock_query, mock_result = _mock_supabase()
    mock_result.data = []

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.get("/auth/v1/profile")
        assert resp.status_code == 401


def test_billing_plans_is_public():
    """Test that billing plans endpoint is publicly accessible."""
    mock_sb, mock_query, mock_result = _mock_supabase()
    mock_result.data = [
        {"id": "p1", "name": "free", "price_monthly": "0", "max_api_keys": 1,
         "max_sessions": 1, "max_sub_users": 1, "features": {}, "is_active": True},
    ]

    with patch("src.storage.supabase.get_supabase", return_value=mock_sb), \
         patch("src.middleware.jwt_auth.get_supabase", return_value=mock_sb), \
         patch("src.services.billing_service.get_supabase", return_value=mock_sb):
        from src.main import app
        client = TestClient(app)

        resp = client.get("/auth/v1/billing/plans")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "free"
