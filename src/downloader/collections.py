"""
Curated collection downloader: batch-download every series in a user's collection or reading list.
"""

from pathlib import Path
from ..cookies import find_default_cookies, parse_cookie_file
from ..utils import sanitize_filename, print_manga_table, parse_chapter_spec
from ..api import ComixAPI


class CollectionDownloaderMixin:
    """Mixin providing curated collection batch-download and management workflows."""

    @classmethod
    def collection(
        cls,
        collection_target: str,
        interactive: bool = True,
        cookie_file: str = None,
        downloader_options: dict = None,
        dry_run: bool = False
    ):
        """Batch-download or interactively select titles from a Comix.to curated collection."""
        c_file = cookie_file or find_default_cookies()
        c_header = parse_cookie_file(c_file) if c_file else ""
        api = ComixAPI("", cookie_header=c_header)

        try:
            cid = api.parse_collection_id(collection_target)
            if not cid:
                print(f"[!] Invalid collection identifier: '{collection_target}'")
                return None

            print(f"[*] Fetching collection #{cid} from Comix.to...")
            col_meta = api.get_collection(cid)
            col_name = col_meta.get("name") or col_meta.get("title") or f"Collection #{cid}"
            col_desc = col_meta.get("description") or ""

            items = api.get_collection_items(cid)
            if not items:
                print(f"[!] No comic series found in collection #{cid} ({col_name}).")
                return None

            desc_text = f" - {col_desc}" if col_desc else ""
            table_title = f"📂 Collection: {col_name} ({len(items)} series){desc_text}"
            print_manga_table(items, title=table_title)

            selected_items = items
            if interactive:
                print("\n[?] Collection download mode:")
                print(f"  [a] Download ALL series in this collection ({len(items)} series)")
                print(f"  [1-{len(items)}] Select series numbers to download (e.g. '1', '1,3,5', '1-5')")
                print("  [q] Cancel")

                choice = input("\nSelection [default: a]: ").strip()
                if choice.lower() in ("q", "quit", "exit", "cancel"):
                    print("[*] Cancelled.")
                    return None

                if choice and choice.lower() not in ("a", "all"):
                    selected_indexes = parse_chapter_spec(choice)
                    selected_items = [
                        it for idx, it in enumerate(items, 1)
                        if idx in selected_indexes
                    ]
                    if not selected_items:
                        print("[!] No valid series selected.")
                        return None
                    print(f"[*] Selected {len(selected_items)} out of {len(items)} series.")

            base_opts = downloader_options.copy() if downloader_options else {}
            base_output = Path(base_opts.get("output_dir") or "./downloads")
            chapter_range = base_opts.pop("chapter_range", None) or "all"

            # Destination directory for the collection
            col_dir = base_output / sanitize_filename(col_name)

            print(f"\n[*] Preparing to download {len(selected_items)} series from '{col_name}'...")
            if dry_run:
                print("[*] Dry run mode enabled. Simulating downloads:\n" + "=" * 65)

            successful = 0
            for idx, manga in enumerate(selected_items, 1):
                title = manga.get("title") or "Unknown"
                hid = manga.get("hid")
                url = manga.get("url") or f"/title/{hid}"
                latest_ch = manga.get("latestChapter") or "-"

                print(f"\n[{idx}/{len(selected_items)}] 📚 {title} (ID: {hid}, Latest: Ch {latest_ch})")
                manga_out_dir = col_dir / sanitize_filename(title)

                if dry_run:
                    print(f"    [DRY RUN] Target URL: {url}")
                    print(f"    [DRY RUN] Destination: {manga_out_dir.resolve()}")
                    print(f"    [DRY RUN] Chapter range: {chapter_range}")
                    successful += 1
                    continue

                opts = base_opts.copy()
                opts["output_dir"] = manga_out_dir
                opts["cookie_file"] = c_file

                downloader = cls(target_url=url, **opts)
                try:
                    downloader.run(chapter_range=chapter_range)
                    successful += 1
                except Exception as ex:
                    print(f"    [!] Error downloading '{title}': {ex}")

            mode_str = "simulated" if dry_run else "completed"
            print(f"\n[+] Collection '{col_name}' download finished ({successful}/{len(selected_items)} series {mode_str}).")
            return selected_items

        finally:
            api.close()
