"""
Comix.to API client handling metadata discovery, chapter queries, and page listing.
"""

import re
import time
import json
from pathlib import Path
from urllib.parse import urlparse, urljoin
import urllib.request
import urllib.error

from .config import USER_AGENT, BASE_URL, API_BASE
from .bridge import NodeSignerBridge


class ComixAPI:
    """Client for fetching and decrypting Comix.to metadata and chapters."""

    def __init__(self, raw_url_or_slug: str, cookie_header: str = ""):
        self.raw_url_or_slug = raw_url_or_slug.strip()
        self.cookie_header = cookie_header
        self.manga_hid = None
        self.manga_slug = None
        self.manga_title = None
        self.cfg_token = None
        self.secure_js_path = None
        self.bridge = None

        self.cache_dir = Path.home() / ".cache" / "comixapi"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _http_get(self, url: str, is_json: bool = False, extra_headers: dict = None, retries: int = 3):
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*" if is_json else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": BASE_URL,
        }
        if self.cookie_header:
            headers["Cookie"] = self.cookie_header
        if is_json:
            headers["X-Requested-With"] = "XMLHttpRequest"
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, headers=headers)
        last_err = None
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = resp.read()
                    if is_json:
                        return json.loads(data.decode("utf-8"))
                    return data.decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        raise last_err or RuntimeError(f"Failed to fetch {url}")

    def parse_comic_url(self) -> str:
        """Extract hid and slug from URL or slug string."""
        url = self.raw_url_or_slug
        if not url.startswith("http"):
            url = f"{BASE_URL}/title/{url}"
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[0] == "title":
            slug_part = parts[1]
        elif len(parts) == 1:
            slug_part = parts[0]
        else:
            slug_part = parts[-1]

        self.manga_hid = slug_part.split("-")[0]
        self.manga_slug = slug_part
        return f"{BASE_URL}/title/{slug_part}"

    def bootstrap(self):
        """Fetch title page HTML, extract CFG token, title, download security bundle, and init bridge."""
        title_url = self.parse_comic_url()
        print(f"[*] Accessing manga page: {title_url}")
        html = self._http_get(title_url)

        # 1. Extract CFG token
        cfg_match = re.search(r'<meta[^>]+name=["\']cfg["\'][^>]+content=["\']([^"\']+)["\']', html) or \
                    re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']cfg["\']', html)
        if not cfg_match:
            raise RuntimeError("Could not find <meta name='cfg'> token. Cloudflare or layout change detected.")
        self.cfg_token = cfg_match.group(1)

        # 2. Extract title
        init_data_match = re.search(r'<script[^>]+id=["\']initial-data["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if init_data_match:
            try:
                init_data = json.loads(init_data_match.group(1))
                queries = init_data.get("queries", {})
                for k, v in queries.items():
                    if isinstance(v, dict) and "title" in v and v.get("hid") == self.manga_hid:
                        self.manga_title = v.get("title")
                        break
            except Exception:
                pass

        if not self.manga_title:
            title_tag = re.search(r'<title>([^<]+)</title>', html)
            self.manga_title = title_tag.group(1).replace(" - Comix", "").strip() if title_tag else self.manga_slug

        print(f"[*] Title: {self.manga_title} (ID: {self.manga_hid})")

        # 3. Locate secure-*.js
        main_js_match = re.search(r'<script[^>]+src=["\']([^"\']+/main-[^"\']+\.js)["\']', html)
        if not main_js_match:
            raise RuntimeError("Could not locate main JS bundle in page.")
        main_js_url = urljoin(title_url, main_js_match.group(1))

        main_js_content = self._http_get(main_js_url)
        sec_match = re.search(r'["\'](\./secure-[^"\']+\.js)["\']', main_js_content)
        if not sec_match:
            raise RuntimeError("Could not find secure-*.js reference in main JS bundle.")

        sec_filename = sec_match.group(1).lstrip("./")
        dist_base = main_js_url.rsplit("/", 1)[0]
        secure_js_url = f"{dist_base}/{sec_filename}"

        cached_sec_file = self.cache_dir / sec_filename
        if not cached_sec_file.exists():
            print(f"[*] Downloading security module: {sec_filename}")
            sec_content = self._http_get(secure_js_url)
            cached_sec_file.write_text(sec_content, encoding="utf-8")
        self.secure_js_path = str(cached_sec_file)

        # 4. Initialize Node Signer Bridge
        root_dir = Path(__file__).resolve().parent.parent
        signer_script = root_dir / "comix_signer.js"
        if not signer_script.exists():
            signer_script = Path(__file__).resolve().parent / "comix_signer.js"
        if not signer_script.exists():
            raise FileNotFoundError(f"Signer bridge script not found at {signer_script}")

        self.bridge = NodeSignerBridge(
            script_path=str(signer_script),
            secure_js_path=self.secure_js_path,
            cfg_token=self.cfg_token,
            manga_id=self.manga_hid
        )

    def fetch_all_chapters(self) -> list:
        """Fetch and decrypt all chapters using API pagination."""
        print(f"[*] Fetching chapters list...")
        all_chapters = []
        page = 1
        limit = 100

        while True:
            url_path = f"/manga/{self.manga_hid}/chapters"
            signed_params = self.bridge.sign(url_path, params={"limit": limit, "page": page})
            qs = "&".join(f"{k}={v}" for k, v in signed_params.items())
            full_url = f"{API_BASE}{url_path}?{qs}"

            encrypted_json = self._http_get(full_url, is_json=True, extra_headers={
                "Referer": f"{BASE_URL}/title/{self.manga_slug}"
            })
            decrypted = self.bridge.decrypt(url_path, encrypted_json)
            items = decrypted.get("items", [])
            if not items:
                break
            all_chapters.extend(items)

            meta = decrypted.get("meta", {})
            last_page = meta.get("lastPage", 1)
            if page >= last_page or not meta.get("hasNext", False):
                break
            page += 1

        print(f"[*] Found {len(all_chapters)} chapter releases across all scanlators/languages.")
        return all_chapters

    def fetch_chapter_pages(self, chapter: dict) -> list:
        """Fetch and decrypt images for a specific chapter."""
        ch_id = str(chapter["id"])
        url_path = f"/chapters/{ch_id}"
        signed_params = self.bridge.sign(url_path, chapter_id=ch_id)
        sig = signed_params.get("_", "")
        full_url = f"{API_BASE}{url_path}?_={sig}"

        ch_url = chapter.get("url", "")
        referer = f"{BASE_URL}{ch_url}" if ch_url else f"{BASE_URL}/title/{self.manga_slug}"

        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": referer})
        decrypted = self.bridge.decrypt(url_path, encrypted, chapter_id=ch_id)

        pages_obj = decrypted.get("pages", {})
        base_url = pages_obj.get("baseUrl", "")
        items = pages_obj.get("items", [])

        img_urls = []
        for p in items:
            raw_url = p.get("url", "")
            if not raw_url:
                continue
            if raw_url.startswith("http"):
                img_urls.append(raw_url)
            else:
                img_urls.append(urljoin(base_url, raw_url))
        return img_urls

    def close(self):
        if self.bridge:
            self.bridge.close()
