#!/usr/bin/env python3
"""
Unofficial Comix.to PDF Downloader & Search Tool
Search, browse, and download entire manga / manhwa series or chapters with client security emulation.

Usage:
  # Search Comix.to and pick interactively
  python comix_downloader.py search "Solo Leveling"
  python comix_downloader.py search "Leveling" --type manhwa --status finished --sort views_7d:desc

  # Download from title URL
  python comix_downloader.py https://comix.to/title/<title-id-or-slug>
"""

import sys
import argparse
from pathlib import Path

# Force UTF-8 on Windows stdout/stderr if possible
if sys.platform == "win32":
    try:
        if sys.stdout and hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if sys.stderr and hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import ComixDownloader


def main():
    parser = argparse.ArgumentParser(
        description="Unofficial Comix.to Manga / Manhwa PDF Downloader & Search Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Account & Library management (requires cookies)
  python comix_downloader.py sync
  python comix_downloader.py --sync
  python comix_downloader.py --export-bookmarks mal
  python comix_downloader.py --export-bookmarks anilist
  python comix_downloader.py following

  # Discover trending / top manhwa and manga
  python comix_downloader.py trending --limit 10
  python comix_downloader.py trending --days 7 --limit 10
  python comix_downloader.py trending --trend-type follows --days 7

  # Search Comix.to and pick interactively to download
  python comix_downloader.py search "Solo Leveling"
  python comix_downloader.py search "Leveling" --type manhwa --status finished --sort views_7d:desc

  # Download all chapters as individual PDFs
  python comix_downloader.py https://comix.to/title/<title-id-or-slug>

  # Download specific chapters and merge into one single volume
  python comix_downloader.py https://comix.to/title/<title-id-or-slug> -c 1-5 --merge

  # Download starting from a specific chapter URL onwards
  python comix_downloader.py https://comix.to/title/<slug>/<chapterId>-chapter-10 --from-here

  # Download curated collections and reading lists
  python comix_downloader.py collection <collection-id-or-url>
  python comix_downloader.py collection 123 --dry-run

  # List all scanlation groups for a title
  python comix_downloader.py groups <title-slug-or-url>
  python comix_downloader.py https://comix.to/title/<slug> --list-groups
        """
    )
    parser.add_argument("target", nargs="?", default=None, help="Comic title URL / slug, or 'search', 'trending', 'collection', 'groups', 'sync', 'export', 'following', 'history' command")
    parser.add_argument("search_query", nargs="*", default=[], help="Search query, collection target, or format when using commands")

    # Curated Collections options
    parser.add_argument("--collection", dest="collection_flag", help="Curated collection URL or ID to batch download")

    # Account & Library options
    parser.add_argument("--sync", dest="sync_flag", action="store_true", help="Sync reading list: check followed titles and download new/missing chapters")
    parser.add_argument("--export-bookmarks", dest="export_bookmarks", nargs="?", const="mal", help="Export Comix.to bookmarks to MAL, AniList, CSV, or JSON (default: mal)")
    parser.add_argument("--dry-run", action="store_true", help="When syncing or downloading collections, preview items without actually downloading")
    parser.add_argument("--unread-only", action="store_true", help="When syncing reading list, only download unread chapters released after your last read chapter")
    parser.add_argument("--folder", help="Filter followed reading list by folder (reading, completed, paused, dropped, planning)")
    parser.add_argument("--history", dest="history_flag", action="store_true", help="View recently read titles from account history")

    # Search & Discovery options
    parser.add_argument("-s", "--search", dest="search_flag", help="Search keyword (alternative to 'search <query>')")
    parser.add_argument("--trending", dest="trending_flag", action="store_true", help="Browse trending titles (alternative to 'trending' command)")
    parser.add_argument("--days", type=int, choices=[1, 7, 30], default=1, help="Time window for trending/top titles in days: 1, 7, or 30 (default: 1)")
    parser.add_argument("--trend-type", choices=["trending", "follows"], default="trending", help="Trending discovery mode: 'trending' or 'follows' (default: 'trending')")
    parser.add_argument("--auto-download", "--download-all", dest="auto_download", action="store_true", help="Automatically batch download all trending titles")
    parser.add_argument("--type", help="Filter search by comic type (manga, manhwa, manhua, other)")
    parser.add_argument("--status", help="Filter search by status (releasing, finished, on_hiatus, discontinued)")
    parser.add_argument("--genre", "--genres", dest="genres", help="Filter by genre(s), e.g. 'Action', 'fantasy', or 'action,adventure'")
    parser.add_argument("--demographic", "--demographics", dest="demographics", help="Filter by demographic(s), e.g. 'shounen', 'seinen', 'shoujo', 'josei'")
    parser.add_argument("--sort", help="Sort order (e.g. 'views_7d:desc', 'chapter_updated_at:desc', 'score:desc')")
    parser.add_argument("--limit", type=int, default=10, help="Number of search/trending results to return (default: 10)")
    parser.add_argument("--no-interactive", action="store_true", help="Print results without interactive prompt")

    # Chapter & Group filtering
    parser.add_argument("-o", "--output", help="Directory to save downloaded PDFs (default: ./downloads/{Title})")
    parser.add_argument("-c", "--chapters", default=None, help="Chapters to download (e.g. '1-5', '1,3,5-10', 'latest', '20+', or 'all')")
    parser.add_argument("-g", "--group", help="Filter by scanlation group name or ID (e.g. 'OmegaScans')")
    parser.add_argument("-l", "--lang", default="en", help="Language filter (default: 'en')")
    parser.add_argument("--list-groups", action="store_true", help="List all available scanlation groups for the title")
    parser.add_argument("--from-here", action="store_true", help="When a chapter URL is provided, download all chapters from that chapter onwards")

    # Downloader options
    parser.add_argument("-m", "--merge", action="store_true", help="Merge all downloaded chapters into a single complete volume PDF")
    parser.add_argument("--cookies", help="Path to Netscape or key=value cookies file (default: comix.to_cookies.txt)")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Number of concurrent image download threads (default: 8)")
    parser.add_argument("--aria2", dest="use_aria2", action="store_true", default=None, help="Force use aria2c for accelerated downloading")
    parser.add_argument("--no-aria2", dest="use_aria2", action="store_false", help="Disable aria2c and use standard Python threads")
    parser.add_argument("--keep-images", action="store_true", help="Keep raw downloaded image files instead of deleting after PDF creation")

    # Cover & Metadata options
    parser.add_argument("--cover", dest="include_cover", action="store_true", default=True, help="Download official cover art as cover.jpg and embed in PDF (default: True)")
    parser.add_argument("--no-cover", dest="include_cover", action="store_false", help="Disable downloading and embedding cover art")
    parser.add_argument("--cover-first", action="store_true", help="Insert cover art as the first page of every chapter PDF")
    parser.add_argument("--no-comicinfo", dest="generate_comicinfo", action="store_false", default=True, help="Disable generating ComicInfo.xml metadata file")

    args = parser.parse_args()

    common_downloader_opts = {
        "output_dir": args.output,
        "concurrency": args.threads,
        "preferred_group": args.group,
        "lang": args.lang,
        "merge_all": args.merge,
        "keep_images": args.keep_images,
        "use_aria2": args.use_aria2,
        "include_cover": args.include_cover,
        "cover_first": args.cover_first,
        "generate_comicinfo": args.generate_comicinfo,
    }

    # Route: Sync library command or flag
    is_sync_cmd = (args.target and args.target.lower() in ("sync", "update-library")) or bool(args.sync_flag)
    if is_sync_cmd:
        ComixDownloader.sync_library(
            folder=args.folder,
            unread_only=args.unread_only,
            limit=args.limit if (args.limit != 10 or args.target == "sync") else None,
            cookie_file=args.cookies,
            dry_run=args.dry_run,
            downloader_options=common_downloader_opts
        )
        return

    # Route: Export bookmarks command or flag
    is_export_cmd = (args.target and args.target.lower() in ("export", "export-bookmarks")) or bool(args.export_bookmarks)
    if is_export_cmd:
        fmt_arg = args.search_query[0] if (isinstance(args.search_query, list) and args.search_query) else (args.search_query or "mal")
        fmt = args.export_bookmarks if args.export_bookmarks else fmt_arg
        ComixDownloader.export_bookmarks(
            format_type=fmt,
            output_file=args.output,
            cookie_file=args.cookies
        )
        return

    # Route: List followed titles / library
    is_following_cmd = (args.target and args.target.lower() in ("following", "library", "bookmarks"))
    if is_following_cmd:
        opts = common_downloader_opts.copy()
        opts["chapter_range"] = args.chapters
        ComixDownloader.list_following(
            folder=args.folder,
            interactive=not args.no_interactive,
            cookie_file=args.cookies,
            downloader_options=opts
        )
        return

    # Route: List reading history
    is_history_cmd = (args.target and args.target.lower() in ("history", "recent", "recently-read")) or bool(args.history_flag)
    if is_history_cmd:
        opts = common_downloader_opts.copy()
        opts["chapter_range"] = args.chapters
        ComixDownloader.list_history(
            limit=args.limit,
            interactive=not args.no_interactive,
            cookie_file=args.cookies,
            downloader_options=opts
        )
        return

    # Route: Trending / Top command or flag
    is_trending_cmd = (args.target and args.target.lower() in ("trending", "top")) or bool(args.trending_flag)
    if is_trending_cmd:
        trend_mode = args.trend_type
        if args.type and args.type.lower() in ("trending", "follows"):
            trend_mode = args.type.lower()

        opts = common_downloader_opts.copy()
        opts["from_here"] = args.from_here
        opts["chapter_range"] = args.chapters
        ComixDownloader.trending(
            trend_type=trend_mode,
            days=args.days,
            limit=args.limit,
            interactive=not args.no_interactive,
            auto_download=args.auto_download,
            cookie_file=args.cookies,
            downloader_options=opts
        )
        return

    # Route: Search command or search flag
    is_search_cmd = (args.target and args.target.lower() == "search") or bool(args.search_flag)
    if is_search_cmd:
        if args.search_flag:
            keyword = args.search_flag
        elif isinstance(args.search_query, list):
            keyword = " ".join(args.search_query).strip()
        else:
            keyword = (args.search_query or "").strip()

        has_filters = bool(args.type or args.status or args.genres or args.demographics or args.sort)
        if not keyword and not has_filters:
            print("[!] Please provide a search query or filter: python comix_downloader.py search \"<keyword>\"")
            sys.exit(1)

        opts = common_downloader_opts.copy()
        opts["from_here"] = args.from_here
        opts["chapter_range"] = args.chapters
        ComixDownloader.search(
            keyword=keyword,
            limit=args.limit,
            manga_type=args.type,
            status=args.status,
            genres=args.genres,
            demographics=args.demographics,
            sort=args.sort,
            interactive=not args.no_interactive,
            cookie_file=args.cookies,
            downloader_options=opts
        )
        return

    # Route: List groups command
    is_groups_cmd = (args.target and args.target.lower() in ("groups", "list-groups"))
    if is_groups_cmd:
        target_manga = args.search_query[0] if (isinstance(args.search_query, list) and args.search_query) else (args.search_query or "")
        if not target_manga:
            print("[!] Please provide a manga URL or slug: python comix_downloader.py groups <manga-url-or-slug>")
            sys.exit(1)
        downloader = ComixDownloader(
            target_url=target_manga,
            cookie_file=args.cookies,
            **common_downloader_opts
        )
        downloader.list_groups()
        return

    # Route: Curated Collection / Reading List command or URL
    is_collection_cmd = (
        (args.target and args.target.lower() in ("collection", "collections"))
        or bool(args.collection_flag)
        or (args.target and ("/collection/" in args.target.lower() or "/collections/" in args.target.lower()))
    )
    if is_collection_cmd:
        if args.collection_flag:
            target_col = args.collection_flag
        elif args.target and args.target.lower() in ("collection", "collections"):
            target_col = args.search_query[0] if (isinstance(args.search_query, list) and args.search_query) else (args.search_query or "")
        else:
            target_col = args.target

        if not target_col:
            print("[!] Please provide a collection URL or ID: python comix_downloader.py collection <collection-url-or-id>")
            sys.exit(1)

        opts = common_downloader_opts.copy()
        opts["chapter_range"] = args.chapters
        ComixDownloader.collection(
            collection_target=target_col,
            interactive=not args.no_interactive,
            cookie_file=args.cookies,
            downloader_options=opts,
            dry_run=args.dry_run
        )
        return

    # Route: Direct Title / Chapter URL
    if args.target:
        downloader = ComixDownloader(
            target_url=args.target,
            cookie_file=args.cookies,
            from_here=args.from_here,
            **common_downloader_opts
        )
        if args.list_groups:
            downloader.list_groups()
        else:
            downloader.run(chapter_range=args.chapters or "all")
        return

    # No arguments provided
    parser.print_help()


if __name__ == "__main__":
    main()
