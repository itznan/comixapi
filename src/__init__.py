"""
Comix.to PDF Downloader package.
"""

from .config import USER_AGENT, BASE_URL, API_BASE
from .downloader import ComixDownloader
from .api import ComixAPI
from .cookies import parse_cookie_file, find_default_cookies
from .utils import sanitize_filename, parse_chapter_spec, print_manga_table, print_groups_table
from .pdf import build_pdf_from_urls, merge_pdf_files, build_cbz_from_urls, merge_cbz_files, build_epub_from_urls
from .metadata import generate_comic_info_xml, save_comic_info_xml, download_cover

__all__ = [
    "ComixDownloader",
    "ComixAPI",
    "parse_cookie_file",
    "find_default_cookies",
    "sanitize_filename",
    "parse_chapter_spec",
    "print_manga_table",
    "print_groups_table",
    "build_pdf_from_urls",
    "merge_pdf_files",
    "build_cbz_from_urls",
    "merge_cbz_files",
    "build_epub_from_urls",
    "generate_comic_info_xml",
    "save_comic_info_xml",
    "download_cover",
]
