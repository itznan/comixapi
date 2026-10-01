"""
Unit and integration tests for Comix Manga API endpoints, Image Proxy, and SFW filter.
"""

from unittest.mock import MagicMock, patch
from io import BytesIO
from fastapi.testclient import TestClient

from src.server import app
from src.api.client import ComixAPI


client = TestClient(app)


# -------------------------------------------------------------
# 1. Image Proxy Tests (Bypass CORS & CORP)
# -------------------------------------------------------------
def test_image_proxy_success():
    """Verify that /api/image proxies images with permissive CORS & CORP headers."""
    dummy_image_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF"
    mock_resp = MagicMock()
    mock_resp.read.return_value = dummy_image_bytes
    mock_resp.headers = {"Content-Type": "image/jpeg"}
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = None

    with patch("urllib.request.urlopen", return_value=mock_resp):
        resp = client.get("/api/image?url=https://static.comix.to/test/image.jpg")
        assert resp.status_code == 200
        assert resp.content == dummy_image_bytes
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.headers["access-control-allow-origin"] == "*"
        assert resp.headers["cross-origin-resource-policy"] == "cross-origin"


def test_image_proxy_invalid_url():
    """Verify that /api/image rejects non-HTTP URLs."""
    resp = client.get("/api/image?url=file:///etc/passwd")
    assert resp.status_code == 400
    assert "Invalid image URL" in resp.json()["detail"]


# -------------------------------------------------------------
# 2. Home Endpoint Tests (/api/manga/home)
# -------------------------------------------------------------
def test_manga_home():
    """Verify /api/manga/home returns popular and latest lists with proxied covers."""
    mock_popular = [
        {
            "hid": "n8we",
            "slug": "the-chick-class-hunter-is-filial",
            "title": "The Chick-Class Hunter is Filial!",
            "poster": {"large": "https://static.comix.to/poster1.jpg"},
            "latest_chapter": {"number": 58},
            "genres": [{"name": "Action"}, {"name": "Fantasy"}]
        }
    ]
    mock_latest = [
        {
            "hid": "sl1",
            "slug": "solo-leveling",
            "title": "Solo Leveling",
            "poster": "https://static.comix.to/poster2.jpg",
            "latest_chapter": {"number": 179},
            "genres": [{"name": "Action"}]
        }
    ]

    with patch.object(ComixAPI, "get_top_titles", return_value=mock_popular), \
         patch.object(ComixAPI, "search_titles", return_value=mock_latest):
        resp = client.get("/api/manga/home")
        assert resp.status_code == 200
        data = resp.json()
        assert "popular" in data
        assert "latest" in data

        pop_item = data["popular"][0]
        assert pop_item["id"] == "n8we-the-chick-class-hunter-is-filial"
        assert pop_item["title"] == "The Chick-Class Hunter is Filial!"
        assert pop_item["cover"].startswith("/api/image?url=")
        assert pop_item["chapter"] == "Ch.58"
        assert "Action" in pop_item["genres"]

        lat_item = data["latest"][0]
        assert lat_item["id"] == "sl1-solo-leveling"
        assert lat_item["chapter"] == "Ch.179"


def test_manga_home_sfw_filter():
    """Verify ?sfw=true on /api/manga/home filters out NSFW content."""
    mock_popular = [
        {
            "hid": "safe1",
            "title": "Safe Adventure",
            "genres": [{"name": "Adventure"}]
        },
        {
            "hid": "nsfw1",
            "title": "Adult Romance",
            "genres": [{"name": "Hentai"}]
        }
    ]
    with patch.object(ComixAPI, "get_top_titles", return_value=mock_popular), \
         patch.object(ComixAPI, "search_titles", return_value=[]):
        resp = client.get("/api/manga/home?sfw=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["popular"]) == 1
        assert data["popular"][0]["title"] == "Safe Adventure"


# -------------------------------------------------------------
# 3. Search Endpoint Tests (/api/manga/search)
# -------------------------------------------------------------
def test_manga_search_advanced():
    """Verify /api/manga/search returns results and pagination structure."""
    mock_items = [
        {
            "hid": "abc",
            "slug": "demon-slayer",
            "title": "Demon Slayer",
            "img": "https://static.comix.to/img.jpg",
            "status": 1,
            "score": 9.5,
            "type": "manga"
        }
    ]
    mock_meta = {"page": 1, "lastPage": 5}

    with patch.object(ComixAPI, "search_titles", return_value=(mock_items, mock_meta)):
        resp = client.get("/api/manga/search?q=demon&types[]=manhwa&status=releasing")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "pagination" in data
        assert data["pagination"]["current_page"] == 1
        assert data["pagination"]["last_page"] == 5

        item = data["results"][0]
        assert item["id"] == "abc-demon-slayer"
        assert item["title"] == "Demon Slayer"
        assert item["img"].startswith("/api/image?url=")
        assert item["score"] == 9.5


# -------------------------------------------------------------
# 4. Comic Details Tests (/api/manga/{id})
# -------------------------------------------------------------
def test_comic_details_success():
    """Verify /api/manga/{id} returns comic object with authors, artists, and scan groups."""
    mock_meta = {
        "hid": "n8we",
        "slug": "the-chick-class-hunter",
        "title": "The Chick-Class Hunter",
        "poster": {"large": "https://static.comix.to/cover.jpg"},
        "demographic": {"name": "Shounen"},
        "authors": [{"name": "John Doe"}],
        "artists": [{"name": "Jane Smith"}],
        "desc": "A great story about hunters...",
        "genres": [{"name": "Action"}, {"name": "Fantasy"}]
    }
    mock_groups = [{"id": 123, "name": "ScanGroup"}]

    def mock_bootstrap(self):
        self.metadata = mock_meta
        self.manga_title = mock_meta.get("title")
        self.manga_slug = mock_meta.get("slug")

    with patch.object(ComixAPI, "bootstrap", side_effect=mock_bootstrap, autospec=True), \
         patch.object(ComixAPI, "get_manga_groups", return_value=mock_groups):
        resp = client.get("/api/manga/n8we-the-chick-class-hunter")
        assert resp.status_code == 200
        data = resp.json()
        assert "comic" in data
        comic = data["comic"]
        assert comic["title"] == "The Chick-Class Hunter"
        assert comic["cover"].startswith("/api/image?url=")
        assert comic["demographics"] == "Shounen"
        assert comic["authors"] == "John Doe"
        assert comic["artists"] == "Jane Smith"
        assert comic["synopsis"] == "A great story about hunters..."
        assert "Action" in comic["genres"]
        assert comic["scanlation_groups"][0]["scanlation_group_id"] == 123


def test_comic_details_sfw_404():
    """Verify /api/manga/{id}?sfw=true returns 404 when comic is mature/NSFW."""
    mock_nsfw_meta = {
        "hid": "adult1",
        "title": "Explicit Title",
        "content_rating": "erotica",
        "genres": [{"name": "Smut"}]
    }
    def mock_bootstrap(self):
        self.metadata = mock_nsfw_meta
        self.manga_title = mock_nsfw_meta.get("title")
        self.manga_slug = "adult1"

    with patch.object(ComixAPI, "bootstrap", side_effect=mock_bootstrap, autospec=True):
        resp = client.get("/api/manga/adult1?sfw=true")
        assert resp.status_code == 404


# -------------------------------------------------------------
# 5. Paginated Chapters Tests (/api/manga/{id}/chapters)
# -------------------------------------------------------------
def test_paginated_chapters():
    """Verify /api/manga/{id}/chapters returns paginated chapter list."""
    mock_page_data = {
        "chapters": [
            {
                "id": "ch1",
                "number": 1,
                "title": "Chapter 1",
                "scanlation_group": {"scanlation_group_id": 42, "name": "Reaper"}
            }
        ],
        "pagination": {"current_page": 1, "last_page": 10, "total": 100, "limit": 30}
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_chapters_page", return_value=mock_page_data):
        resp = client.get("/api/manga/test-slug/chapters?page=1&limit=30")
        assert resp.status_code == 200
        data = resp.json()
        assert "chapters" in data
        assert "pagination" in data
        assert data["chapters"][0]["number"] == 1
        assert data["chapters"][0]["scanlation_group"]["name"] == "Reaper"


# -------------------------------------------------------------
# 6. Read Chapter Images Tests (/api/manga/read)
# -------------------------------------------------------------
def test_read_chapter_images():
    """Verify /api/manga/read returns chapter images wrapped in image proxy."""
    mock_chapter_info = {
        "chapterId": "8295088",
        "total_images": 2,
        "images": [
            {"url": "https://cdn.comix.to/img1.webp", "width": 800, "height": 1200},
            {"url": "https://cdn.comix.to/img2.webp", "width": 800, "height": 1200}
        ]
    }
    with patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "get_chapter_images", return_value=mock_chapter_info):
        resp = client.get("/api/manga/read?chapterId=8295088")
        assert resp.status_code == 200
        data = resp.json()
        assert data["chapterId"] == "8295088"
        assert data["total_images"] == 2
        for img in data["images"]:
            assert img["url"].startswith("/api/image?url=")
            assert img["width"] == 800
            assert img["height"] == 1200


def test_read_chapter_images_missing_id():
    """Verify /api/manga/read returns 400 when chapterId is missing."""
    resp = client.get("/api/manga/read")
    assert resp.status_code == 400


# -------------------------------------------------------------
# 7. Manga Collections Tests (/api/manga/collections/{id})
# -------------------------------------------------------------
def test_manga_collection_endpoint():
    """Verify /api/manga/collections/{id} returns collection metadata and results."""
    mock_meta = {
        "id": 1692,
        "name": "Ongoing Series",
        "description": "Collection description",
        "itemCount": 1,
        "likeCount": 5,
        "cover": {"title": "Cover Comic"}
    }
    mock_items = [
        {
            "hid": "55kym",
            "slug": "villainess-sword",
            "title": "Villainess with a Sword",
            "img": "https://static.comix.to/sword.jpg",
            "latest_chapter": {"number": 60},
            "status": "releasing",
            "score": 7.2,
            "type": "manhwa"
        }
    ]
    with patch.object(ComixAPI, "get_collection", return_value=mock_meta), \
         patch.object(ComixAPI, "get_collection_items", return_value=mock_items):
        resp = client.get("/api/manga/collections/1692")
        assert resp.status_code == 200
        data = resp.json()
        assert "collection" in data
        assert "results" in data
        assert data["collection"]["id"] == 1692
        assert data["collection"]["name"] == "Ongoing Series"
        assert data["results"][0]["id"] == "55kym-villainess-sword"
        assert data["results"][0]["chapter"] == "Ch.60"
        assert data["results"][0]["img"].startswith("/api/image?url=")


# -------------------------------------------------------------
# 8. Browse & Filter Tests (/api/manga/browse & /api/manga/filter)
# -------------------------------------------------------------
def test_manga_browse():
    """Verify /api/manga/browse returns sorted results and pagination."""
    mock_items = [
        {
            "hid": "new1",
            "title": "Brand New Manga",
            "type": "manga",
            "score": 8.0
        }
    ]
    mock_meta = {"page": 1, "lastPage": 20}
    with patch.object(ComixAPI, "search_titles", return_value=(mock_items, mock_meta)):
        resp = client.get("/api/manga/browse")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Brand New Manga"
        assert data["pagination"]["current_page"] == 1


def test_manga_filter():
    """Verify /api/manga/filter queries by genre and returns results."""
    mock_items = [
        {
            "hid": "act1",
            "title": "Action Hero",
            "genres": [{"name": "Action"}]
        }
    ]
    mock_meta = {"page": 1, "lastPage": 3}
    with patch.object(ComixAPI, "search_titles", return_value=(mock_items, mock_meta)):
        resp = client.get("/api/manga/filter?genres=action,adventure")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["title"] == "Action Hero"
