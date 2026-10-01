"""
Library synchronization, followed titles management, and reading list export workflows.
"""

from pathlib import Path
from ..cookies import find_default_cookies, parse_cookie_file
from ..utils import sanitize_filename, print_manga_table
from ..metadata import download_cover, save_comic_info_xml
from ..api import ComixAPI


class SyncMixin:
    """Mixin providing reading list sync, following list, and bookmark export for ComixDownloader."""

    @classmethod
    def list_following(
        cls,
        interactive: bool = True,
        cookie_file: str = None,
        downloader_options: dict = None
    ):
        """Display all bookmarked / followed titles in user's Comix.to account with optional download."""
        c_file = cookie_file or find_default_cookies()
        if not c_file:
            print("[!] Error: No cookies found. To view your library, provide 'comix.to_cookies.txt' with your logged-in session cookies.")
            return None

        c_header = parse_cookie_file(c_file) if c_file else ""
        if not c_header:
            print("[!] Error: Cookies file is empty or invalid.")
            return None

        api = ComixAPI("", cookie_header=c_header)
        try:
            print("[*] Fetching followed titles from your Comix.to account...")
            results = api.get_following_titles()
            if not results:
                print("[*] No bookmarked titles found in your account.")
                return None

            print_manga_table(results, title="📚 My Comix.to Reading List / Bookmarks")

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
                    chapter_range = opts.pop("chapter_range", None)
                    if not chapter_range:
                        ch_choice = input("\n[?] Enter chapters to download (e.g. 'all', '1-5', 'latest', '10+') [default: all]: ").strip()
                        if ch_choice.lower() in ("q", "quit", "cancel"):
                            print("[*] Cancelled.")
                            return None
                        chapter_range = ch_choice if ch_choice else "all"

                    downloader = cls(target_url=title_url, **opts)
                    downloader.run(chapter_range=chapter_range)
                    return downloader
                else:
                    print(f"[!] Invalid selection. Please enter 1 to {len(results)} or 'q'.")
        finally:
            api.close()

    @classmethod
    def sync_library(
        cls,
        cookie_file: str = None,
        downloader_options: dict = None,
        dry_run: bool = False
    ):
        """Check all titles in user's reading list and download new/missing chapters."""
        c_file = cookie_file or find_default_cookies()
        if not c_file:
            print("[!] Error: No cookies found. To sync your library, provide 'comix.to_cookies.txt' with your logged-in session cookies.")
            return

        c_header = parse_cookie_file(c_file) if c_file else ""
        if not c_header:
            print("[!] Error: Cookies file is empty or invalid.")
            return

        api = ComixAPI("", cookie_header=c_header)
        try:
            print("[*] Fetching followed titles from your Comix.to account...")
            following = api.get_following_titles()
            if not following:
                print("[*] No bookmarked titles found in your account.")
                return

            print(f"[+] Found {len(following)} followed titles in your reading list.\n" + "=" * 65)

            base_opts = downloader_options.copy() if downloader_options else {}
            base_output_dir = Path(base_opts.get("output_dir") or "./downloads")
            total_downloaded = 0

            for idx, item in enumerate(following, 1):
                title = item.get("title") or "Unknown"
                hid = item.get("hid")
                url_slug = item.get("url") or f"/title/{hid}"
                pivot = item.get("bookmarkPivot") or {}
                user_ch = pivot.get("userChapter", 0)
                latest_ch = item.get("latestChapter", 0)

                print(f"\n[{idx}/{len(following)}] 📚 {title} (Latest: Ch {latest_ch}, Last Read: Ch {user_ch})")

                manga_dir = base_output_dir / sanitize_filename(title)
                existing_pdfs = list(manga_dir.glob("*.pdf")) if manga_dir.exists() else []

                opts = base_opts.copy()
                opts["output_dir"] = manga_dir
                opts["cookie_file"] = c_file

                downloader = cls(target_url=url_slug, **opts)
                try:
                    downloader.api.bootstrap()
                    raw_chapters = downloader.api.fetch_all_chapters()
                    all_chapters = downloader.filter_and_deduplicate(raw_chapters, "all")
                    if not all_chapters:
                        print(f"    [!] No readable chapters available.")
                        continue

                    # Filter chapters that aren't already downloaded on disk
                    needed_chapters = []
                    for ch in all_chapters:
                        ch_num = ch.get("number", 0)
                        prefix = f"Ch {ch_num:03d}" if isinstance(ch_num, int) else f"Ch {ch_num}"
                        already_has = any(prefix in p.name for p in existing_pdfs)
                        if not already_has:
                            needed_chapters.append(ch)

                    if not needed_chapters:
                        print(f"    ✓ Up to date ({len(existing_pdfs)} chapters present).")
                    else:
                        print(f"    ⬇ {len(needed_chapters)} new/missing chapters to download.")
                        if not dry_run:
                            downloader.output_dir = manga_dir
                            manga_dir.mkdir(parents=True, exist_ok=True)
                            cover_file = manga_dir / "cover.jpg"
                            if not cover_file.exists():
                                download_cover(downloader.api.metadata, cover_file)
                            comicinfo_file = manga_dir / "ComicInfo.xml"
                            if not comicinfo_file.exists():
                                save_comic_info_xml(downloader.api.metadata, comicinfo_file)

                            for ch in needed_chapters:
                                ch_cover = cover_file if (cover_file.exists() and ch.get("number") in (1, 1.0, 0, 0.0)) else None
                                res = downloader.download_chapter(ch, manga_dir, cover_image=ch_cover)
                                if res:
                                    total_downloaded += 1
                            print(f"    ✓ Finished syncing {title}.")
                except Exception as ex:
                    print(f"    [!] Error syncing '{title}': {ex}")
                finally:
                    downloader.api.close()

            print("\n" + "=" * 65)
            print(f"[+] Library synchronization complete! Downloaded {total_downloaded} new chapter PDFs.")
        finally:
            api.close()

    @classmethod
    def export_bookmarks(
        cls,
        format_type: str = "mal",
        output_file: str = None,
        cookie_file: str = None
    ):
        """Export user bookmarks to MAL, AniList, CSV, or JSON format."""
        c_file = cookie_file or find_default_cookies()
        if not c_file:
            print("[!] Error: No cookies found. To export bookmarks, provide 'comix.to_cookies.txt' with your logged-in session cookies.")
            return None

        c_header = parse_cookie_file(c_file) if c_file else ""
        if not c_header:
            print("[!] Error: Cookies file is empty or invalid.")
            return None

        api = ComixAPI("", cookie_header=c_header)
        try:
            fmt = (format_type or "mal").strip().lower()
            print(f"[*] Exporting Comix.to bookmarks in '{fmt.upper()}' format...")
            data = api.export_user_bookmarks(format_type=fmt)
            if not data:
                print(f"[!] Export returned empty data.")
                return None

            if output_file:
                out_path = Path(output_file)
            else:
                ext = "xml" if fmt in ("mal", "myanimelist") else ("json" if fmt in ("anilist", "al", "json") else ("txt" if fmt == "txt" else "csv"))
                out_path = Path(f"comix_bookmarks_{fmt}.{ext}")

            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(data, encoding="utf-8")
            print(f"[+] Successfully exported {len(data)} bytes to {out_path.resolve()}")
            return out_path
        finally:
            api.close()
