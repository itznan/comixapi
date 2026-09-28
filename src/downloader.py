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
                 use_aria2: bool = None, from_here: bool = False):
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

        if self.api.target_chapter_id:
            target_id_str = str(self.api.target_chapter_id)
            matching = [c for c in deduped if str(c.get("id")) == target_id_str or str(c.get("hid")) == target_id_str]
            if matching:
                target_ch = matching[0]
                if self.from_here:
                    t_num = target_ch.get("number", 0)
                    deduped = [c for c in deduped if c.get("number", 0) >= t_num]
                    print(f"[*] Downloading from Chapter {t_num} onwards ({len(deduped)} chapters).")
                else:
                    deduped = [target_ch]
                    print(f"[*] Downloading targeted Chapter {target_ch.get('number')} only.")
            else:
                print(f"[!] Warning: Target chapter ID {target_id_str} not found in chapter list.")

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

    @classmethod
    def search(
        cls,
        keyword: str = "",
        limit: int = 10,
        manga_type: str = None,
        status: str = None,
        sort: str = None,
        genres: list = None,
        demographics: list = None,
        interactive: bool = True,
        cookie_file: str = None,
        downloader_options: dict = None
    ):
        """Search Comix.to titles with optional filters and interactive selection."""
        from .cookies import find_default_cookies, parse_cookie_file
        from .utils import print_manga_table

        c_file = cookie_file or find_default_cookies()
        c_header = parse_cookie_file(c_file) if c_file else ""
        api = ComixAPI("", cookie_header=c_header)
        try:
            query_desc = f"'{keyword}'" if keyword else "all titles"
            filter_descs = []
            if manga_type:
                filter_descs.append(f"type={manga_type}")
            if status:
                filter_descs.append(f"status={status}")
            if genres:
                filter_descs.append(f"genres={genres}")
            if demographics:
                filter_descs.append(f"demographics={demographics}")
            if sort:
                filter_descs.append(f"sort={sort}")
            filter_str = f" [{', '.join(filter_descs)}]" if filter_descs else ""

            print(f"[*] Searching Comix.to for {query_desc}{filter_str}...")
            results = api.search_titles(
                keyword=keyword,
                limit=limit,
                manga_type=manga_type,
                status=status,
                sort=sort,
                genres=genres,
                demographics=demographics
            )
            if not results:
                print(f"[!] No results found for {query_desc}{filter_str}.")
                return None

            print_manga_table(results)

            if not interactive:
                return results

            while True:
                choice = input(f"\n[?] Enter number to download (1-{len(results)}) or 'q' to cancel: ").strip()
                if choice.lower() in ("q", "quit", "exit"):
                    print("[*] Cancelled.")
                    return None
                if choice.isdigit() and 1 <= int(choice) <= len(results):
                    selected = results[int(choice) - 1]
                    title_url = selected.get("url") or f"/title/{selected.get('hid')}"
                    print(f"\n[*] Selected: {selected.get('title')} ({title_url})")

                    opts = downloader_options.copy() if downloader_options else {}
                    opts["cookie_file"] = c_file
                    chapter_range = opts.pop("chapter_range", "all")
                    downloader = cls(target_url=title_url, **opts)
                    downloader.run(chapter_range=chapter_range)
                    return downloader
                else:
                    print(f"[!] Invalid selection. Please enter 1 to {len(results)} or 'q'.")
        finally:
            api.close()

    def list_groups(self):
        """Display all scanlation groups that contributed to this title."""
        try:
            self.api.bootstrap()
            groups = self.api.get_manga_groups()
            if not groups:
                print(f"[*] No specific group metadata found for {self.api.manga_title}.")
                return
            print(f"\n[*] Available scanlation groups for '{self.api.manga_title}':")
            for g in groups:
                name = g.get("name") or g.get("title") or "Unknown"
                gid = g.get("id")
                slug = g.get("slug", "")
                print(f"  • {name} (ID: {gid}, Slug: {slug})")
            print(f"\nTip: Download with a specific group using: -g \"{groups[0].get('name')}\"\n")
        finally:
            self.api.close()

    @classmethod
    def trending(
        cls,
        trend_type: str = "trending",
        days: int = 1,
        limit: int = 10,
        interactive: bool = True,
        cookie_file: str = None,
        downloader_options: dict = None
    ):
        """Fetch and display trending/top titles on Comix.to with interactive download selection."""
        from .cookies import find_default_cookies, parse_cookie_file
        from .utils import print_manga_table

        c_file = cookie_file or find_default_cookies()
        c_header = parse_cookie_file(c_file) if c_file else ""
        api = ComixAPI("", cookie_header=c_header)
        try:
            period_str = "Today" if days == 1 else f"Past {days} Days"
            type_label = "Trending" if trend_type == "trending" else "Most Followed"
            print(f"[*] Fetching {type_label} titles ({period_str}, limit: {limit})...")

            results = api.get_top_titles(type_filter=trend_type, days=days, limit=limit)
            if not results:
                print(f"[!] No {trend_type} titles found.")
                return None

            print_manga_table(results, title=f"🔥 Comix.to {type_label} ({period_str})")

            if not interactive:
                return results

            while True:
                choice = input(f"\n[?] Enter number to download (1-{len(results)}) or 'q' to cancel: ").strip()
                if choice.lower() in ("q", "quit", "exit"):
                    print("[*] Cancelled.")
                    return None
                if choice.isdigit() and 1 <= int(choice) <= len(results):
                    selected = results[int(choice) - 1]
                    title_url = selected.get("url") or f"/title/{selected.get('hid')}"
                    print(f"\n[*] Selected: {selected.get('title')} ({title_url})")

                    opts = downloader_options.copy() if downloader_options else {}
                    opts["cookie_file"] = c_file
                    chapter_range = opts.pop("chapter_range", "all")
                    downloader = cls(target_url=title_url, **opts)
                    downloader.run(chapter_range=chapter_range)
                    return downloader
                else:
                    print(f"[!] Invalid selection. Please enter 1 to {len(results)} or 'q'.")
        finally:
            api.close()
