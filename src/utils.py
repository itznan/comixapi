"""
General helper functions for comix downloader.
"""

import re
import sys

# Force UTF-8 on Windows stdout if possible
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from tqdm import tqdm
except ImportError:
    class tqdm:
        """Lightweight fallback progress bar when tqdm is not installed."""
        def __init__(self, iterable=None, total=None, desc="", unit="", **kwargs):
            self.iterable = iterable
            self.total = total or (len(iterable) if iterable else 0)
            self.desc = desc
            self.n = 0
            if desc:
                print(f"[{desc}] Total: {self.total}")

        def __iter__(self):
            for item in self.iterable:
                yield item
                self.update(1)

        def update(self, n=1):
            self.n += n
            if self.total:
                sys.stdout.write(f"\r{self.desc}: {self.n}/{self.total}")
                sys.stdout.flush()

        def close(self):
            print()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe filenames across Windows, macOS, Linux."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def parse_chapter_spec(spec: str) -> set:
    """Parse chapter selection string like '1-5', '1,3,7-10', '15+' into a set of numbers."""
    result = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = float(start_s.strip())
            end = float(end_s.strip())
            cur = start
            while cur <= end:
                result.add(int(cur) if cur.is_integer() else cur)
                cur += 1
        elif part.endswith("+"):
            start = float(part[:-1].strip())
            for n in range(int(start), 9999):
                result.add(n)
        else:
            val = float(part)
            result.add(int(val) if val.is_integer() else val)
    return result


def print_manga_table(items: list):
    """Format and display manga list in a beautiful terminal table."""
    if not items:
        print("[!] No titles found.")
        return

    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        table = Table(
            title="🔍 Comix.to Search Results",
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=False
        )
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Title", style="bold white", min_width=22, max_width=42)
        table.add_column("ID", style="cyan", width=8, justify="right")
        table.add_column("Type", style="magenta", width=9)
        table.add_column("Status", width=11)
        table.add_column("Rating", style="yellow", width=8, justify="center")
        table.add_column("Latest Ch", style="green", width=10, justify="right")
        table.add_column("Slug", style="dim", min_width=15)

        for i, item in enumerate(items, 1):
            title = item.get("title") or "Unknown"
            m_id = str(item.get("id") or item.get("hid") or "-")
            m_type = (item.get("type") or "manga").upper()
            status = item.get("status") or "unknown"
            status_styled = f"[green]{status}[/green]" if status in ("finished", "completed") else f"[yellow]{status}[/yellow]"
            rating = str(item.get("ratedAvg") or item.get("ratedScore") or "-")
            rating_str = f"★ {rating}" if rating != "-" else "-"
            latest_ch = str(item.get("latestChapter") if item.get("latestChapter") is not None else "-")
            url = item.get("url") or f"/title/{item.get('hid', '')}"

            table.add_row(
                str(i),
                title,
                m_id,
                m_type,
                status_styled,
                rating_str,
                latest_ch,
                url
            )
        console.print(table)

    except ImportError:
        header = f"{'#':<4} {'Title':<35} {'ID':<8} {'Type':<8} {'Status':<11} {'Rating':<8} {'Latest Ch':<10}"
        print("\n" + "=" * len(header))
        print(header)
        print("-" * len(header))
        for i, item in enumerate(items, 1):
            title = (item.get("title") or "Unknown")[:33]
            m_id = str(item.get("id") or item.get("hid") or "-")[:8]
            m_type = (item.get("type") or "manga")[:7]
            status = (item.get("status") or "unknown")[:10]
            rating = str(item.get("ratedAvg") or "-")
            latest_ch = str(item.get("latestChapter") or "-")
            print(f"{i:<4} {title:<35} {m_id:<8} {m_type:<8} {status:<11} {rating:<8} {latest_ch:<10}")
        print("=" * len(header) + "\n")

