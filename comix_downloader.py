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

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import ComixDownloader


def main():
    parser = argparse.ArgumentParser(
        description="Unofficial Comix.to Manga / Manhwa PDF Downloader & Search Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
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

  # List all scanlation groups for a title
  python comix_downloader.py https://comix.to/title/<slug> --list-groups
        """
    )
    parser.add_argument("target", nargs="?", default=None, help="Comic title URL / slug, or 'search' / 'trending' command")
    parser.add_argument("search_query", nargs="?", default=None, help="Search query when using 'search' command")

    # Search & Discovery options
    parser.add_argument("-s", "--search", dest="search_flag", help="Search keyword (alternative to 'search <query>')")
    parser.add_argument("--trending", dest="trending_flag", action="store_true", help="Browse trending titles (alternative to 'trending' command)")
    parser.add_argument("--days", type=int, choices=[1, 7, 30], default=1, help="Time window for trending/top titles in days: 1, 7, or 30 (default: 1)")
    parser.add_argument("--trend-type", choices=["trending", "follows"], default="trending", help="Trending discovery mode: 'trending' or 'follows' (default: 'trending')")
    parser.add_argument("--type", help="Filter search by comic type (manga, manhwa, manhua, other)")
    parser.add_argument("--status", help="Filter search by status (releasing, finished, on_hiatus, discontinued)")
    parser.add_argument("--genre", "--genres", dest="genres", help="Filter by genre(s), e.g. 'Action', 'fantasy', or 'action,adventure'")
    parser.add_argument("--demographic", "--demographics", dest="demographics", help="Filter by demographic(s), e.g. 'shounen', 'seinen', 'shoujo', 'josei'")
    parser.add_argument("--sort", help="Sort order (e.g. 'views_7d:desc', 'chapter_updated_at:desc', 'score:desc')")
    parser.add_argument("--limit", type=int, default=10, help="Number of search/trending results to return (default: 10)")
    parser.add_argument("--no-interactive", action="store_true", help="Print results without interactive prompt")

    # Chapter & Group filtering
    parser.add_argument("-o", "--output", help="Directory to save downloaded PDFs (default: ./downloads/{Title})")
    parser.add_argument("-c", "--chapters", default="all", help="Chapters to download (e.g. '1-5', '1,3,5-10', '20+', or 'all')")
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

    args = parser.parse_args()

    # Route: Trending / Top command or flag
    is_trending_cmd = (args.target and args.target.lower() in ("trending", "top")) or bool(args.trending_flag)
    if is_trending_cmd:
        trend_mode = args.trend_type
        if args.type and args.type.lower() in ("trending", "follows"):
            trend_mode = args.type.lower()

        ComixDownloader.trending(
            trend_type=trend_mode,
            days=args.days,
            limit=args.limit,
            interactive=not args.no_interactive,
            cookie_file=args.cookies,
            downloader_options={
                "output_dir": args.output,
                "concurrency": args.threads,
                "preferred_group": args.group,
                "lang": args.lang,
                "merge_all": args.merge,
                "keep_images": args.keep_images,
                "use_aria2": args.use_aria2,
                "from_here": args.from_here,
                "chapter_range": args.chapters
            }
        )
        return

    # Route: Search command or search flag
    is_search_cmd = (args.target and args.target.lower() == "search") or bool(args.search_flag)
    if is_search_cmd:
        keyword = args.search_flag if args.search_flag else (args.search_query or "")
        has_filters = bool(args.type or args.status or args.genres or args.demographics or args.sort)
        if not keyword and not has_filters:
            print("[!] Please provide a search query or filter: python comix_downloader.py search \"<keyword>\"")
            sys.exit(1)

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
            downloader_options={
                "output_dir": args.output,
                "concurrency": args.threads,
                "preferred_group": args.group,
                "lang": args.lang,
                "merge_all": args.merge,
                "keep_images": args.keep_images,
                "use_aria2": args.use_aria2,
                "from_here": args.from_here,
                "chapter_range": args.chapters
            }
        )
        return

    # Route: Direct Title / Chapter URL
    if args.target:
        downloader = ComixDownloader(
            target_url=args.target,
            output_dir=args.output,
            cookie_file=args.cookies,
            concurrency=args.threads,
            preferred_group=args.group,
            lang=args.lang,
            merge_all=args.merge,
            keep_images=args.keep_images,
            use_aria2=args.use_aria2,
            from_here=args.from_here
        )
        if args.list_groups:
            downloader.list_groups()
        else:
            downloader.run(chapter_range=args.chapters)
        return

    # No arguments provided
    parser.print_help()


if __name__ == "__main__":
    main()
