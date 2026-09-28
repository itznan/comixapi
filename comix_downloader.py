#!/usr/bin/env python3
"""
Unofficial Comix.to PDF Downloader
Download entire manga / manhwa / comic series or select chapters in high quality PDF format with just a single link.

Usage:
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
        description="Unofficial Comix.to Manga / Manhwa PDF Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all chapters as individual PDFs
  python comix_downloader.py https://comix.to/title/<title-id-or-slug>

  # Download specific chapters and merge into one single volume
  python comix_downloader.py https://comix.to/title/<title-id-or-slug> -c 1-5 --merge

  # Specify scanlation group and custom output folder
  python comix_downloader.py https://comix.to/title/<title-id-or-slug> -g <GroupName> -o ./my_folder
        """
    )
    parser.add_argument("url", help="Comic / Manga title URL or slug (e.g. https://comix.to/title/<title-id-or-slug>)")
    parser.add_argument("-o", "--output", help="Directory to save downloaded PDFs (default: ./downloads/{Title})")
    parser.add_argument("-c", "--chapters", default="all", help="Chapters to download (e.g. '1-5', '1,3,5-10', '20+', or 'all')")
    parser.add_argument("-g", "--group", help="Filter by scanlation group name or ID (e.g. 'OmegaScans')")
    parser.add_argument("-l", "--lang", default="en", help="Language filter (default: 'en')")
    parser.add_argument("-m", "--merge", action="store_true", help="Merge all downloaded chapters into a single complete volume PDF")
    parser.add_argument("--cookies", help="Path to Netscape or key=value cookies file (default: comix.to_cookies.txt)")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Number of concurrent image download threads (default: 8)")
    parser.add_argument("--aria2", dest="use_aria2", action="store_true", default=None, help="Force use aria2c for accelerated downloading")
    parser.add_argument("--no-aria2", dest="use_aria2", action="store_false", help="Disable aria2c and use standard Python threads")
    parser.add_argument("--keep-images", action="store_true", help="Keep raw downloaded image files instead of deleting after PDF creation")

    args = parser.parse_args()

    downloader = ComixDownloader(
        target_url=args.url,
        output_dir=args.output,
        cookie_file=args.cookies,
        concurrency=args.threads,
        preferred_group=args.group,
        lang=args.lang,
        merge_all=args.merge,
        keep_images=args.keep_images,
        use_aria2=args.use_aria2
    )
    downloader.run(chapter_range=args.chapters)


if __name__ == "__main__":
    main()
