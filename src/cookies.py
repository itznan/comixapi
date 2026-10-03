"""
Cookie management and auto-discovery utilities for Comix.to.
"""

import os
from pathlib import Path


def parse_cookie_file(cookie_path: str) -> str:
    """Parse Netscape format cookie file or standard key=value cookie file into Cookie header string."""
    if not cookie_path or not os.path.exists(cookie_path):
        return ""
    cookies = []
    with open(cookie_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                cookies.append(f"{parts[5]}={parts[6]}")
            elif "=" in line:
                cookies.append(line)
    return "; ".join(cookies)


def find_default_cookies() -> str:
    """Search for comix.to_cookies.txt or cookies.txt in common project and working locations, or COOKIE_FILE env var."""
    env_cookie = os.environ.get("COOKIE_FILE")
    if env_cookie and Path(env_cookie).is_file():
        return str(Path(env_cookie).resolve())

    cwd = Path.cwd()
    root_dir = Path(__file__).resolve().parent.parent
    candidates = [
        cwd / "comix.to_cookies.txt",
        root_dir / "comix.to_cookies.txt",
        cwd / "cookies.txt",
        root_dir / "cookies.txt",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return ""
