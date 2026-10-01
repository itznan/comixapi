"""
Unit tests for ComicInfo.xml metadata generation and cover art management.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.metadata import generate_comic_info_xml, save_comic_info_xml, download_cover


@pytest.fixture
def sample_metadata():
    return {
        "id": 32026,
        "hid": "emqg8",
        "slug": "solo-leveling",
        "url": "/title/emqg8-solo-leveling",
        "title": "Solo Leveling",
        "type": "manhwa",
        "synopsis": "<p>Mysterious portals, known as 'Gates', now dot the world.</p>",
        "year": 2018,
        "contentRating": "safe",
        "ratedAvg": 9.2,
        "latestChapter": 200,
        "finalChapter": 200,
        "originalLanguage": "ko",
        "authors": [
            {"id": 24051, "title": "Chugong"},
            {"id": 24052, "title": "h-goon"}
        ],
        "artists": [
            {"id": 3849, "title": "REDICE Studio"},
            {"id": 24054, "title": "DUBU"}
        ],
        "publishers": [
            {"id": 100, "title": "D&C Media"}
        ],
        "genres": [
            {"title": "Action"},
            {"title": "Fantasy"}
        ],
        "tags": [
            {"title": "Dungeons"},
            {"title": "Hunters"}
        ],
        "demographics": [
            {"title": "Shounen"}
        ],
        "links": {
            "al": "https://anilist.co/manga/105398",
            "mal": "https://myanimelist.net/manga/121496",
            "md": "https://mangadex.org/title/32d76d19-8a05-4db0-9fc2-e0b0648fe9d0",
            "mu": "https://www.mangaupdates.com/series/6z1uqw7",
            "mb": "https://mangabaka.org/3397"
        },
        "poster": {
            "large": "https://static.comix.to/4ec7/i/4/4d/68e0b7f60cecc.jpg",
            "medium": "https://static.comix.to/4ec7/i/4/4d/68e0b7f60cecc@280.jpg"
        }
    }


def test_generate_comic_info_xml_structure(sample_metadata):
    xml_str = generate_comic_info_xml(sample_metadata)
    assert xml_str.startswith("<?xml")

    root = ET.fromstring(xml_str)
    assert root.tag == "ComicInfo"

    # Core elements
    assert root.find("Title").text == "Solo Leveling"
    assert root.find("Series").text == "Solo Leveling"
    assert "Mysterious portals" in root.find("Summary").text
    assert "<p>" not in root.find("Summary").text  # HTML tags stripped

    # Authors, Artists, Publishers
    assert root.find("Writer").text == "Chugong, h-goon"
    assert root.find("Penciller").text == "REDICE Studio, DUBU"
    assert root.find("Publisher").text == "D&C Media"

    # Genres & Tags
    assert root.find("Genre").text == "Action, Fantasy"
    tags_text = root.find("Tags").text
    assert "Dungeons" in tags_text
    assert "Hunters" in tags_text
    assert "Shounen" in tags_text

    # Ratings & counts
    assert root.find("CommunityRating").text == "9.2"
    assert root.find("AgeRating").text == "Everyone"
    assert root.find("Count").text == "200"
    assert root.find("Year").text == "2018"
    assert root.find("LanguageISO").text == "ko"
    assert root.find("Format").text == "Webtoon"
    assert root.find("Manga").text == "Yes"

    # Notes with external links
    notes = root.find("Notes").text
    assert "MyAnimeList: https://myanimelist.net/manga/121496" in notes
    assert "AniList: https://anilist.co/manga/105398" in notes
    assert "MangaDex: https://mangadex.org/title/32d76d19-8a05-4db0-9fc2-e0b0648fe9d0" in notes


def test_generate_comic_info_xml_with_chapter(sample_metadata):
    chapter = {
        "number": 10,
        "title": "Awakening",
        "language": "en",
        "group": {"name": "AsuraScans"}
    }
    xml_str = generate_comic_info_xml(sample_metadata, chapter=chapter, page_count=25)
    root = ET.fromstring(xml_str)

    assert root.find("Title").text == "Chapter 10 - Awakening"
    assert root.find("Number").text == "10"
    assert root.find("PageCount").text == "25"
    assert root.find("Translator").text == "AsuraScans"
    assert root.find("LanguageISO").text == "en"


def test_save_comic_info_xml(sample_metadata, tmp_path):
    out_dir = tmp_path / "Solo Leveling"
    xml_file = save_comic_info_xml(sample_metadata, out_dir)

    assert xml_file.exists()
    assert xml_file.name == "ComicInfo.xml"
    content = xml_file.read_text(encoding="utf-8")
    assert "<Title>Solo Leveling</Title>" in content


def test_download_cover_invalid_inputs(tmp_path):
    # None or empty poster source should return False safely
    assert download_cover(None, tmp_path / "cover.jpg") is False
    assert download_cover("", tmp_path / "cover.jpg") is False
    assert download_cover({}, tmp_path / "cover.jpg") is False
    assert download_cover({"poster": {}}, tmp_path / "cover.jpg") is False
