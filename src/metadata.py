"""
Metadata generation (ComicInfo.xml) and cover image management for Comix.to downloads.
Compatible with Komga, Kavita, Tachiyomi, Mihon, and modern comic readers.
"""

import re
import xml.etree.ElementTree as ET
from xml.dom import minidom
from pathlib import Path
import urllib.request
from .config import USER_AGENT, BASE_URL


def generate_comic_info_xml(
    manga_metadata: dict,
    chapter: dict = None,
    page_count: int = 0
) -> str:
    """Generate standard ComicInfo.xml metadata string for CBZ/archives and media servers."""
    root = ET.Element("ComicInfo")
    root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    root.set("xmlns:xsd", "http://www.w3.org/2001/XMLSchema")

    title = manga_metadata.get("title") or "Unknown Manga"
    ch_num = chapter.get("number") if chapter else None
    ch_title = chapter.get("name") or chapter.get("title") if chapter else ""

    # Title & Series
    if ch_num is not None:
        title_elem = ET.SubElement(root, "Title")
        title_elem.text = f"Chapter {ch_num}" + (f" - {ch_title}" if ch_title else "")
        num_elem = ET.SubElement(root, "Number")
        num_elem.text = str(ch_num)
    else:
        title_elem = ET.SubElement(root, "Title")
        title_elem.text = title

    series_elem = ET.SubElement(root, "Series")
    series_elem.text = title

    # Summary
    synopsis = manga_metadata.get("synopsis") or ""
    if synopsis:
        # Strip potential HTML tags
        clean_synopsis = re.sub(r"<[^>]+>", "", synopsis).strip()
        if clean_synopsis:
            summary_elem = ET.SubElement(root, "Summary")
            summary_elem.text = clean_synopsis

    # Authors & Artists
    authors = [(a.get("title") or a.get("name")) for a in manga_metadata.get("authors", []) if isinstance(a, dict) and (a.get("title") or a.get("name"))]
    if authors:
        writer_elem = ET.SubElement(root, "Writer")
        writer_elem.text = ", ".join(authors)

    artists = [(a.get("title") or a.get("name")) for a in manga_metadata.get("artists", []) if isinstance(a, dict) and (a.get("title") or a.get("name"))]
    if artists:
        penciller_elem = ET.SubElement(root, "Penciller")
        penciller_elem.text = ", ".join(artists)

    # Publishers
    publishers = [(p.get("title") or p.get("name")) for p in manga_metadata.get("publishers", []) if isinstance(p, dict) and (p.get("title") or p.get("name"))]
    if publishers:
        pub_elem = ET.SubElement(root, "Publisher")
        pub_elem.text = ", ".join(publishers)

    # Genres & Tags
    genres = [(g.get("title") or g.get("name")) for g in manga_metadata.get("genres", []) if isinstance(g, dict) and (g.get("title") or g.get("name"))]
    if genres:
        genre_elem = ET.SubElement(root, "Genre")
        genre_elem.text = ", ".join(genres)

    tags = [(t.get("title") or t.get("name")) for t in manga_metadata.get("tags", []) if isinstance(t, dict) and (t.get("title") or t.get("name"))]
    demographics = [(d.get("title") or d.get("name")) for d in manga_metadata.get("demographics", []) if isinstance(d, dict) and (d.get("title") or d.get("name"))]
    all_tags = tags + demographics
    if all_tags:
        tags_elem = ET.SubElement(root, "Tags")
        tags_elem.text = ", ".join(all_tags)

    # Year
    year = manga_metadata.get("year")
    if year:
        year_elem = ET.SubElement(root, "Year")
        year_elem.text = str(year)

    # Web URL
    url_slug = manga_metadata.get("url") or f"/title/{manga_metadata.get('hid', '')}"
    web_elem = ET.SubElement(root, "Web")
    web_elem.text = f"{BASE_URL}{url_slug}"

    # Community Rating
    rated_avg = manga_metadata.get("ratedAvg") or manga_metadata.get("ratedScore")
    if rated_avg:
        cr_elem = ET.SubElement(root, "CommunityRating")
        cr_elem.text = str(rated_avg)

    # Age / Content Rating
    content_rating = manga_metadata.get("contentRating")
    if content_rating:
        ar_elem = ET.SubElement(root, "AgeRating")
        cr_map = {
            "safe": "Everyone",
            "suggestive": "Teen",
            "erotica": "Mature 17+",
            "pornographic": "Adult 18+"
        }
        ar_elem.text = cr_map.get(content_rating.lower(), content_rating.capitalize())

    # Total Chapters Count
    total_chapters = manga_metadata.get("finalChapter") or manga_metadata.get("latestChapter")
    if total_chapters:
        count_elem = ET.SubElement(root, "Count")
        count_elem.text = str(total_chapters)

    # Page count
    if page_count > 0:
        pc_elem = ET.SubElement(root, "PageCount")
        pc_elem.text = str(page_count)

    # Scanlation group / Translator
    if chapter and chapter.get("group") and chapter["group"].get("name"):
        trans_elem = ET.SubElement(root, "Translator")
        trans_elem.text = chapter["group"]["name"]

    # Language
    lang_iso = (chapter.get("language") if chapter else None) or manga_metadata.get("originalLanguage") or "en"
    lang_elem = ET.SubElement(root, "LanguageISO")
    lang_elem.text = lang_iso

    # Manga format & Webtoon setting
    m_type = (manga_metadata.get("type") or "").lower()
    format_elem = ET.SubElement(root, "Format")
    if m_type in ("manhwa", "manhua"):
        format_elem.text = "Webtoon"
    else:
        format_elem.text = "Manga"

    manga_elem = ET.SubElement(root, "Manga")
    if m_type in ("manhwa", "manhua"):
        manga_elem.text = "Yes"  # Webtoon vertical
    else:
        manga_elem.text = "YesAndRightToLeft"

    # External Links in Notes for media servers (Komga, Kavita)
    links = manga_metadata.get("links") or {}
    link_lines = []
    link_labels = [
        ("mal", "MyAnimeList"),
        ("al", "AniList"),
        ("mu", "MangaUpdates"),
        ("md", "MangaDex"),
        ("mb", "MangaBaka"),
    ]
    for key, label in link_labels:
        if key in links and links[key]:
            link_lines.append(f"{label}: {links[key]}")

    if link_lines:
        notes_elem = ET.SubElement(root, "Notes")
        notes_elem.text = "External Links:\n" + "\n".join(link_lines)

    raw_xml = ET.tostring(root, encoding="utf-8")
    dom = minidom.parseString(raw_xml)
    return dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def save_comic_info_xml(
    manga_metadata: dict,
    out_path: Path,
    chapter: dict = None,
    page_count: int = 0
) -> Path:
    """Generate and write standard ComicInfo.xml to file or directory."""
    xml_content = generate_comic_info_xml(manga_metadata, chapter=chapter, page_count=page_count)
    out_path = Path(out_path)
    if out_path.is_dir() or not out_path.name.lower().endswith(".xml"):
        out_path.mkdir(parents=True, exist_ok=True)
        out_file = out_path / "ComicInfo.xml"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_file = out_path

    out_file.write_text(xml_content, encoding="utf-8")
    return out_file


def download_cover(poster_source, save_path: Path) -> bool:
    """Download official high-res cover poster image to disk."""
    if not poster_source:
        return False

    poster_url = None
    if isinstance(poster_source, dict):
        if "poster" in poster_source and isinstance(poster_source["poster"], (dict, str)):
            poster_source = poster_source["poster"]
        if isinstance(poster_source, dict):
            poster_url = poster_source.get("large") or poster_source.get("medium")
        else:
            poster_url = str(poster_source)
    elif isinstance(poster_source, str):
        poster_url = poster_source.strip()

    if not poster_url:
        return False

    if poster_url.startswith("/"):
        poster_url = f"{BASE_URL}{poster_url}"

    save_path = Path(save_path)
    if save_path.is_dir() or not save_path.suffix:
        save_path.mkdir(parents=True, exist_ok=True)
        save_file = save_path / "cover.jpg"
    else:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_file = save_path

    if save_file.exists() and save_file.stat().st_size > 500:
        return True

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL
    }
    try:
        req = urllib.request.Request(poster_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        save_file.write_bytes(data)
        return True
    except Exception:
        return False
