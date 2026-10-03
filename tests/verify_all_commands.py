"""
Automated verification script to check every ComixAPI command / endpoint one by one.
Validates HTTP status codes, output formats, schemas, headers, and parameter handling.
"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure src can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.server import app
from src.api.client import ComixAPI
from src.downloader.core import ComixDownloader


client = TestClient(app)

results_summary = []


def record_result(cmd_name: str, endpoint: str, status_code: int, passed: bool, details: str):
    results_summary.append({
        "command": cmd_name,
        "endpoint": endpoint,
        "status_code": status_code,
        "passed": passed,
        "details": details
    })
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status_icon} | {cmd_name:<30} | {endpoint:<40} | HTTP {status_code} | {details}")


def verify_all():
    print("\n" + "=" * 95)
    print("🔍 VERIFYING ALL COMIXAPI COMMANDS & ENDPOINTS ONE BY ONE")
    print("=" * 95 + "\n")

    # 1. GET / (Root redirect)
    resp = client.get("/", follow_redirects=False)
    passed = resp.status_code in (301, 302, 307, 308) and resp.headers.get("location") == "/docs"
    record_result("Root Redirect", "GET /", resp.status_code, passed, f"Redirects to {resp.headers.get('location')}")

    # 2. GET /docs (Swagger UI)
    resp = client.get("/docs")
    passed = resp.status_code == 200 and "swagger-ui" in resp.text.lower()
    record_result("Swagger UI", "GET /docs", resp.status_code, passed, "Interactive Swagger UI served")

    # 3. GET /redoc (ReDoc UI)
    resp = client.get("/redoc")
    passed = resp.status_code == 200 and "redoc" in resp.text.lower()
    record_result("ReDoc UI", "GET /redoc", resp.status_code, passed, "Interactive ReDoc UI served")

    # 4. GET /openapi.json (OpenAPI Schema)
    resp = client.get("/openapi.json")
    data = resp.json() if resp.status_code == 200 else {}
    passed = resp.status_code == 200 and data.get("info", {}).get("title") == "ComixAPI" and len(data.get("paths", {})) >= 15
    record_result("OpenAPI Spec", "GET /openapi.json", resp.status_code, passed, f"Generated schema with {len(data.get('paths', {}))} endpoints")

    # 5. GET /api/health
    resp = client.get("/api/health")
    data = resp.json() if resp.status_code == 200 else {}
    passed = resp.status_code == 200 and data.get("status") == "healthy" and "aria2_accelerator" in data
    record_result("System Health", "GET /api/health", resp.status_code, passed, f"Status: {data.get('status')}, Version: {data.get('version')}")

    # 6. GET /api/image (Image Proxy)
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None
    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = client.get("/api/image?url=https://static.comix.to/sample.jpg")
        passed = (
            resp.status_code == 200 and
            resp.headers.get("access-control-allow-origin") == "*" and
            resp.headers.get("cross-origin-resource-policy") == "cross-origin" and
            resp.content == b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
        )
        record_result("Image Proxy", "GET /api/image?url=...", resp.status_code, passed, "CORS & CORP headers present, image bytes delivered")

    # 7. GET /api/search
    mock_search = [{"title": "Solo Leveling", "hid": "sl1"}]
    with patch.object(ComixAPI, "search_titles", return_value=mock_search):
        resp = client.get("/api/search?q=Solo&type=manhwa&genre=Action")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("count") == 1 and data.get("items")[0]["title"] == "Solo Leveling"
        record_result("Legacy Search", "GET /api/search?q=...", resp.status_code, passed, f"Returned {data.get('count')} item(s)")

    # 8. GET /api/trending
    mock_trending = [{"title": "Top Manhwa 1", "hid": "top1"}]
    with patch.object(ComixAPI, "get_top_titles", return_value=mock_trending):
        resp = client.get("/api/trending?type=trending&days=7")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("trend_type") == "trending" and data.get("days") == 7 and data.get("count") == 1
        record_result("Trending Titles", "GET /api/trending?type=...&days=...", resp.status_code, passed, f"Trend: {data.get('trend_type')}, Days: {data.get('days')}")

    # 9. GET /api/manga/home
    mock_pop = [{"hid": "p1", "slug": "pop-manga", "title": "Popular Manga", "latest_chapter": {"number": 10}, "genres": [{"name": "Action"}]}]
    mock_lat = [{"hid": "l1", "slug": "latest-manga", "title": "Latest Manga", "latest_chapter": {"number": 50}, "genres": [{"name": "Fantasy"}]}]
    with patch.object(ComixAPI, "get_top_titles", return_value=mock_pop), \
         patch.object(ComixAPI, "search_titles", return_value=mock_lat):
        resp = client.get("/api/manga/home?sfw=true")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and "popular" in data and "latest" in data and len(data["popular"]) == 1
        record_result("Manga Home Feed", "GET /api/manga/home?sfw=true", resp.status_code, passed, f"Popular: {len(data.get('popular', []))}, Latest: {len(data.get('latest', []))}")

    # 10. GET /api/manga/browse
    mock_browse = [{"hid": "b1", "slug": "browse-manga", "title": "Browse Manga", "score": 8.5, "status": 1}]
    with patch.object(ComixAPI, "search_titles", return_value=(mock_browse, {"page": 1, "lastPage": 5})):
        resp = client.get("/api/manga/browse?sort=popular&type=manhwa")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and len(data.get("results", [])) == 1 and data.get("pagination", {}).get("last_page") == 5
        record_result("Browse Manga", "GET /api/manga/browse?sort=...", resp.status_code, passed, f"Results: {len(data.get('results', []))}, Pages: {data.get('pagination', {}).get('last_page')}")

    # 11. GET /api/manga/filter
    mock_filtered = [{"hid": "f1", "title": "Filtered Manga"}]
    with patch.object(ComixAPI, "search_titles", return_value=(mock_filtered, {"page": 1, "lastPage": 2})):
        resp = client.get("/api/manga/filter?genres=action,fantasy&status=releasing")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and len(data.get("results", [])) == 1
        record_result("Filter Manga", "GET /api/manga/filter?genres=...", resp.status_code, passed, f"Results: {len(data.get('results', []))}")

    # 12. GET /api/manga/search (Advanced)
    mock_adv = [{"hid": "adv1", "title": "Advanced Result", "score": 9.0}]
    with patch.object(ComixAPI, "search_titles", return_value=(mock_adv, {"page": 1, "lastPage": 10})):
        resp = client.get("/api/manga/search?q=hero&sort=rating")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and len(data.get("results", [])) == 1
        record_result("Advanced Search", "GET /api/manga/search?q=...&sort=...", resp.status_code, passed, f"Results: {len(data.get('results', []))}")

    # 13. GET /api/manga/collections/{id}
    mock_col_meta = {"id": 10, "name": "Best Action", "description": "Top action manhwa"}
    mock_col_items = [{"hid": "m1", "title": "Action Comic 1"}]
    with patch.object(ComixAPI, "get_collection", return_value=mock_col_meta), \
         patch.object(ComixAPI, "get_collection_items", return_value=mock_col_items):
        resp = client.get("/api/manga/collections/10")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("collection", {}).get("name") == "Best Action"
        record_result("Curated Collection", "GET /api/manga/collections/{id}", resp.status_code, passed, f"Collection: '{data.get('collection', {}).get('name')}', Items: {len(data.get('results', []))}")

    # 14. GET /api/collection/{id} (Alias)
    with patch.object(ComixAPI, "get_collection_items", return_value=mock_col_items):
        resp = client.get("/api/collection/10")
        data = resp.json() if resp.status_code == 200 else {}
        passed = resp.status_code == 200 and data.get("count") == 1
        record_result("Collection Alias", "GET /api/collection/{id}", resp.status_code, passed, f"Count: {data.get('count')}")

    # 15. GET /api/manga/{slug_or_id} & /api/title/{slug_or_id}
    mock_manga_meta = {
        "hid": "sl1", "slug": "solo-leveling", "title": "Solo Leveling",
        "authors": [{"name": "Chugong"}], "artists": [{"name": "DUBU"}],
        "genres": [{"name": "Action"}], "desc": "Hunter world."
    }
    def mock_boot(self):
        self.metadata = mock_manga_meta
        self.manga_title = "Solo Leveling"
        self.manga_slug = "sl1-solo-leveling"
        self.manga_hid = "sl1"

    with patch.object(ComixAPI, "bootstrap", side_effect=mock_boot, autospec=True), \
         patch.object(ComixAPI, "get_manga_groups", return_value=[{"id": 1, "name": "Asura"}]):
        resp1 = client.get("/api/manga/sl1-solo-leveling")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and data1.get("comic", {}).get("title") == "Solo Leveling"
        record_result("Manga Details", "GET /api/manga/{id}", resp1.status_code, passed1, f"Title: '{data1.get('comic', {}).get('title')}', Author: '{data1.get('comic', {}).get('authors')}'")

        resp2 = client.get("/api/title/sl1-solo-leveling")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and data2.get("comic", {}).get("title") == "Solo Leveling"
        record_result("Title Details (Alias)", "GET /api/title/{id}", resp2.status_code, passed2, f"Title: '{data2.get('comic', {}).get('title')}'")

    # 16. GET /api/manga/{id}/chapters & /api/title/{id}/chapters
    mock_chapters_resp = {
        "chapters": [{"id": "ch1", "number": 1, "title": "Chapter 1"}],
        "pagination": {"current_page": 1, "last_page": 1, "total": 1, "limit": 30}
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_chapters_page", return_value=mock_chapters_resp):
        resp1 = client.get("/api/manga/sl1-solo-leveling/chapters?page=1&limit=30")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and len(data1.get("chapters", [])) == 1
        record_result("Manga Chapters", "GET /api/manga/{id}/chapters", resp1.status_code, passed1, f"Total chapters: {data1.get('total_available')}")

        resp2 = client.get("/api/title/sl1-solo-leveling/chapters?page=1&limit=30")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and len(data2.get("chapters", [])) == 1
        record_result("Title Chapters (Alias)", "GET /api/title/{id}/chapters", resp2.status_code, passed2, f"Total chapters: {data2.get('total_available')}")

    # 17. GET /api/manga/{id}/groups & /api/title/{id}/groups
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "get_manga_groups", return_value=[{"id": 42, "name": "Reaper Scans"}]):
        resp1 = client.get("/api/manga/sl1/groups")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and data1.get("count") == 1
        record_result("Manga Groups", "GET /api/manga/{id}/groups", resp1.status_code, passed1, f"Groups count: {data1.get('count')}")

        resp2 = client.get("/api/title/sl1/groups")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and data2.get("count") == 1
        record_result("Title Groups (Alias)", "GET /api/title/{id}/groups", resp2.status_code, passed2, f"Groups count: {data2.get('count')}")

    # 18. GET /api/manga/read & /api/chapter/{chapter_id}/pages
    mock_pages = {
        "chapterId": "888", "total_images": 2,
        "images": [{"url": "https://img.comix.to/1.jpg"}, {"url": "https://img.comix.to/2.jpg"}]
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "get_chapter_images", return_value=mock_pages):
        resp1 = client.get("/api/manga/read?chapterId=888")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and data1.get("total_images") == 2 and data1["images"][0]["url"].startswith("/api/image?url=")
        record_result("Read Chapter Images", "GET /api/manga/read?chapterId=...", resp1.status_code, passed1, f"Total images: {data1.get('total_images')}, CORS proxied")

        resp2 = client.get("/api/chapter/888/pages")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and data2.get("total_images") == 2
        record_result("Chapter Pages (REST)", "GET /api/chapter/{id}/pages", resp2.status_code, passed2, f"Total images: {data2.get('total_images')}, CORS proxied")

    # 19. GET /api/user/following & /api/following
    with patch("src.server.find_default_cookies", return_value="cookies.txt"), \
         patch("src.server.parse_cookie_file", return_value="session=xyz"), \
         patch.object(ComixAPI, "get_following_titles", return_value=[{"title": "Bookmarked Series"}]):
        resp1 = client.get("/api/user/following?folder=reading")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and data1.get("count") == 1
        record_result("User Following", "GET /api/user/following?folder=...", resp1.status_code, passed1, f"Count: {data1.get('count')}, Folder: {data1.get('folder')}")

        resp2 = client.get("/api/following?folder=reading")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and data2.get("count") == 1
        record_result("Following (Alias)", "GET /api/following", resp2.status_code, passed2, f"Count: {data2.get('count')}")

    # 20. GET /api/user/history & /api/history
    with patch("src.server.find_default_cookies", return_value="cookies.txt"), \
         patch("src.server.parse_cookie_file", return_value="session=xyz"), \
         patch.object(ComixAPI, "get_user_history", return_value=[{"title": "History Series"}]):
        resp1 = client.get("/api/user/history?page=1&limit=20")
        data1 = resp1.json() if resp1.status_code == 200 else {}
        passed1 = resp1.status_code == 200 and data1.get("count") == 1
        record_result("User History", "GET /api/user/history?page=...", resp1.status_code, passed1, f"Count: {data1.get('count')}, Page: {data1.get('page')}")

        resp2 = client.get("/api/history")
        data2 = resp2.json() if resp2.status_code == 200 else {}
        passed2 = resp2.status_code == 200 and data2.get("count") == 1
        record_result("History (Alias)", "GET /api/history", resp2.status_code, passed2, f"Count: {data2.get('count')}")

    # 21. GET /api/user/export (MAL, CSV, JSON)
    with patch("src.server.find_default_cookies", return_value="cookies.txt"), \
         patch("src.server.parse_cookie_file", return_value="session=xyz"):
        with patch.object(ComixAPI, "export_user_bookmarks", return_value="<myanimelist></myanimelist>"):
            resp_mal = client.get("/api/user/export?format=mal")
            passed_mal = resp_mal.status_code == 200 and "application/xml" in resp_mal.headers.get("content-type", "")
            record_result("Export Bookmarks (MAL)", "GET /api/user/export?format=mal", resp_mal.status_code, passed_mal, f"Content-Type: {resp_mal.headers.get('content-type')}")

        with patch.object(ComixAPI, "export_user_bookmarks", return_value="ID,Title,Chapter\n1,Solo,10"):
            resp_csv = client.get("/api/user/export?format=csv")
            passed_csv = resp_csv.status_code == 200 and "text/csv" in resp_csv.headers.get("content-type", "")
            record_result("Export Bookmarks (CSV)", "GET /api/user/export?format=csv", resp_csv.status_code, passed_csv, f"Content-Type: {resp_csv.headers.get('content-type')}")

        with patch.object(ComixAPI, "export_user_bookmarks", return_value='[{"title": "Solo"}]'):
            resp_json = client.get("/api/user/export?format=json")
            passed_json = resp_json.status_code == 200 and "application/json" in resp_json.headers.get("content-type", "")
            record_result("Export Bookmarks (JSON)", "GET /api/user/export?format=json", resp_json.status_code, passed_json, f"Content-Type: {resp_json.headers.get('content-type')}")

    # 22. POST /api/download/chapter
    fake_ch_file = Path("./tests/dummy_ch.cbz")
    fake_ch_file.write_text("dummy", encoding="utf-8")
    try:
        with patch.object(ComixAPI, "bootstrap"), \
             patch.object(ComixAPI, "fetch_all_chapters", return_value=[{"id": 1, "number": 40.5}]), \
             patch.object(ComixDownloader, "download_chapter", return_value=fake_ch_file):
            payload = {
                "manga": "solo-leveling",
                "chapter_number": 40.5,
                "format": "cbz"
            }
            resp = client.post("/api/download/chapter", json=payload)
            data = resp.json() if resp.status_code == 200 else {}
            passed = resp.status_code == 200 and data.get("success") is True and data.get("chapter") == 40.5
            record_result("Download Chapter", "POST /api/download/chapter", resp.status_code, passed, f"Downloaded: Ch {data.get('chapter')}, Format: {data.get('format')}")
    finally:
        fake_ch_file.unlink(missing_ok=True)

    # 23. POST /api/download/series
    fake_vol_file = Path("./tests/dummy_vol.cbz")
    fake_vol_file.write_text("dummy-volume", encoding="utf-8")
    try:
        with patch.object(ComixAPI, "bootstrap"), \
             patch.object(ComixAPI, "fetch_all_chapters", return_value=[{"id": 1, "number": 1}, {"id": 2, "number": 2}]), \
             patch.object(ComixDownloader, "download_chapter", return_value=fake_vol_file):
            payload = {
                "manga": "solo-leveling",
                "chapter_range": "1-2",
                "format": "cbz",
                "merge": True
            }
            resp = client.post("/api/download/series", json=payload)
            data = resp.json() if resp.status_code == 200 else {}
            passed = resp.status_code == 200 and data.get("success") is True and data.get("total_downloaded") == 2
            record_result("Download Series", "POST /api/download/series", resp.status_code, passed, f"Range: {data.get('chapter_range')}, Total: {data.get('total_downloaded')}")
    finally:
        fake_vol_file.unlink(missing_ok=True)

    print("\n" + "=" * 95)
    total_count = len(results_summary)
    passed_count = sum(1 for r in results_summary if r["passed"])
    print(f"📊 SUMMARY: {passed_count}/{total_count} API Commands & Endpoints Verified Successfully!")
    print("=" * 95 + "\n")
    assert passed_count == total_count, f"Some endpoints failed: {[r for r in results_summary if not r['passed']]}"


if __name__ == "__main__":
    verify_all()
