"""
Comprehensive tests verifying all functions and endpoints across ComixAPI client and FastAPI server.
"""

import os
from unittest.mock import MagicMock, patch
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.server import app
from src.api.client import ComixAPI
from src.cookies import find_default_cookies
from src.downloader.core import ComixDownloader


client = TestClient(app)


# -------------------------------------------------------------
# 1. Client & Mixin Edge Cases
# -------------------------------------------------------------
def test_parse_comic_url_with_title_prefix():
    """Verify parse_comic_url handles 'title/slug' without duplicating title/ in URL."""
    api = ComixAPI("title/emqg8-solo-leveling")
    parsed_url = api.parse_comic_url()
    assert parsed_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.manga_hid == "emqg8"
    assert api.manga_slug == "emqg8-solo-leveling"


def test_client_close_safe():
    """Verify close safely terminates bridge and sets to None."""
    api = ComixAPI("")
    mock_bridge = MagicMock()
    api.bridge = mock_bridge
    api.close()
    assert mock_bridge.close.called
    assert api.bridge is None


def test_fetch_all_chapters_auto_bootstrap_and_wrapped_result():
    """Verify fetch_all_chapters auto-bootstraps, errors without manga_hid, and parses wrapped result."""
    # 1. Error without manga_hid
    api_empty = ComixAPI("")
    api_empty.bootstrap = MagicMock()
    with pytest.raises(ValueError, match="Manga HID or URL must be set"):
        api_empty.fetch_all_chapters()

    # 2. Wrapped result and auto-bootstrap
    api = ComixAPI("emqg8-solo-leveling")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": {
            "items": [{"id": 1, "number": 1}],
            "meta": {"has_next": False, "last_page": 1}
        }
    }
    api._http_get = MagicMock(return_value={})

    chapters = api.fetch_all_chapters()
    assert len(chapters) == 1
    assert chapters[0]["number"] == 1


def test_fetch_chapter_pages_auto_bootstrap_and_none_pages():
    """Verify fetch_chapter_pages handles None pages gracefully and auto-bootstraps."""
    api = ComixAPI("emqg8-solo-leveling")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    # Payload where pages is None
    api.bridge.decrypt.return_value = {"pages": None}
    api._http_get = MagicMock(return_value={})

    pages = api.fetch_chapter_pages({"id": "123"})
    assert pages == []


def test_get_chapter_images_nested_result():
    """Verify get_chapter_images handles pages nested in result."""
    api = ComixAPI("emqg8-solo-leveling")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": {
            "pages": {
                "baseUrl": "https://img.comix.to/",
                "items": [{"url": "1.jpg", "w": 100, "h": 200}]
            }
        }
    }
    api._http_get = MagicMock(return_value={})

    data = api.get_chapter_images("999")
    assert data["chapterId"] == "999"
    assert data["total_images"] == 1
    assert data["images"][0]["url"] == "https://img.comix.to/1.jpg"
    assert data["images"][0]["width"] == 100


def test_fetch_chapters_page_auto_bootstrap_and_scan_group():
    """Verify fetch_chapters_page parses scanlation group title and id."""
    api = ComixAPI("emqg8-solo-leveling")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": {
            "items": [
                {
                    "id": 10,
                    "number": 1,
                    "scanlationGroup": {"id": 5, "title": "Asura"}
                }
            ],
            "meta": {"currentPage": 1, "lastPage": 1, "totalCount": 1}
        }
    }
    api._http_get = MagicMock(return_value={})

    res = api.fetch_chapters_page(page=1, limit=30)
    assert len(res["chapters"]) == 1
    assert res["chapters"][0]["scanlation_group"]["name"] == "Asura"
    assert res["pagination"]["total"] == 1


def test_user_following_unrecognized_folder_returns_empty():
    """Verify get_following_titles returns empty list when unrecognized folder is requested."""
    api = ComixAPI("", cookie_header="auth=123")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"token": "sig"}
    api.bridge.decrypt.return_value = {
        "items": [
            {"id": 1, "bookmarkPivot": {"folderId": 1}}
        ],
        "meta": {"hasNext": False, "lastPage": 1}
    }
    api._http_get = MagicMock(return_value={})

    res = api.get_following_titles(folder="invalid_folder_xyz")
    assert res == []


def test_collections_snake_case_pagination():
    """Verify get_collection_items terminates properly with snake_case last_page."""
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": {
            "items": [{"manga": {"id": 1, "title": "Comic 1"}}],
            "meta": {"has_next": False, "last_page": 1}
        }
    }
    api._http_get = MagicMock(return_value={})

    items = api.get_collection_items("100")
    assert len(items) == 1
    assert items[0]["title"] == "Comic 1"


def test_find_default_cookies_env_var(tmp_path, monkeypatch):
    """Verify find_default_cookies respects COOKIE_FILE environment variable."""
    fake_cookie_file = tmp_path / "custom_cookies.txt"
    fake_cookie_file.write_text("test_cookie=1", encoding="utf-8")

    monkeypatch.setenv("COOKIE_FILE", str(fake_cookie_file))
    found = find_default_cookies()
    assert found == str(fake_cookie_file.resolve())


# -------------------------------------------------------------
# 2. Server Endpoints & Aliases
# -------------------------------------------------------------
def test_server_chapter_pages_endpoint():
    """Verify /api/chapter/{chapter_id}/pages endpoint."""
    mock_data = {
        "chapterId": "42",
        "total_images": 1,
        "images": [{"url": "https://img.comix.to/page1.jpg"}]
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "get_chapter_images", return_value=mock_data):
        resp = client.get("/api/chapter/42/pages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapterId"] == "42"
        assert data["images"][0]["url"].startswith("/api/image?url=")


def test_server_collection_alias_endpoint():
    """Verify /api/collection/{id} alias endpoint."""
    mock_items = [{"title": "Series in Collection"}]
    with patch.object(ComixAPI, "get_collection_items", return_value=mock_items):
        resp = client.get("/api/collection/99")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1


def test_server_title_aliases():
    """Verify /api/title/{slug_or_id}, chapters, and groups aliases."""
    mock_meta = {
        "hid": "sl1",
        "slug": "solo-leveling",
        "title": "Solo Leveling",
        "authors": [{"title": "Chugong"}],
        "artists": [{"title": "DUBU"}],
        "genres": [{"title": "Action"}],
        "demographic": {"title": "Shounen"}
    }
    mock_groups = [{"id": 1, "name": "Reaper"}]

    def mock_bootstrap(self):
        self.metadata = mock_meta
        self.manga_title = "Solo Leveling"
        self.manga_slug = "sl1-solo-leveling"
        self.manga_hid = "sl1"

    with patch.object(ComixAPI, "bootstrap", side_effect=mock_bootstrap, autospec=True), \
         patch.object(ComixAPI, "get_manga_groups", return_value=mock_groups):
        # 1. /api/title/{id}
        resp1 = client.get("/api/title/sl1-solo-leveling")
        assert resp1.status_code == 200
        assert resp1.json()["comic"]["authors"] == "Chugong"

        # 2. /api/title/{id}/groups
        resp2 = client.get("/api/title/sl1-solo-leveling/groups")
        assert resp2.status_code == 200
        assert resp2.json()["groups"][0]["name"] == "Reaper"

    # 3. /api/title/{id}/chapters
    mock_ch_page = {
        "chapters": [{"id": "c1", "number": 1}],
        "pagination": {"current_page": 1, "last_page": 1, "total": 1, "limit": 30}
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_chapters_page", return_value=mock_ch_page):
        resp3 = client.get("/api/title/sl1-solo-leveling/chapters")
        assert resp3.status_code == 200
        assert resp3.json()["chapters"][0]["number"] == 1


def test_server_following_and_history_aliases():
    """Verify /api/following and /api/history aliases."""
    with patch("src.server.find_default_cookies", return_value="dummy_cookies.txt"), \
         patch("src.server.parse_cookie_file", return_value="auth=1"), \
         patch.object(ComixAPI, "get_following_titles", return_value=[{"title": "Bookmarked Title"}]), \
         patch.object(ComixAPI, "get_user_history", return_value=[{"title": "History Title"}]):
        resp1 = client.get("/api/following")
        assert resp1.status_code == 200
        assert resp1.json()["items"][0]["title"] == "Bookmarked Title"

        resp2 = client.get("/api/history")
        assert resp2.status_code == 200
        assert resp2.json()["items"][0]["title"] == "History Title"


def test_server_export_media_types():
    """Verify export endpoints return appropriate content-type headers."""
    with patch("src.server.find_default_cookies", return_value="dummy_cookies.txt"), \
         patch("src.server.parse_cookie_file", return_value="auth=1"), \
         patch.object(ComixAPI, "export_user_bookmarks", return_value="Title,Chapter\nSolo,100"):
        resp = client.get("/api/user/export?format=csv")
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]


def test_server_flexible_search_and_trending_params():
    """Verify /api/search and /api/trending accept singular/alias parameters."""
    with patch.object(ComixAPI, "search_titles", return_value=[{"title": "Search Result"}]):
        resp = client.get("/api/search?q=Solo&genre=Action&demographic=shounen")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    with patch.object(ComixAPI, "get_top_titles", return_value=[{"title": "Trending Result"}]) as mock_top:
        resp = client.get("/api/trending?type=follows")
        assert resp.status_code == 200
        assert resp.json()["trend_type"] == "follows"
        assert mock_top.call_args[1]["type_filter"] == "follows"


def test_server_download_series_endpoint(tmp_path):
    """Verify /api/download/series endpoint."""
    fake_file = tmp_path / "Solo Leveling - Ch 001.cbz"
    fake_file.write_text("cbz-content", encoding="utf-8")

    mock_chapters = [{"id": "c1", "number": 1, "name": "Chapter 1"}]

    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_all_chapters", return_value=mock_chapters), \
         patch.object(ComixDownloader, "download_chapter", return_value=fake_file):
        payload = {
            "manga": "emqg8-solo-leveling",
            "chapter_range": "1",
            "format": "cbz",
            "merge": False
        }
        resp = client.post("/api/download/series", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["total_downloaded"] == 1
        assert "Solo Leveling - Ch 001.cbz" in data["files"]
