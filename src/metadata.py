"""
Metadata generation (ComicInfo.xml) and cover image management for Comix.to downloads.
Compatible with Komga, Kavita, Tachiyomi, Mihon, and modern comic readers.
"""

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
    """Generate standard ComicInfo.xml metadata string for CBZ/archives."""
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
    synopsis = manga_metadata.get("synopsis")
    if synopsis:
        summary_elem = ET.SubElement(root, "Summary")
        summary_elem.text = synopsis.strip()

    # Authors & Artists
    authors = [a.get("title") for a in manga_metadata.get("authors", []) if a.get("title")]
    if authors:
        writer_elem = ET.SubElement(root, "Writer")
        writer_elem.text = ", ".join(authors)

    artists = [a.get("title") for a in manga_metadata.get("artists", []) if a.get("title")]
    if artists:
        penciller_elem = ET.SubElement(root, "Penciller")
        penciller_elem.text = ", ".join(artists)

    # Genres & Tags
    genres = [g.get("title") for g in manga_metadata.get("genres", []) if g.get("title")]
    if genres:
        genre_elem = ET.SubElement(root, "Genre")
        genre_elem.text = ", ".join(genres)

    tags = [t.get("title") for t in manga_metadata.get("tags", []) if t.get("title")]
    demographics = [d.get("title") for d in manga_metadata.get("demographics", []) if d.get("title")]
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

    # Page count
    if page_count > 0:
        pc_elem = ET.SubElement(root, "PageCount")
        pc_elem.text = str(page_count)

    # Scanlation group
    if chapter and chapter.get("group") and chapter["group"].get("name"):
        trans_elem = ET.SubElement(root, "Translator")
        trans_elem.text = chapter["group"]["name"]

    # Manga format
    manga_elem = ET.SubElement(root, "Manga")
    m_type = (manga_metadata.get("type") or "").lower()
    if m_type in ("manhwa", "manhua"):
        manga_elem.text = "Yes"  # Webtoon vertical
    else:
        manga_elem.text = "YesAndRightToLeft"

    raw_xml = ET.tostring(root, encoding="utf-8")
    dom = minidom.parseString(raw_xml)
    return dom.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")


def download_cover(poster_url: str, save_path: Path) -> bool:
    """Download cover image poster to disk."""
    if not poster_url:
        return False
    save_path = Path(save_path)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if save_path.exists() and save_path.stat().st_size > 500:
        return True

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL
    }
    try:
        req = urllib.request.Request(poster_url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        save_path.write_bytes(data)
        return True
    except Exception as e:
        return False
