import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


@pytest.fixture
def mock_supabase():
    """Mock Supabase client for testing without real DB."""
    mock_client = MagicMock()
    mock_query = MagicMock()

    # Default: return empty results
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

    mock_client.table.return_value = mock_query

    return mock_client, mock_query, mock_result


@pytest.fixture
def client(mock_supabase):
    """Create test client with mocked Supabase."""
    mock_client, _, _ = mock_supabase

    with patch("src.storage.supabase.get_supabase", return_value=mock_client):
        with patch("src.middleware.jwt_auth.get_supabase", return_value=mock_client):
            from src.main import app
            yield TestClient(app)
