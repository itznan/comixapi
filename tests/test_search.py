"""
Unit tests for Comix.to search, filtering, and chapter selection logic.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import GENRE_MAP, DEMOGRAPHIC_MAP
from src.downloader import ComixDownloader


def test_genre_and_demographic_mappings():
    # Verify core genres
    assert GENRE_MAP.get("action") == 6
    assert GENRE_MAP.get("fantasy") == 12
    assert GENRE_MAP.get("sci-fi") == 24
    assert GENRE_MAP.get("sci fi") == 24
    assert GENRE_MAP.get("martial arts") == 30

    # Verify demographics including aliases
    assert DEMOGRAPHIC_MAP.get("shounen") == 2
    assert DEMOGRAPHIC_MAP.get("shonen") == 2
    assert DEMOGRAPHIC_MAP.get("shoujo") == 1
    assert DEMOGRAPHIC_MAP.get("shojo") == 1
    assert DEMOGRAPHIC_MAP.get("seinen") == 4
    assert DEMOGRAPHIC_MAP.get("josei") == 3


def test_filter_and_deduplicate_by_language_and_group():
    downloader = ComixDownloader(
        target_url="https://comix.to/title/test-manga",
        preferred_group="AlphaScans",
        lang="en"
    )

    chapters = [
        {"id": 1, "number": 1, "language": "en", "group": {"name": "AlphaScans"}, "votes": 10},
        {"id": 2, "number": 1, "language": "en", "group": {"name": "BetaScans"}, "votes": 5},
        {"id": 3, "number": 1, "language": "es", "group": {"name": "AlphaScans"}, "votes": 20},
        {"id": 4, "number": 2, "language": "en", "group": {"name": "AlphaScans"}, "votes": 15},
    ]

    deduped = downloader.filter_and_deduplicate(chapters, chapter_range_spec="all")
    assert len(deduped) == 2
    assert deduped[0]["id"] == 1
    assert deduped[1]["id"] == 4


def test_filter_and_deduplicate_range_selection():
    downloader = ComixDownloader(target_url="https://comix.to/title/test-manga")
    chapters = [
        {"id": i, "number": i, "language": "en", "votes": 10}
        for i in range(1, 11)
    ]

    # Select range 3-5
    filtered = downloader.filter_and_deduplicate(chapters, chapter_range_spec="3-5")
    assert [c["number"] for c in filtered] == [3, 4, 5]

    # Select individual chapters
    filtered_comma = downloader.filter_and_deduplicate(chapters, chapter_range_spec="2, 7, 9")
    assert [c["number"] for c in filtered_comma] == [2, 7, 9]


def test_filter_and_deduplicate_latest_keyword():
    downloader = ComixDownloader(target_url="https://comix.to/title/test-manga")
    chapters = [
        {"id": 1, "number": 1, "language": "en"},
        {"id": 2, "number": 50, "language": "en"},
        {"id": 3, "number": 100, "language": "en"},
    ]

    filtered_latest = downloader.filter_and_deduplicate(chapters, chapter_range_spec="latest")
    assert len(filtered_latest) == 1
    assert filtered_latest[0]["number"] == 100

    filtered_last = downloader.filter_and_deduplicate(chapters, chapter_range_spec="last")
    assert len(filtered_last) == 1
    assert filtered_last[0]["number"] == 100


def test_filter_and_deduplicate_quality_scoring():
    # Official releases or higher voted versions should win deduplication
    downloader = ComixDownloader(target_url="https://comix.to/title/test-manga")
    chapters = [
        {"id": 10, "number": 1, "language": "en", "isOfficial": False, "votes": 10},
        {"id": 20, "number": 1, "language": "en", "isOfficial": True, "votes": 2},
    ]
    deduped = downloader.filter_and_deduplicate(chapters, chapter_range_spec="all")
    assert len(deduped) == 1
    assert deduped[0]["id"] == 20
