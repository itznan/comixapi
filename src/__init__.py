"""
Comix.to PDF Downloader package.
"""

from .config import USER_AGENT, BASE_URL, API_BASE
from .downloader import ComixDownloader
from .api import ComixAPI
from .cookies import parse_cookie_file, find_default_cookies
from .utils import sanitize_filename, parse_chapter_spec
from .pdf import build_pdf_from_urls, merge_pdf_files

__all__ = [
    "ComixDownloader",
    "ComixAPI",
    "parse_cookie_file",
    "find_default_cookies",
    "sanitize_filename",
    "parse_chapter_spec",
    "build_pdf_from_urls",
    "merge_pdf_files",
]
