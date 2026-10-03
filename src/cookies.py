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


def test_cookies(cookie_header: str = "", user_agent: str = "") -> dict:
    """Test if the provided or discovered cookies bypass Cloudflare and can access Comix.to."""
    try:
        from .config import USER_AGENT, BASE_URL
    except (ImportError, ValueError):
        import sys
        root = str(Path(__file__).resolve().parent.parent)
        if root not in sys.path:
            sys.path.insert(0, root)
        from src.config import USER_AGENT, BASE_URL

    try:
        from curl_cffi import requests as cffi_requests
        has_cffi = True
    except ImportError:
        cffi_requests = None
        has_cffi = False

    import urllib.request
    import urllib.error

    resolved = resolve_cookies(cookie_header)
    ua = user_agent.strip() if user_agent and user_agent.strip() else (os.environ.get("USER_AGENT") or USER_AGENT)
    url = BASE_URL

    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": url,
    }

    # Parse cookie string into key-value dict for native curl-impersonate HTTP/2 handling
    cookie_dict = (
        {k.strip(): v.strip() for k, v in [c.split("=", 1) for c in resolved.split("; ") if "=" in c]}
        if resolved else None
    )

    # 1. Try with curl_cffi browser impersonation
    if has_cffi and cffi_requests:
        try:
            resp = cffi_requests.get(
                url,
                headers=headers,
                cookies=cookie_dict,
                impersonate="chrome",
                timeout=15,
                allow_redirects=True
            )
            body = resp.text
            has_cfg = 'name="cfg"' in body or "initial-data" in body
            success = resp.status_code == 200 and has_cfg
            msg = (
                "Cookies are valid! Cloudflare bypassed successfully."
                if success
                else (
                    "HTTP 403 Forbidden: Cloudflare challenge required. Cookies are missing or expired."
                    if resp.status_code == 403
                    else f"Connected (HTTP {resp.status_code}), but session token missing."
                )
            )
            return {
                "success": success,
                "status_code": resp.status_code,
                "has_cfg_token": has_cfg,
                "cookie_length": len(resolved),
                "transport": "curl_cffi (impersonate=chrome)",
                "user_agent": ua,
                "message": msg
            }
        except Exception:
            pass

    # 2. Fallback to urllib.request
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
                "transport": "urllib",
                "user_agent": ua,
                "message": "Cookies are valid! Cloudflare bypassed successfully." if (status == 200 and has_cfg) else f"Connected (HTTP {status}), but session token missing."
            }
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {
                "success": False,
                "status_code": 403,
                "cookie_length": len(resolved),
                "transport": "urllib",
                "user_agent": ua,
                "message": "HTTP 403 Forbidden: Cloudflare challenge required. Cookies are missing or expired."
            }
        return {
            "success": False,
            "status_code": e.code,
            "cookie_length": len(resolved),
            "transport": "urllib",
            "user_agent": ua,
            "message": f"HTTP Error {e.code}: {e.reason}"
        }
    except Exception as e:
        return {
            "success": False,
            "status_code": None,
            "cookie_length": len(resolved),
            "transport": "urllib",
            "user_agent": ua,
            "message": f"Connection error: {str(e)}"
        }


if __name__ == "__main__":
    import sys
    import argparse

    # Ensure UTF-8 stdout/stderr on Windows cmd/powershell
    if sys.platform == "win32":
        try:
            if sys.stdout and hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if sys.stderr and hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Ensure project root in sys.path
    root_dir = str(Path(__file__).resolve().parent.parent)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    parser = argparse.ArgumentParser(description="Comix.to Cookie & Cloudflare Bypass Inspector")
    parser.add_argument("cookie_file", nargs="?", default=None, help="Path to cookie file (optional)")
    parser.add_argument("--ua", "--user-agent", dest="user_agent", default="", help="Exact User-Agent string from Chrome (navigator.userAgent)")
    args = parser.parse_args()

    print("=" * 65)
    print("🍪 COMIX.TO COOKIE INSPECTOR & VALIDATOR")
    print("=" * 65)

    target_file = args.cookie_file if args.cookie_file else find_default_cookies()
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

    active_ua = args.user_agent or os.environ.get("USER_AGENT") or "Chrome (Default Config)"
    print(f"[*] Testing with UA:   {active_ua[:60]}...")
    print("[*] Testing live connection to https://comix.to ...")

    res = test_cookies(cookie_data, user_agent=args.user_agent)
    transport_name = res.get("transport", "standard")
    print(f"[*] Transport Engine:  {transport_name}")

    if res["success"]:
        print(f"\n✅ SUCCESS: {res['message']} (HTTP {res['status_code']})")
    else:
        print(f"\n❌ FAILED: {res['message']} (HTTP {res['status_code']})")
        print("\n💡 HOW TO REFRESH AND MATCH COOKIES:")
        print("1. Open Chrome/Firefox on THIS computer (same network/IP, no VPN mismatch).")
        print("2. Navigate to https://comix.to and let the page load completely.")
        print("3. In Chrome DevTools (F12) Console, run: navigator.userAgent")
        print("4. Export cookies using 'Get cookies.txt LOCALLY' to 'comix.to_cookies.txt'.")
        print("5. Test with your exact browser User-Agent:")
        print("   python src\\cookies.py --ua \"<paste your navigator.userAgent>\"")
        print("   Or set environment variable:")
        print("   $env:USER_AGENT=\"<paste your navigator.userAgent>\"")
    print("=" * 65)
