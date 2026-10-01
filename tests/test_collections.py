"""
Unit tests for Curated Collections & Reading Lists Downloader (/collections/{id}/items).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import ComixAPI
from src.downloader import ComixDownloader


def test_parse_collection_id():
    api = ComixAPI("")
    assert api.parse_collection_id("https://comix.to/collection/123-top-10-dungeon-manhwa") == "123"
    assert api.parse_collection_id("https://comix.to/collections/456") == "456"
    assert api.parse_collection_id("collection/789") == "789"
    assert api.parse_collection_id("999-staff-picks") == "999"
    assert api.parse_collection_id("42") == "42"
    assert api.parse_collection_id("https://comix.to/collection/55-action?sort=views#top") == "55"


def test_get_collection_metadata():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": {
            "id": 123,
            "title": "Top 10 Dungeon Manhwa",
            "description": "Best dungeon crawl series"
        }
    }
    api._http_get = MagicMock(return_value={})

    meta = api.get_collection("https://comix.to/collection/123-top-10-dungeon-manhwa")
    assert meta["id"] == 123
    assert meta["title"] == "Top 10 Dungeon Manhwa"
    assert meta["description"] == "Best dungeon crawl series"


def test_get_collection_items_with_pagination():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}

    # Mock page 1 and page 2 responses
    page1_resp = {
        "result": {
            "items": [
                {"manga": {"id": 1, "hid": "aaa", "title": "Series A"}},
                {"id": 2, "hid": "bbb", "title": "Series B"}  # direct format
            ],
            "meta": {"hasNext": True, "lastPage": 2}
        }
    }
    page2_resp = {
        "result": {
            "items": [
                {"manga": {"id": 3, "hid": "ccc", "title": "Series C"}}
            ],
            "meta": {"hasNext": False, "lastPage": 2}
        }
    }

    api.bridge.decrypt.side_effect = [page1_resp, page2_resp]
    api._http_get = MagicMock(return_value={})

    items = api.get_collection_items("123")
    assert len(items) == 3
    assert items[0]["title"] == "Series A"
    assert items[1]["title"] == "Series B"
    assert items[2]["title"] == "Series C"


def test_collection_dry_run_simulation(capsys):
    mock_items = [
        {"id": 1, "hid": "m1", "title": "Title One", "url": "/title/m1-title-one", "latestChapter": 50},
        {"id": 2, "hid": "m2", "title": "Title Two", "url": "/title/m2-title-two", "latestChapter": 100},
    ]

    with patch.object(ComixAPI, "get_collection", return_value={"name": "Curated Best"}), \
         patch.object(ComixAPI, "get_collection_items", return_value=mock_items), \
         patch.object(ComixAPI, "close"):

        result = ComixDownloader.collection(
            collection_target="https://comix.to/collection/77-curated-best",
            interactive=False,
            dry_run=True,
            downloader_options={"chapter_range": "latest"}
        )

        assert result == mock_items
        captured = capsys.readouterr().out
        assert "Curated Best" in captured
        assert "Title One" in captured
        assert "Title Two" in captured
        assert "[DRY RUN]" in captured
