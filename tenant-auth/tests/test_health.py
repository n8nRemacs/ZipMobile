from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def test_health_returns_ok():
    mock_client = MagicMock()
    with patch("src.storage.supabase.get_supabase", return_value=mock_client):
        with patch("src.middleware.jwt_auth.get_supabase", return_value=mock_client):
            from src.main import app
            client = TestClient(app)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"
            assert "version" in data


def test_ready_with_supabase():
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_result = MagicMock()
    mock_result.data = [{"id": "test"}]
    mock_query.select.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.execute.return_value = mock_result
    mock_client.table.return_value = mock_query

    with patch("src.storage.supabase.get_supabase", return_value=mock_client):
        with patch("src.middleware.jwt_auth.get_supabase", return_value=mock_client):
            with patch("src.routers.health.get_supabase", return_value=mock_client):
                from src.main import app
                client = TestClient(app)
                resp = client.get("/ready")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ready"
                assert data["supabase"] is True
