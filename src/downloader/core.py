"""
Core Comix.to download orchestration: chapter filtering, deduplication, PDF/CBZ/EPUB creation, and volume merging.
"""

from pathlib import Path
from ..api import ComixAPI
from ..cookies import find_default_cookies, parse_cookie_file
from ..utils import sanitize_filename, parse_chapter_spec, print_groups_table
from ..pdf import build_pdf_from_urls, merge_pdf_files, build_cbz_from_urls, merge_cbz_files, build_epub_from_urls
from ..metadata import save_comic_info_xml, download_cover, generate_comic_info_xml
from .interactive import InteractiveSearchMixin
from .sync import SyncMixin
from .collections import CollectionDownloaderMixin


class ComixDownloader(InteractiveSearchMixin, SyncMixin, CollectionDownloaderMixin):
    """Orchestrates chapter discovery, image downloading, and multi-format document compilation for Comix.to."""

    def __init__(self, target_url: str = "", output_dir: str = None,
                 cookie_file: str = None, concurrency: int = 8,
                 preferred_group: str = None, lang: str = "en",
                 merge_all: bool = False, keep_images: bool = False,
                 use_aria2: bool = None, from_here: bool = False,
                 include_cover: bool = True, cover_first: bool = False,
                 generate_comicinfo: bool = True, export_format: str = "pdf"):
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
        self.from_here = from_here
        self.include_cover = include_cover
        self.cover_first = cover_first
        self.generate_comicinfo = generate_comicinfo

        fmt = (export_format or "pdf").strip().lower()
        self.export_format = fmt if fmt in ("pdf", "cbz", "epub", "both") else "pdf"

        self.api = ComixAPI(self.target_url, self.cookie_header)

    def filter_and_deduplicate(self, chapters: list, chapter_range_spec: str = None) -> list:
        """Filter chapters by language/group, handle direct chapter targeting and --from-here, and pick best version per chapter number."""
        target_ch = None
        has_target = bool(self.api.target_chapter_id or self.api.target_chapter_num is not None)

        if has_target:
            tid = str(self.api.target_chapter_id) if self.api.target_chapter_id else None
            tnum = self.api.target_chapter_num

            candidates = []
            if tid:
                candidates = [
                    c for c in chapters
                    if str(c.get("id")) == tid or
                       str(c.get("hid")) == tid or
                       (c.get("url") and (f"/{tid}-" in c.get("url", "") or c.get("url", "").rstrip("/").endswith(f"/{tid}")))
                ]

            if not candidates and tnum is not None:
                candidates = [c for c in chapters if c.get("number") == tnum]

            if not candidates and tid:
                try:
                    num_val = float(tid)
                    cand_num = int(num_val) if num_val.is_integer() else num_val
                    candidates = [c for c in chapters if c.get("number") == cand_num]
                except ValueError:
                    pass

            if candidates:
                lang_matches = [c for c in candidates if c.get("language") == self.lang]
                pool = lang_matches if lang_matches else candidates
                target_ch = sorted(pool, key=lambda x: (
                    1 if x.get("isOfficial") else 0,
                    x.get("votes", 0) or 0,
                    x.get("id", 0)
                ), reverse=True)[0]
            else:
                desc = tid or tnum
                print(f"[!] Warning: Target chapter '{desc}' not found in chapter list.")
                return []

            if not self.from_here:
                print(f"[*] Downloading targeted Chapter {target_ch.get('number')} only.")
                return [target_ch]

            target_num = target_ch.get("number", 0)
            target_lang = target_ch.get("language") or self.lang
            print(f"[*] --from-here enabled: Starting from Chapter {target_num} onwards.")

            if target_lang:
                lang_filtered = [c for c in chapters if c.get("language") == target_lang]
                if lang_filtered:
                    chapters = lang_filtered

            chapters = [c for c in chapters if c.get("number") is not None and c.get("number") >= target_num]
            chapter_range_spec = None

        else:
            # Standard manga title URL: filter by language
            if self.lang:
                filtered = [c for c in chapters if c.get("language") == self.lang]
                if filtered:
                    chapters = filtered

        # Filter by preferred scanlation group if specified
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

        # Deduplicate: pick best candidate per chapter number
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

        # Handle --from-here if passed with a title URL and chapter range like "-c 20 --from-here"
        if self.from_here and not target_ch and chapter_range_spec:
            try:
                start_num = float(chapter_range_spec.strip().rstrip("+"))
                start_clean = int(start_num) if start_num.is_integer() else start_num
                deduped = [c for c in deduped if c.get("number", 0) >= start_clean]
                print(f"[*] Downloading from Chapter {start_clean} onwards ({len(deduped)} chapters).")
                return deduped
            except ValueError:
                pass

        if target_ch and self.from_here:
            print(f"[*] Downloading from Chapter {target_ch.get('number')} onwards ({len(deduped)} chapters).")

        # Apply chapter range filters if specified
        if chapter_range_spec and str(chapter_range_spec).strip().lower() != "all":
            spec_lower = str(chapter_range_spec).strip().lower()
            if spec_lower in ("latest", "last"):
                if deduped:
                    deduped = [deduped[-1]]
                    print(f"[*] Downloading latest Chapter {deduped[0].get('number')} only.")
            else:
                selected_numbers = parse_chapter_spec(chapter_range_spec)
                deduped = [c for c in deduped if c.get("number") in selected_numbers]

        return deduped

    def download_chapter(self, chapter: dict, out_folder: Path, cover_image: Path = None) -> Path:
        """Download single chapter and convert to specified format (PDF, CBZ, EPUB)."""
        ch_num = chapter.get("number", 0)
        ch_name = chapter.get("name") or chapter.get("title") or ""
        group_name = (chapter.get("group") or {}).get("name", "")

        prefix = f"Ch {int(ch_num):03d}" if (isinstance(ch_num, int) or (isinstance(ch_num, float) and ch_num.is_integer())) else f"Ch {ch_num}"
        clean_name = f" - {sanitize_filename(ch_name)}" if ch_name else ""
        clean_group = f" [{sanitize_filename(group_name)}]" if group_name else ""
        base_stem = f"{sanitize_filename(self.api.manga_title)} - {prefix}{clean_name}{clean_group}"

        target_ext = ".cbz" if self.export_format == "cbz" else (".epub" if self.export_format == "epub" else ".pdf")
        target_path = out_folder / f"{base_stem}{target_ext}"

        if target_path.exists() and target_path.stat().st_size > 1000:
            print(f"[*] Chapter {ch_num} already exists: {target_path.name} (skipping)")
            return target_path

        img_urls = self.api.fetch_chapter_pages(chapter)
        if not img_urls:
            print(f"[!] Warning: Chapter {ch_num} has no pages available.")
            return None

        # Build chapter-specific ComicInfo.xml metadata for CBZ
        ch_comicinfo_str = None
        if self.generate_comicinfo and hasattr(self.api, "metadata") and self.api.metadata:
            ch_comicinfo_str = generate_comic_info_xml(self.api.metadata, chapter=chapter, page_count=len(img_urls))

        saved_path = None
        if self.export_format == "cbz":
            success = build_cbz_from_urls(
                img_urls=img_urls,
                cbz_path=target_path,
                concurrency=self.concurrency,
                use_aria2=self.use_aria2,
                keep_images=self.keep_images,
                desc=f"Ch.{ch_num} pages",
                cover_image_path=cover_image,
                comic_info_xml_str=ch_comicinfo_str
            )
            if success and target_path.exists():
                print(f"[+] Saved CBZ: {target_path.name} ({len(img_urls)} pages, {target_path.stat().st_size // 1024} KB)")
                saved_path = target_path

        elif self.export_format == "epub":
            success = build_epub_from_urls(
                img_urls=img_urls,
                epub_path=target_path,
                concurrency=self.concurrency,
                use_aria2=self.use_aria2,
                keep_images=self.keep_images,
                desc=f"Ch.{ch_num} pages",
                cover_image_path=cover_image,
                title=f"{self.api.manga_title} - Ch.{ch_num}"
            )
            if success and target_path.exists():
                print(f"[+] Saved EPUB: {target_path.name} ({len(img_urls)} pages, {target_path.stat().st_size // 1024} KB)")
                saved_path = target_path

        elif self.export_format == "both":
            pdf_path = out_folder / f"{base_stem}.pdf"
            cbz_path = out_folder / f"{base_stem}.cbz"
            build_pdf_from_urls(
                img_urls=img_urls,
                pdf_path=pdf_path,
                concurrency=self.concurrency,
                use_aria2=self.use_aria2,
                keep_images=True,
                desc=f"Ch.{ch_num} PDF",
                cover_image_path=cover_image
            )
            build_cbz_from_urls(
                img_urls=img_urls,
                cbz_path=cbz_path,
                concurrency=self.concurrency,
                use_aria2=self.use_aria2,
                keep_images=self.keep_images,
                desc=f"Ch.{ch_num} CBZ",
                cover_image_path=cover_image,
                comic_info_xml_str=ch_comicinfo_str
            )
            saved_path = cbz_path if cbz_path.exists() else pdf_path

        else:  # Default: PDF
            success = build_pdf_from_urls(
                img_urls=img_urls,
                pdf_path=target_path,
                concurrency=self.concurrency,
                use_aria2=self.use_aria2,
                keep_images=self.keep_images,
                desc=f"Ch.{ch_num} pages",
                cover_image_path=cover_image
            )
            if success and target_path.exists():
                print(f"[+] Saved PDF: {target_path.name} ({len(img_urls)} pages, {target_path.stat().st_size // 1024} KB)")
                saved_path = target_path

        return saved_path

    def run(self, chapter_range: str = "all"):
        """Run the full download pipeline."""
        try:
            self.api.bootstrap()
            raw_chapters = self.api.fetch_all_chapters()
            chapters = self.filter_and_deduplicate(raw_chapters, chapter_range)

            if not chapters:
                print("[!] No chapters found matching the specified criteria.")
                return

            print(f"[*] Preparing to download {len(chapters)} chapters ({self.export_format.upper()} format).")

            if not self.output_dir:
                self.output_dir = Path("./downloads") / sanitize_filename(self.api.manga_title)
            self.output_dir.mkdir(parents=True, exist_ok=True)
            print(f"[*] Output directory: {self.output_dir.resolve()}")

            # 1. Download official high-res cover poster and save as cover.jpg
            cover_path = self.output_dir / "cover.jpg"
            if self.include_cover:
                poster_url = None
                poster_data = self.api.metadata.get("poster")
                if isinstance(poster_data, dict):
                    poster_url = poster_data.get("large") or poster_data.get("medium")
                elif isinstance(poster_data, str):
                    poster_url = poster_data

                if poster_url:
                    if download_cover(poster_url, cover_path):
                        print(f"[+] Downloaded official cover poster: {cover_path.name}")

            # 2. Generate standard ComicInfo.xml metadata for media servers (Komga, Kavita, Calibre)
            comicinfo_path = self.output_dir / "ComicInfo.xml"
            if self.generate_comicinfo:
                save_comic_info_xml(self.api.metadata, comicinfo_path)
                print(f"[+] Generated ComicInfo.xml metadata for {self.api.manga_title}")

            downloaded_files = []
            for idx, ch in enumerate(chapters, 1):
                print(f"\n--- [{idx}/{len(chapters)}] Chapter {ch.get('number')} ---")
                ch_num = ch.get("number")
                ch_cover = None
                if self.include_cover and cover_path.exists():
                    if self.cover_first or (ch_num in (1, 1.0, 0, 0.0) and not self.merge_all):
                        ch_cover = cover_path

                file_path = self.download_chapter(ch, self.output_dir, cover_image=ch_cover)
                if file_path and file_path.exists():
                    downloaded_files.append(file_path)

            if self.merge_all and downloaded_files:
                merged_cover = cover_path if (self.include_cover and cover_path.exists()) else None
                merged_stem = f"{sanitize_filename(self.api.manga_title)} - Complete"

                if self.export_format == "cbz":
                    merged_path = self.output_dir / f"{merged_stem}.cbz"
                    merge_cbz_files(downloaded_files, merged_path, cover_image_path=merged_cover, comic_info_xml_path=comicinfo_path)
                elif self.export_format == "epub":
                    pass
                else:
                    merged_path = self.output_dir / f"{merged_stem}.pdf"
                    merge_pdf_files(downloaded_files, merged_path, cover_image_path=merged_cover)

            print(f"\n[OK] Finished downloading! {len(downloaded_files)} {self.export_format.upper()} files saved in:")
            print(f"    {self.output_dir.resolve()}")

        finally:
            self.api.close()

    def list_groups(self) -> list:
        """Display all scanlation groups that contributed to this title."""
        try:
            self.api.bootstrap()
            groups = self.api.get_manga_groups()
            title = self.api.manga_title or self.api.manga_slug or "Manga"
            print_groups_table(groups, manga_title=title)
            return groups
        finally:
            self.api.close()
