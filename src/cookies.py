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


def resolve_cookies(cookie_override: str = "") -> str:
    """Resolve cookie header string from override, env vars (COMIX_COOKIE / COMIX_COOKIES), or file."""
    if cookie_override and cookie_override.strip():
        return cookie_override.strip()
    env_cookie = os.environ.get("COMIX_COOKIE") or os.environ.get("COMIX_COOKIES")
    if env_cookie and env_cookie.strip():
        return env_cookie.strip()
    default_path = find_default_cookies()
    if default_path:
        return parse_cookie_file(default_path)
    return ""


def test_cookies(cookie_header: str = "") -> dict:
    """Test if the provided or discovered cookies bypass Cloudflare and can access Comix.to."""
    import urllib.request
    import urllib.error

    resolved = resolve_cookies(cookie_header)
    url = "https://comix.to"
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
    }
    if resolved:
        headers["Cookie"] = resolved

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="ignore")
            has_cfg = 'name="cfg"' in body or "initial-data" in body
            return {
                "success": status == 200 and has_cfg,
                "status_code": status,
                "has_cfg_token": has_cfg,
                "cookie_length": len(resolved),
                "message": "Cookies are valid! Cloudflare bypassed successfully." if (status == 200 and has_cfg) else f"Connected (HTTP {status}), but session token missing."
            }
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {
                "success": False,
                "status_code": 403,
                "cookie_length": len(resolved),
                "message": "HTTP 403 Forbidden: Cloudflare challenge required. Cookies are missing or expired."
            }
        return {
            "success": False,
            "status_code": e.code,
            "cookie_length": len(resolved),
            "message": f"HTTP Error {e.code}: {e.reason}"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "cookie_length": len(resolved),
            "message": f"Connection error: {str(e)}"
        }


if __name__ == "__main__":
    import sys

    print("=" * 65)
    print("🍪 COMIX.TO COOKIE INSPECTOR & VALIDATOR")
    print("=" * 65)

    target_file = sys.argv[1] if len(sys.argv) > 1 else find_default_cookies()
    if target_file and os.path.exists(target_file):
        print(f"[*] Cookie File Found: {target_file}")
        cookie_data = parse_cookie_file(target_file)
        has_cf = "cf_clearance" in cookie_data
        has_session = "session" in cookie_data
        has_remember = "remember_web" in cookie_data
        print(f"[*] Cookie Length:     {len(cookie_data)} chars")
        print(f"[*] Key Cookies Found: cf_clearance={has_cf}, session={has_session}, remember_web={has_remember}")
    else:
        print("[!] No cookie file found at default locations (comix.to_cookies.txt, cookies.txt)")
        cookie_data = resolve_cookies()

    print("[*] Testing live connection to https://comix.to ...")
    res = test_cookies(cookie_data)
    if res["success"]:
        print(f"\n✅ SUCCESS: {res['message']} (HTTP {res['status_code']})")
    else:
        print(f"\n❌ FAILED: {res['message']} (HTTP {res['status_code']})")
        print("\n💡 HOW TO REFRESH COOKIES:")
        print("1. Open Chrome/Firefox and navigate to https://comix.to")
        print("2. Log in and complete the Cloudflare Turnstile challenge if prompted.")
        print("3. Use a browser extension like 'Get cookies.txt LOCALLY' or export cookies as Netscape format.")
        print("4. Save the file as 'comix.to_cookies.txt' in this directory:")
        print(f"   {Path.cwd() / 'comix.to_cookies.txt'}")
        print("5. Or set environment variable:")
        print("   $env:COMIX_COOKIE=\"cf_clearance=...; session=...\"")
    print("=" * 65)
