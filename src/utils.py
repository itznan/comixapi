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
