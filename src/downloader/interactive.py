"""
Interactive search, trending discovery, and terminal prompt workflows for the downloader.
"""

from ..cookies import find_default_cookies, parse_cookie_file
from ..utils import print_manga_table
from ..api import ComixAPI


class InteractiveSearchMixin:
    """Mixin providing interactive search and trending CLI workflows for ComixDownloader."""

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
