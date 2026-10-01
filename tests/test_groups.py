"""
Unit tests for Scanlation Group Discovery (/manga/{id}/groups) and -g/--group filtering.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import ComixAPI
from src.downloader import ComixDownloader
from src.utils import print_groups_table


def test_get_manga_groups_with_mock():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling")
    # Mock bridge and http_get
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "mock_sig"}
    api.bridge.decrypt.return_value = {
        "result": [
            {"id": 10, "name": "Asura Scans", "slug": "asura-scans"},
            {"id": 25, "name": "Reaper Scans", "slug": "reaper-scans"},
        ]
    }
    api._http_get = MagicMock(return_value={"mock": "data"})

    groups = api.get_manga_groups()
    assert len(groups) == 2
    assert groups[0]["name"] == "Asura Scans"
    assert groups[0]["id"] == 10
    assert groups[1]["name"] == "Reaper Scans"
    assert groups[1]["id"] == 25


def test_get_manga_groups_slug_sanitization():
    api = ComixAPI("")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"_": "sig"}
    api.bridge.decrypt.return_value = {"result": [{"id": 1, "name": "OmegaScans"}]}
    api._http_get = MagicMock(return_value={})

    # Pass full slug with title
    groups = api.get_manga_groups("emqg8-solo-leveling")
    assert len(groups) == 1
    # Check that bridge.sign was called with sanitized /manga/emqg8/groups
    call_args = api.bridge.sign.call_args[0]
    assert call_args[0] == "/manga/emqg8/groups"


def test_list_groups_downloader():
    downloader = ComixDownloader("https://comix.to/title/emqg8-solo-leveling")
    downloader.api.bootstrap = MagicMock()
    downloader.api.close = MagicMock()
    downloader.api.get_manga_groups = MagicMock(return_value=[
        {"id": 5, "name": "Alpha Scans", "slug": "alpha-scans"},
        {"id": 9, "name": "Beta Scans", "slug": "beta-scans"}
    ])

    groups = downloader.list_groups()
    assert len(groups) == 2
    assert groups[0]["name"] == "Alpha Scans"
    assert groups[1]["name"] == "Beta Scans"
    assert downloader.api.close.called


def test_print_groups_table(capsys):
    groups = [
        {"id": 42, "name": "Flame Comics", "slug": "flame-comics"},
        {"id": 88, "name": "Void Scans", "slug": "void-scans"},
    ]
    print_groups_table(groups, manga_title="Solo Leveling")
    captured = capsys.readouterr().out
    assert "Flame Comics" in captured
    assert "Void Scans" in captured
    assert "42" in captured
    assert "-g" in captured
