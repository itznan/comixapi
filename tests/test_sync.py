import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.api.client import ComixAPI
from src.downloader.core import ComixDownloader


def test_get_following_titles_requires_cookies():
    api = ComixAPI("", cookie_header="")
    with pytest.raises(RuntimeError, match="Session cookies required"):
        api.get_following_titles()


def test_get_following_titles_pagination_and_folder_filtering():
    api = ComixAPI("", cookie_header="auth=123")
    api.bridge = MagicMock()
    api.bridge.sign.side_effect = lambda url_path, params=None, **kw: {**(params or {}), "token": "signed"}

    page1_items = [
        {"title": "Solo Leveling", "hid": "sl123", "bookmarkPivot": {"folderId": 1, "userChapter": 50}},
        {"title": "Tower of God", "hid": "tog456", "bookmarkPivot": {"folderId": 2, "userChapter": 100}},
    ]
    page2_items = [
        {"title": "Omniscient Reader", "hid": "orv789", "bookmarkPivot": {"folderId": 1, "userChapter": 120}},
    ]

    def mock_http_get(url, is_json=True, extra_headers=None):
        if "page=1" in url:
            return {"page": 1}
        return {"page": 2}

    def mock_decrypt(url_path, encrypted):
        if encrypted.get("page") == 1:
            return {"result": {"items": page1_items, "meta": {"hasNext": True, "lastPage": 2}}}
        return {"result": {"items": page2_items, "meta": {"hasNext": False, "lastPage": 2}}}

    with patch.object(api, "_http_get", side_effect=mock_http_get), \
         patch.object(api.bridge, "decrypt", side_effect=mock_decrypt):
        # 1. Fetch all
        all_titles = api.get_following_titles()
        assert len(all_titles) == 3

        # 2. Filter by folder "reading" (folderId 1)
        reading_titles = api.get_following_titles(folder="reading")
        assert len(reading_titles) == 2
        assert {t["title"] for t in reading_titles} == {"Solo Leveling", "Omniscient Reader"}

        # 3. Filter by folder "completed" (folderId 2)
        completed_titles = api.get_following_titles(folder="completed")
        assert len(completed_titles) == 1
        assert completed_titles[0]["title"] == "Tower of God"


def test_get_user_history_normalization():
    api = ComixAPI("", cookie_header="auth=123")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"token": "signed"}

    history_items = [
        {
            "manga": {"title": "Return of the Blossoming Blade", "hid": "mount-hua", "latestChapter": 140},
            "chapter": {"number": 139, "hid": "ch139", "name": "Episode 139"},
            "updatedAt": "2026-09-30T10:00:00Z"
        }
    ]

    with patch.object(api, "_http_get", return_value={"raw": 1}), \
         patch.object(api.bridge, "decrypt", return_value={"result": {"items": history_items}}):
        results = api.get_user_history()
        assert len(results) == 1
        item = results[0]
        assert item["title"] == "Return of the Blossoming Blade"
        assert item["lastReadChapter"] == 139
        assert item["lastReadChapterId"] == "ch139"


def test_export_user_bookmarks_formats():
    api = ComixAPI("", cookie_header="auth=123")
    api.bridge = MagicMock()
    api.bridge.sign.return_value = {"token": "signed"}

    mock_following = [
        {
            "id": 101,
            "title": "Solo Leveling",
            "hid": "solo-leveling",
            "latestChapter": 179,
            "bookmarkPivot": {"folderId": 1, "userChapter": 150, "userScore": 10},
            "links": {"mal": "https://myanimelist.net/manga/121496", "al": "https://anilist.co/manga/105398"}
        }
    ]

    with patch.object(api, "get_following_titles", return_value=mock_following), \
         patch.object(api, "_http_get", side_effect=RuntimeError("Native export simulated offline")):
        # 1. Test MAL XML export
        mal_xml = api.export_user_bookmarks("mal")
        assert "<myanimelist>" in mal_xml
        assert "<manga_mangadb_id>121496</manga_mangadb_id>" in mal_xml
        assert "Solo Leveling" in mal_xml
        assert "<my_read_chapters>150</my_read_chapters>" in mal_xml
        assert "<my_score>10</my_score>" in mal_xml
        # Verify valid XML
        root = ET.fromstring(mal_xml)
        assert root.tag == "myanimelist"

        # 2. Test AniList JSON export
        al_json = api.export_user_bookmarks("anilist")
        al_data = json.loads(al_json)
        assert isinstance(al_data, list)
        assert len(al_data) == 1
        assert al_data[0]["anilist_id"] == 105398
        assert al_data[0]["status"] == "CURRENT"
        assert al_data[0]["progress"] == 150

        # 3. Test CSV export
        csv_data = api.export_user_bookmarks("csv")
        assert "Solo Leveling" in csv_data
        assert "reading" in csv_data

        # 4. Test JSON export
        json_data = api.export_user_bookmarks("json")
        parsed = json.loads(json_data)
        assert parsed[0]["title"] == "Solo Leveling"


def test_sync_library_dry_run_and_skipping(tmp_path):
    mock_following = [
        {
            "title": "Sample Manhwa",
            "hid": "sample-hid",
            "bookmarkPivot": {"folderId": 1, "userChapter": 2},
            "latestChapter": 5
        }
    ]

    # Pre-create chapter 1 and 2 PDFs on disk
    manga_dir = tmp_path / "Sample Manhwa"
    manga_dir.mkdir(parents=True)
    ch1_pdf = manga_dir / "Sample Manhwa - Ch 001.pdf"
    ch1_pdf.write_text("pdf dummy content")
    ch2_pdf = manga_dir / "Sample Manhwa - Ch 002.pdf"
    ch2_pdf.write_text("pdf dummy content")

    raw_chapters = [
        {"number": 1, "hid": "c1"},
        {"number": 2, "hid": "c2"},
        {"number": 3, "hid": "c3"},
        {"number": 4, "hid": "c4"},
    ]

    with patch("src.downloader.sync.find_default_cookies", return_value="fake_cookies.txt"), \
         patch("src.downloader.sync.parse_cookie_file", return_value="auth=123"), \
         patch.object(ComixAPI, "get_following_titles", return_value=mock_following), \
         patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_all_chapters", return_value=raw_chapters), \
         patch.object(ComixDownloader, "download_chapter", return_value=Path("dummy.pdf")) as mock_download:

        # 1. Dry run: should not call download_chapter
        ComixDownloader.sync_library(
            cookie_file="fake_cookies.txt",
            downloader_options={"output_dir": str(tmp_path)},
            dry_run=True
        )
        assert mock_download.call_count == 0

        # 2. Real sync: should only download Ch 3 and Ch 4 (since Ch 1 and 2 already exist)
        ComixDownloader.sync_library(
            cookie_file="fake_cookies.txt",
            downloader_options={"output_dir": str(tmp_path)},
            dry_run=False
        )
        assert mock_download.call_count == 2
        downloaded_ch_nums = [call[0][0]["number"] for call in mock_download.call_args_list]
        assert downloaded_ch_nums == [3, 4]


def test_sync_library_unread_only(tmp_path):
    mock_following = [
        {
            "title": "Action Hero",
            "hid": "hero-hid",
            "bookmarkPivot": {"folderId": 1, "userChapter": 10},
            "latestChapter": 15
        }
    ]

    raw_chapters = [
        {"number": 9, "hid": "c9"},
        {"number": 10, "hid": "c10"},
        {"number": 11, "hid": "c11"},
        {"number": 12, "hid": "c12"},
    ]

    with patch("src.downloader.sync.find_default_cookies", return_value="fake_cookies.txt"), \
         patch("src.downloader.sync.parse_cookie_file", return_value="auth=123"), \
         patch.object(ComixAPI, "get_following_titles", return_value=mock_following), \
         patch.object(ComixAPI, "bootstrap"), \
         patch.object(ComixAPI, "fetch_all_chapters", return_value=raw_chapters), \
         patch.object(ComixDownloader, "download_chapter", return_value=Path("dummy.pdf")) as mock_download:

        # With unread_only=True, only chapters > 10 should be downloaded (Ch 11 and 12)
        ComixDownloader.sync_library(
            unread_only=True,
            cookie_file="fake_cookies.txt",
            downloader_options={"output_dir": str(tmp_path)}
        )
        assert mock_download.call_count == 2
        downloaded_ch_nums = [call[0][0]["number"] for call in mock_download.call_args_list]
        assert downloaded_ch_nums == [11, 12]


def test_list_history_non_interactive():
    mock_history = [
        {"title": "Nano Machine", "hid": "nano-machine", "lastReadChapter": 200, "latestChapter": 220}
    ]

    with patch("src.downloader.sync.find_default_cookies", return_value="fake_cookies.txt"), \
         patch("src.downloader.sync.parse_cookie_file", return_value="auth=123"), \
         patch.object(ComixAPI, "get_user_history", return_value=mock_history):
        results = ComixDownloader.list_history(interactive=False, cookie_file="fake_cookies.txt")
        assert results == mock_history
