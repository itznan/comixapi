"""
Core HTTP client, session bootstrap, CFG token extraction, and URL parser for Comix.to.
"""

import re
import json
import time
from pathlib import Path
from urllib.parse import urlparse, urljoin
import urllib.request

from ..config import USER_AGENT, BASE_URL
from ..bridge import NodeSignerBridge
from .chapters import ChapterMixin
from .search import SearchMixin
from .user import UserMixin


class ComixAPI(ChapterMixin, SearchMixin, UserMixin):
    """Client for fetching and decrypting Comix.to metadata and chapters."""

    def __init__(self, raw_url_or_slug: str = "", cookie_header: str = ""):
        self.raw_url_or_slug = raw_url_or_slug.strip() if raw_url_or_slug else ""
        self.cookie_header = cookie_header
        self.manga_hid = None
        self.manga_slug = None
        self.manga_title = None
        self.target_chapter_id = None
        self.target_chapter_num = None
        self.metadata = {}
        self.cfg_token = None
        self.secure_js_path = None
        self.bridge = None

        self.cache_dir = Path.home() / ".cache" / "comixapi"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        if self.raw_url_or_slug:
            self.parse_comic_url()

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
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = resp.read()
                    if is_json:
                        return json.loads(data.decode("utf-8"))
                    return data.decode("utf-8", errors="replace")
            except Exception as e:
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        raise last_err or RuntimeError(f"Failed to fetch {url}")

    def parse_comic_url(self) -> str:
        """Extract hid, slug, and optional target chapter id / number from URL or slug string."""
        url = self.raw_url_or_slug
        if not url:
            return BASE_URL

        if not url.startswith("http"):
            if url.startswith("/"):
                url = f"{BASE_URL}{url}"
            else:
                url = f"{BASE_URL}/title/{url}"

        parsed = urlparse(url)
        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]

        slug_part = ""
        chapter_part = ""

        if len(parts) >= 3 and parts[0] == "title":
            slug_part = parts[1]
            chapter_part = parts[2]
        elif len(parts) >= 2 and parts[0] == "title":
            slug_part = parts[1]
        elif len(parts) == 1 and parts[0]:
            slug_part = parts[0]
        elif parts:
            slug_part = parts[-1]

        if chapter_part:
            # Parse chapter_part, e.g. "9567548-chapter-40.6", "k26r-chapter-1", "chapter-10", "ch-5", "9567548"
            m = re.match(r"^([a-zA-Z0-9]+)-(?:chapter|ch)-([\d.]+)", chapter_part, re.IGNORECASE)
            if m:
                self.target_chapter_id = m.group(1)
                try:
                    num_val = float(m.group(2))
                    self.target_chapter_num = int(num_val) if num_val.is_integer() else num_val
                except ValueError:
                    pass
            else:
                m_num = re.match(r"^(?:chapter|ch)-([\d.]+)", chapter_part, re.IGNORECASE)
                if m_num:
                    try:
                        num_val = float(m_num.group(1))
                        self.target_chapter_num = int(num_val) if num_val.is_integer() else num_val
                    except ValueError:
                        pass
                else:
                    id_part = chapter_part.split("-")[0]
                    if id_part:
                        self.target_chapter_id = id_part
                        try:
                            num_val = float(id_part)
                            if num_val < 10000:
                                self.target_chapter_num = int(num_val) if num_val.is_integer() else num_val
                        except ValueError:
                            pass

        if slug_part:
            self.manga_hid = slug_part.split("-")[0]
            self.manga_slug = slug_part
            return f"{BASE_URL}/title/{slug_part}"

        return BASE_URL

    def bootstrap(self):
        """Fetch page HTML, extract CFG token, title, download security bundle, and init bridge."""
        if self.bridge:
            return

        if self.raw_url_or_slug:
            title_url = self.parse_comic_url()
            print(f"[*] Accessing manga page: {title_url}")
            html = self._http_get(title_url)
        else:
            title_url = BASE_URL
            print(f"[*] Initializing Comix.to session: {title_url}")
            html = self._http_get(title_url)

        # 1. Extract CFG token
        cfg_match = re.search(r'<meta[^>]+name=["\']cfg["\'][^>]+content=["\']([^"\']+)["\']', html) or \
                    re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']cfg["\']', html)
        if not cfg_match:
            raise RuntimeError("Could not find <meta name='cfg'> token. Cloudflare or layout change detected.")
        self.cfg_token = cfg_match.group(1)

        # 2. Extract title & rich metadata
        init_data_match = re.search(r'<script[^>]+id=["\']initial-data["\'][^>]*>(.*?)</script>', html, re.DOTALL)
        if init_data_match:
            try:
                init_data = json.loads(init_data_match.group(1))
                queries = init_data.get("queries", {})
                for k, v in queries.items():
                    if isinstance(v, dict) and "title" in v and (not self.manga_hid or v.get("hid") == self.manga_hid):
                        self.metadata = v
                        self.manga_title = v.get("title")
                        if not self.manga_hid:
                            self.manga_hid = v.get("hid")
                            self.manga_slug = f"{self.manga_hid}-{v.get('slug', '')}"
                        break
            except Exception:
                pass

        if not self.manga_title and self.manga_slug:
            title_tag = re.search(r'<title>([^<]+)</title>', html)
            self.manga_title = title_tag.group(1).replace(" - Comix", "").strip() if title_tag else self.manga_slug

        if self.manga_title:
            print(f"[*] Title: {self.manga_title} (ID: {self.manga_hid})")
        if self.target_chapter_id:
            print(f"[*] Direct chapter requested: {self.target_chapter_id}")

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
        possible_roots = [
            Path.cwd(),
            Path(__file__).resolve().parent.parent.parent,
            Path(__file__).resolve().parent.parent,
            Path(__file__).resolve().parent,
        ]
        signer_script = None
        for r in possible_roots:
            candidate = r / "comix_signer.js"
            if candidate.is_file():
                signer_script = candidate
                break

        if not signer_script:
            raise FileNotFoundError("Signer bridge script 'comix_signer.js' not found in project.")

        self.bridge = NodeSignerBridge(
            script_path=str(signer_script),
            secure_js_path=self.secure_js_path,
            cfg_token=self.cfg_token,
            manga_id=self.manga_hid or ""
        )

    def close(self):
        """Release bridge process and resources."""
        if self.bridge:
            self.bridge.close()
