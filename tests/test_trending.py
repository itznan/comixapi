"""
Unit tests for Trending & "Top" Discovery (/manga/top) endpoint and workflows.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import ComixAPI
from src.downloader import ComixDownloader


def test_get_top_titles_trending():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {
        "result": [
            {"id": 1, "hid": "abc", "title": "Trending Title 1", "latestChapter": 20},
            {"id": 2, "hid": "def", "title": "Trending Title 2", "latestChapter": 45},
        ]
    }
    api._http_get = MagicMock(return_value={})

    titles = api.get_top_titles(type_filter="trending", days=7, limit=10)
    assert len(titles) == 2
    assert titles[0]["title"] == "Trending Title 1"

    # Verify parameters passed to bridge.sign
    call_args = api.bridge.sign.call_args[1]
    assert call_args["params"]["type"] == "trending"
    assert call_args["params"]["days"] == 7
    assert call_args["params"]["limit"] == 10


def test_get_top_titles_follows_days_capped():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {"result": []}
    api._http_get = MagicMock(return_value={})

    # For 'follows', 30 days is capped to 7 days
    api.get_top_titles(type_filter="follows", days=30, limit=5)
    call_args = api.bridge.sign.call_args[1]
    assert call_args["params"]["type"] == "follows"
    assert call_args["params"]["days"] == 7


def test_get_top_titles_alias_normalization():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {"result": []}
    api._http_get = MagicMock(return_value={})

    api.get_top_titles(type_filter="bookmarks", days=1, limit=5)
    call_args = api.bridge.sign.call_args[1]
    assert call_args["params"]["type"] == "follows"


def test_trending_non_interactive():
    mock_results = [
        {"id": 1, "hid": "t1", "title": "Top One", "latestChapter": 10},
        {"id": 2, "hid": "t2", "title": "Top Two", "latestChapter": 20},
    ]
    with patch.object(ComixAPI, "get_top_titles", return_value=mock_results), \
         patch.object(ComixAPI, "close"):

        res = ComixDownloader.trending(
            trend_type="trending",
            days=1,
            limit=10,
            interactive=False
        )
        assert res == mock_results


def test_trending_auto_download():
    mock_results = [
        {"id": 101, "hid": "auto1", "title": "Auto One", "latestChapter": 5},
    ]

    with patch.object(ComixAPI, "get_top_titles", return_value=mock_results), \
         patch.object(ComixAPI, "close"), \
         patch.object(ComixDownloader, "run") as mock_run:

        res = ComixDownloader.trending(
            trend_type="trending",
            days=7,
            limit=5,
            auto_download=True
        )

        assert res == mock_results
        assert mock_run.called
