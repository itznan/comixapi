"""
Unit tests for comix downloader utilities and chapter parsing.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils import parse_chapter_spec, sanitize_filename, print_manga_table


def test_sanitize_filename():
    assert sanitize_filename('Solo: Leveling / Ragnarok * "Test"?') == "Solo Leveling  Ragnarok  Test"
    assert sanitize_filename("Normal Title 123") == "Normal Title 123"
    assert sanitize_filename("Chapter <10> | [Group]") == "Chapter 10  [Group]"


def test_parse_chapter_spec_range():
    res = parse_chapter_spec("1-5")
    assert res == {1, 2, 3, 4, 5}


def test_parse_chapter_spec_comma():
    res = parse_chapter_spec("1, 3, 7")
    assert res == {1, 3, 7}


def test_parse_chapter_spec_mixed():
    res = parse_chapter_spec("1-3, 5, 8-10")
    assert res == {1, 2, 3, 5, 8, 9, 10}


def test_parse_chapter_spec_decimal():
    res = parse_chapter_spec("12.5, 13")
    assert 12.5 in res
    assert 13 in res


def test_parse_chapter_spec_plus():
    res = parse_chapter_spec("9990+")
    assert 9990 in res
    assert 9995 in res
    assert 9989 not in res


def test_parse_chapter_spec_keywords_safe():
    # Keywords should not raise exceptions
    assert parse_chapter_spec("all") == set()
    assert parse_chapter_spec("latest") == set()
    assert parse_chapter_spec("last") == set()
    assert parse_chapter_spec("invalid, 5") == {5}


def test_print_manga_table_empty(capsys):
    print_manga_table([])
    captured = capsys.readouterr()
    assert "No titles found" in captured.out


def test_print_manga_table_renders(capsys):
    sample = [
        {
            "id": 32026,
            "title": "Solo Leveling",
            "type": "manhwa",
            "status": "finished",
            "ratedAvg": 9.2,
            "latestChapter": 200,
            "url": "/title/emqg8-solo-leveling"
        }
    ]
    print_manga_table(sample)
    captured = capsys.readouterr()
    # Ensure title and latest chapter are in output
    assert "Solo Leveling" in captured.out
    assert "32026" in captured.out
    assert "200" in captured.out
