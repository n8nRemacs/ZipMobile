import pytest
from unittest.mock import patch, MagicMock

# Override settings before importing jwt_service
with patch("src.config.settings") as mock_settings:
    mock_settings.jwt_secret = "test-secret-key-for-unit-tests-32c"
    mock_settings.jwt_algorithm = "HS256"
    mock_settings.jwt_access_token_expire_minutes = 30
    mock_settings.jwt_refresh_token_expire_days = 30


def test_create_and_verify_access_token():
    """Test creating and verifying an access token."""
    from src.services.jwt_service import create_access_token, verify_access_token

    with patch("src.services.jwt_service.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key-for-unit-tests-32c"
        mock_settings.jwt_algorithm = "HS256"
        mock_settings.jwt_access_token_expire_minutes = 30

        token, expires_in = create_access_token("user-123", "tenant-456", "owner")
        assert isinstance(token, str)
        assert expires_in == 1800  # 30 min

        payload = verify_access_token(token)
        assert payload["sub"] == "user-123"
        assert payload["tenant_id"] == "tenant-456"
        assert payload["role"] == "owner"
        assert payload["type"] == "access"


def test_verify_invalid_token():
    """Test that invalid tokens raise ValueError."""
    from src.services.jwt_service import verify_access_token

    with patch("src.services.jwt_service.settings") as mock_settings:
        mock_settings.jwt_secret = "test-secret-key-for-unit-tests-32c"
        mock_settings.jwt_algorithm = "HS256"

        with pytest.raises(ValueError, match="Invalid token"):
            verify_access_token("not-a-valid-jwt-token")


def test_create_refresh_token():
    """Test creating a refresh token stores it in DB."""
    from src.services.jwt_service import create_refresh_token

    mock_sb = MagicMock()
    mock_query = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{"id": "rt-1"}]
    mock_query.insert.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_sb.table.return_value = mock_query

    with patch("src.services.jwt_service.get_supabase", return_value=mock_sb), \
         patch("src.services.jwt_service.settings") as mock_settings:
        mock_settings.jwt_refresh_token_expire_days = 30

        raw_token = create_refresh_token("user-123")
        assert isinstance(raw_token, str)
        assert len(raw_token) > 20

        # Verify insert was called
        mock_sb.table.assert_called_with("refresh_tokens")
        mock_query.insert.assert_called_once()
