"""
Main Downloader orchestrator coordinating API calls, chapter filtering, and PDF generation.
"""

from pathlib import Path
from .config import DEFAULT_CONCURRENCY
from .cookies import find_default_cookies, parse_cookie_file
from .utils import sanitize_filename, parse_chapter_spec
from .api import ComixAPI
from .pdf import build_pdf_from_urls, merge_pdf_files


class ComixDownloader:
    """High-level controller for downloading manga series in PDF format."""

    def __init__(self, target_url: str, output_dir: str = None, cookie_file: str = None,
                 concurrency: int = DEFAULT_CONCURRENCY, preferred_group: str = None,
                 lang: str = "en", merge_all: bool = False, keep_images: bool = False,
                 use_aria2: bool = None):
        self.target_url = target_url
        self.output_dir = Path(output_dir) if output_dir else None
        self.cookie_file = cookie_file or find_default_cookies()
        self.cookie_header = parse_cookie_file(self.cookie_file) if self.cookie_file else ""
        self.concurrency = concurrency
        self.preferred_group = preferred_group
        self.lang = lang
        self.merge_all = merge_all
        self.keep_images = keep_images
        self.use_aria2 = use_aria2

        self.api = ComixAPI(self.target_url, self.cookie_header)

    def filter_and_deduplicate(self, chapters: list, chapter_range_spec: str = None) -> list:
        """Filter chapters by language/group and pick best version per chapter number."""
        if self.lang:
            filtered = [c for c in chapters if c.get("language") == self.lang]
            if filtered:
                chapters = filtered

        if self.preferred_group:
            p_lower = self.preferred_group.lower()
            filtered = [
                c for c in chapters
                if (c.get("group") and p_lower in c["group"].get("name", "").lower()) or
                   str(c.get("groupId")) == self.preferred_group
            ]
            if filtered:
                chapters = filtered
            else:
                print(f"[!] Warning: No chapters matched group '{self.preferred_group}'. Using all groups.")

        grouped = {}
        for c in chapters:
            num = c.get("number")
            if num is None:
                continue
            if num not in grouped:
                grouped[num] = []
            grouped[num].append(c)

        deduped = []
        for num in sorted(grouped.keys()):
            candidates = grouped[num]
            best = sorted(candidates, key=lambda x: (
                1 if x.get("isOfficial") else 0,
                x.get("votes", 0) or 0,
                x.get("id", 0)
            ), reverse=True)[0]
            deduped.append(best)

        if chapter_range_spec and chapter_range_spec.lower() != "all":
            selected_numbers = parse_chapter_spec(chapter_range_spec)
            deduped = [c for c in deduped if c.get("number") in selected_numbers]

        return deduped

    def download_chapter(self, chapter: dict, out_folder: Path) -> Path:
        """Download single chapter and convert to PDF."""
        ch_num = chapter.get("number", 0)
        ch_name = chapter.get("name") or chapter.get("title") or ""
        group_name = (chapter.get("group") or {}).get("name", "")

        prefix = f"Ch {ch_num:03d}" if isinstance(ch_num, int) else f"Ch {ch_num}"
        clean_name = f" - {sanitize_filename(ch_name)}" if ch_name else ""
        clean_group = f" [{sanitize_filename(group_name)}]" if group_name else ""
        pdf_filename = f"{sanitize_filename(self.api.manga_title)} - {prefix}{clean_name}{clean_group}.pdf"
        pdf_path = out_folder / pdf_filename

        if pdf_path.exists() and pdf_path.stat().st_size > 1000:
            print(f"[*] Chapter {ch_num} already exists: {pdf_path.name} (skipping)")
            return pdf_path

        img_urls = self.api.fetch_chapter_pages(chapter)
        if not img_urls:
            print(f"[!] Warning: Chapter {ch_num} has no pages available.")
            return None

        success = build_pdf_from_urls(
            img_urls=img_urls,
            pdf_path=pdf_path,
            concurrency=self.concurrency,
            use_aria2=self.use_aria2,
            keep_images=self.keep_images,
            desc=f"Ch.{ch_num} pages"
        )

        if success and pdf_path.exists():
            print(f"[+] Saved PDF: {pdf_path.name} ({len(img_urls)} pages, {pdf_path.stat().st_size // 1024} KB)")
            return pdf_path
        return None

    def run(self, chapter_range: str = "all"):
        """Run the full download pipeline."""
        try:
            self.api.bootstrap()
            raw_chapters = self.api.fetch_all_chapters()
            chapters = self.filter_and_deduplicate(raw_chapters, chapter_range)

            if not chapters:
                print("[!] No chapters found matching the specified criteria.")
                return

            print(f"[*] Preparing to download {len(chapters)} chapters.")

            if not self.output_dir:
                self.output_dir = Path("./downloads") / sanitize_filename(self.api.manga_title)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[*] Output directory: {self.output_dir.resolve()}")

            downloaded_pdfs = []
            for idx, ch in enumerate(chapters, 1):
                print(f"\n--- [{idx}/{len(chapters)}] Chapter {ch.get('number')} ---")
                pdf_path = self.download_chapter(ch, self.output_dir)
                if pdf_path and pdf_path.exists():
                    downloaded_pdfs.append(pdf_path)

            if self.merge_all and downloaded_pdfs:
                merged_path = self.output_dir / f"{sanitize_filename(self.api.manga_title)} - Complete.pdf"
                merge_pdf_files(downloaded_pdfs, merged_path)

            print(f"\n[OK] Finished downloading! {len(downloaded_pdfs)} PDF files saved in:")
            print(f"    {self.output_dir.resolve()}")

        finally:
            self.api.close()
