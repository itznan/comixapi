"""
Unit tests for Direct Chapter URL parsing and --from-here download continuation.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api import ComixAPI
from src.downloader import ComixDownloader


def test_parse_comic_url_standard_title():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.manga_hid == "emqg8"
    assert api.manga_slug == "emqg8-solo-leveling"
    assert api.target_chapter_id is None
    assert api.target_chapter_num is None


def test_parse_comic_url_chapter_with_id_and_float_num():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/9567548-chapter-40.6")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.manga_hid == "emqg8"
    assert api.manga_slug == "emqg8-solo-leveling"
    assert api.target_chapter_id == "9567548"
    assert api.target_chapter_num == 40.6


def test_parse_comic_url_chapter_with_alphanumeric_id():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/k26r-chapter-1/")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.target_chapter_id == "k26r"
    assert api.target_chapter_num == 1


def test_parse_comic_url_chapter_num_only():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/chapter-15")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.target_chapter_num == 15


def test_parse_comic_url_chapter_short_ch():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/ch-7.5")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.target_chapter_num == 7.5


def test_parse_comic_url_chapter_numeric_id_only():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/9567548")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.target_chapter_id == "9567548"


def test_direct_chapter_download_single():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/9567548-chapter-40.6",
        from_here=False
    )
    raw_chapters = [
        {"id": 100, "number": 1, "language": "en", "votes": 5, "url": "/title/emqg8-solo-leveling/100-chapter-1"},
        {"id": 9567548, "number": 40.6, "language": "en", "votes": 10, "url": "/title/emqg8-solo-leveling/9567548-chapter-40.6"},
        {"id": 200, "number": 41, "language": "en", "votes": 8, "url": "/title/emqg8-solo-leveling/200-chapter-41"},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    assert len(result) == 1
    assert result[0]["id"] == 9567548
    assert result[0]["number"] == 40.6


def test_direct_chapter_download_from_here():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/9567548-chapter-40.6",
        from_here=True
    )
    raw_chapters = [
        {"id": 100, "number": 1, "language": "en", "votes": 5},
        {"id": 101, "number": 40, "language": "en", "votes": 5},
        {"id": 9567548, "number": 40.6, "language": "en", "votes": 10},
        {"id": 200, "number": 41, "language": "en", "votes": 8},
        {"id": 201, "number": 42, "language": "en", "votes": 12},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    assert len(result) == 3
    numbers = [c["number"] for c in result]
    assert numbers == [40.6, 41, 42]


def test_direct_chapter_not_found_returns_empty():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/99999999-chapter-999",
        from_here=False
    )
    raw_chapters = [
        {"id": 100, "number": 1, "language": "en", "votes": 5},
        {"id": 200, "number": 2, "language": "en", "votes": 8},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    # Must NOT fallback to downloading chapter 1 & 2
    assert result == []


def test_direct_chapter_custom_language_preserved():
    # If user provides a Spanish chapter URL, it should be selected even if default lang is en
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/8888-chapter-5",
        lang="en",
        from_here=False
    )
    raw_chapters = [
        {"id": 7777, "number": 5, "language": "en", "votes": 5},
        {"id": 8888, "number": 5, "language": "es", "votes": 20},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    assert len(result) == 1
    assert result[0]["id"] == 8888
    assert result[0]["language"] == "es"


def test_title_url_with_from_here_and_range():
    # When using a title URL with -c 3 --from-here
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling",
        from_here=True
    )
    raw_chapters = [
        {"id": 1, "number": 1, "language": "en", "votes": 5},
        {"id": 2, "number": 2, "language": "en", "votes": 5},
        {"id": 3, "number": 3, "language": "en", "votes": 5},
        {"id": 4, "number": 4, "language": "en", "votes": 5},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="3")
    assert len(result) == 2
    assert [c["number"] for c in result] == [3, 4]


def test_parse_comic_url_with_query_and_trailing_slash():
    api = ComixAPI("https://comix.to/title/emqg8-solo-leveling/9567548-chapter-40.6/?ref=bookmark#comments")
    title_url = api.parse_comic_url()
    assert title_url == "https://comix.to/title/emqg8-solo-leveling"
    assert api.target_chapter_id == "9567548"
    assert api.target_chapter_num == 40.6


def test_from_here_deduplicates_competing_scanlators():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/10-chapter-10",
        from_here=True
    )
    raw_chapters = [
        {"id": 1, "number": 9, "language": "en", "votes": 5},
        # Chapter 10 has an official version and an unofficial version with more votes
        {"id": 10, "number": 10, "language": "en", "isOfficial": True, "votes": 5},
        {"id": 11, "number": 10, "language": "en", "isOfficial": False, "votes": 100},
        # Chapter 11 has competing scanlations by votes
        {"id": 20, "number": 11, "language": "en", "votes": 20},
        {"id": 21, "number": 11, "language": "en", "votes": 50},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    assert len(result) == 2
    assert result[0]["number"] == 10
    assert result[0]["id"] == 10  # official preferred
    assert result[1]["number"] == 11
    assert result[1]["id"] == 21  # highest votes preferred


def test_direct_chapter_matched_by_url_field():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/emqg8-solo-leveling/abc1234-chapter-33",
        from_here=False
    )
    raw_chapters = [
        {"id": 500, "number": 33, "language": "en", "url": "/title/emqg8-solo-leveling/abc1234-chapter-33"},
        {"id": 501, "number": 33, "language": "en", "url": "/title/emqg8-solo-leveling/xyz9999-chapter-33"},
    ]

    result = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec="all")
    assert len(result) == 1
    assert result[0]["id"] == 500
