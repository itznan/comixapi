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
        if not part or part.lower() in ("all", "latest", "last"):
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            try:
                start = float(start_s.strip())
                end = float(end_s.strip())
                cur = start
                while cur <= end:
                    result.add(int(cur) if cur.is_integer() else cur)
                    cur += 1
            except ValueError:
                pass
        elif part.endswith("+"):
            try:
                start = float(part[:-1].strip())
                for n in range(int(start), 9999):
                    result.add(n)
            except ValueError:
                pass
        else:
            try:
                val = float(part)
                result.add(int(val) if val.is_integer() else val)
            except ValueError:
                pass
    return result


def print_manga_table(items: list, title: str = "🔍 Comix.to Search Results"):
    """Format and display manga list in a beautiful terminal table."""
    if not items:
        print("[!] No titles found.")
        return

    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box

        console = Console()
        term_width = console.width or 80
        show_slug = term_width >= 105

        table = Table(
            title=title,
            box=box.ROUNDED,
            header_style="bold cyan",
            show_lines=False
        )
        table.add_column("#", style="dim", width=3, justify="right")
        table.add_column("Title", style="bold white", min_width=16, max_width=30, overflow="fold")
        table.add_column("ID", style="cyan", width=7, justify="right")
        table.add_column("Type", style="magenta", width=7, justify="center")
        table.add_column("Status", width=9, justify="center")
        table.add_column("Rating", style="yellow", width=7, justify="center")
        table.add_column("Latest Ch", style="green", width=9, justify="right")
        if show_slug:
            table.add_column("Slug", style="dim", min_width=15, max_width=35, overflow="ellipsis")

        for i, item in enumerate(items, 1):
            title_text = item.get("title") or "Unknown"
            m_id = str(item.get("id") or item.get("hid") or "-")
            m_type = (item.get("type") or "manga").upper()
            status = item.get("status") or "unknown"
            status_styled = f"[green]{status}[/green]" if status in ("finished", "completed") else f"[yellow]{status}[/yellow]"
            rating = str(item.get("ratedAvg") or item.get("ratedScore") or "-")
            rating_str = f"★ {rating}" if rating != "-" else "-"
            latest_val = item.get("latestChapter")
            if latest_val is not None:
                latest_ch = f"Ch {latest_val}" if str(latest_val).replace(".", "", 1).isdigit() else str(latest_val)
            else:
                latest_ch = "-"
            url = item.get("url") or f"/title/{item.get('hid', '')}"

            row = [
                str(i),
                title_text,
                m_id,
                m_type,
                status_styled,
                rating_str,
                latest_ch
            ]
            if show_slug:
                row.append(url)
            table.add_row(*row)
        console.print(table)

    except Exception:
        header = f"{'#':<4} {'Title':<28} {'ID':<8} {'Type':<8} {'Status':<10} {'Rating':<7} {'Latest Ch':<10}"
        print("\n" + "=" * len(header))
        print(header)
        print("-" * len(header))
        for i, item in enumerate(items, 1):
            title_text = (item.get("title") or "Unknown")[:26]
            m_id = str(item.get("id") or item.get("hid") or "-")[:7]
            m_type = (item.get("type") or "manga")[:7]
            status = (item.get("status") or "unknown")[:9]
            rating = str(item.get("ratedAvg") or "-")
            latest_val = item.get("latestChapter")
            latest_ch = f"Ch {latest_val}" if latest_val is not None else "-"
            print(f"{i:<4} {title_text:<28} {m_id:<8} {m_type:<8} {status:<10} {rating:<7} {latest_ch:<10}")
        print("=" * len(header) + "\n")

