"""
Unit and integration tests for FastAPI Web Server and Swagger UI endpoints.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from src.server import app, create_app
from src.api.client import ComixAPI


client = TestClient(app)


def test_swagger_ui_served():
    """Verify that Swagger UI is accessible at /docs."""
    resp = client.get("/docs")
    assert resp.status_code == 200
    assert "swagger-ui" in resp.text.lower() or "swaggerui" in resp.text.lower()


def test_redoc_ui_served():
    """Verify that ReDoc UI is accessible at /redoc."""
    resp = client.get("/redoc")
    assert resp.status_code == 200
    assert "redoc" in resp.text.lower()


def test_root_redirects_to_swagger():
    """Verify that / redirects to /docs with status 307."""
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (301, 302, 307, 308)
    assert resp.headers["location"] == "/docs"


def test_openapi_schema_generated():
    """Verify that OpenAPI schema defines all expected endpoints and tags."""
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "ComixAPI"

    paths = schema["paths"]
    assert "/api/health" in paths
    assert "/api/search" in paths
    assert "/api/trending" in paths
    assert "/api/manga/{slug_or_id}" in paths
    assert "/api/manga/{slug_or_id}/chapters" in paths
    assert "/api/manga/{slug_or_id}/groups" in paths
    assert "/api/collections/{collection_id}" in paths
    assert "/api/user/following" in paths
    assert "/api/user/history" in paths
    assert "/api/user/export" in paths
    assert "/api/download/chapter" in paths


def test_api_health():
    """Verify health check endpoint returns 200."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["swagger_ui"] == "/docs"


def test_api_search():
    """Verify search endpoint integrates with ComixAPI.search_titles."""
    mock_results = [{"title": "Solo Leveling", "hid": "sl1"}]
    with patch.object(ComixAPI, "search_titles", return_value=mock_results):
        resp = client.get("/api/search?q=Solo")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Solo Leveling"


def test_api_trending():
    """Verify trending endpoint integrates with ComixAPI.get_top_titles."""
    mock_results = [{"title": "Return of the Blossoming Blade", "hid": "hua1"}]
    with patch.object(ComixAPI, "get_top_titles", return_value=mock_results):
        resp = client.get("/api/trending?trend_type=trending&days=7")
        assert resp.status_code == 200
        data = resp.json()
        assert data["days"] == 7
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Return of the Blossoming Blade"


def test_api_collection():
    """Verify collections endpoint integrates with ComixAPI.get_collection_items."""
    mock_items = [{"title": "Dungeon Comic 1"}]
    with patch.object(ComixAPI, "get_collection_items", return_value=mock_items):
        resp = client.get("/api/collections/top-10-dungeons")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["items"][0]["title"] == "Dungeon Comic 1"


def test_api_cookies_status():
    """Verify cookies status endpoint returns diagnostic object."""
    resp = client.get("/api/cookies/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "has_cookie_configured" in data
    assert "cloudflare_bypassed" in data
    assert "status_code" in data
