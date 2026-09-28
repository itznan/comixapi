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

from .config import USER_AGENT, BASE_URL, API_BASE, GENRE_MAP, DEMOGRAPHIC_MAP
from .bridge import NodeSignerBridge


class ComixAPI:
    """Client for fetching and decrypting Comix.to metadata and chapters."""

    def __init__(self, raw_url_or_slug: str = "", cookie_header: str = ""):
        self.raw_url_or_slug = raw_url_or_slug.strip() if raw_url_or_slug else ""
        self.cookie_header = cookie_header
        self.manga_hid = None
        self.manga_slug = None
        self.manga_title = None
        self.target_chapter_id = None
        self.metadata = {}
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
        """Extract hid, slug, and optional target chapter id from URL or slug string."""
        url = self.raw_url_or_slug
        if not url:
            return BASE_URL

        if not url.startswith("http"):
            url = f"{BASE_URL}/title/{url}"

        parsed = urlparse(url)
        path = parsed.path.strip("/")
        parts = path.split("/")

        slug_part = ""
        if len(parts) >= 3 and parts[0] == "title":
            slug_part = parts[1]
            chapter_part = parts[2]
            self.target_chapter_id = chapter_part.split("-")[0]
        elif len(parts) >= 2 and parts[0] == "title":
            slug_part = parts[1]
        elif len(parts) == 1 and parts[0]:
            slug_part = parts[0]
        elif parts:
            slug_part = parts[-1]

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
            manga_id=self.manga_hid or ""
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

    def _extract_items(self, data) -> list:
        """Extract list of items from diverse Comix.to response structures."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            res = data.get("result")
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                if "items" in res and isinstance(res["items"], list):
                    return res["items"]
                if "data" in res and isinstance(res["data"], list):
                    return res["data"]
            if "items" in data and isinstance(data["items"], list):
                return data["items"]
            if "data" in data and isinstance(data["data"], list):
                return data["data"]
        return []

    def search_titles(
        self,
        keyword: str = "",
        limit: int = 10,
        page: int = 1,
        manga_type: str = None,
        status: str = None,
        sort: str = None,
        genres: list = None,
        demographics: list = None
    ) -> list:
        """Search manga on Comix.to with optional filters and sorting."""
        if not self.bridge:
            self.bootstrap()

        url_path = "/manga"
        params = {"limit": limit, "page": page}
        if keyword and str(keyword).strip():
            params["keyword"] = str(keyword).strip()

        if manga_type:
            if isinstance(manga_type, str):
                params["types"] = [t.strip().lower() for t in manga_type.split(",") if t.strip()]
            else:
                params["types"] = manga_type

        if status:
            if isinstance(status, str):
                params["statuses"] = [s.strip().lower() for s in status.split(",") if s.strip()]
            else:
                params["statuses"] = status

        if sort:
            sort_val = str(sort).strip()
            if ":" in sort_val:
                col, direction = sort_val.split(":", 1)
                params["order"] = {col: direction}
            else:
                params["order"] = {sort_val: "desc"}

        if genres:
            if isinstance(genres, (str, int)):
                genres = [genres]
            resolved_genres = []
            for g in genres:
                if isinstance(g, str):
                    for part in g.split(","):
                        part = part.strip().lower()
                        if not part:
                            continue
                        if part.isdigit():
                            resolved_genres.append(int(part))
                        elif part in GENRE_MAP:
                            resolved_genres.append(GENRE_MAP[part])
                        elif part.replace(" ", "-") in GENRE_MAP:
                            resolved_genres.append(GENRE_MAP[part.replace(" ", "-")])
                        elif part.replace("-", " ") in GENRE_MAP:
                            resolved_genres.append(GENRE_MAP[part.replace("-", " ")])
                elif isinstance(g, int):
                    resolved_genres.append(g)
            if resolved_genres:
                params["genres_in"] = resolved_genres

        if demographics:
            if isinstance(demographics, (str, int)):
                demographics = [demographics]
            resolved_demos = []
            for d in demographics:
                if isinstance(d, str):
                    for part in d.split(","):
                        part = part.strip().lower()
                        if not part:
                            continue
                        if part.isdigit():
                            resolved_demos.append(int(part))
                        elif part in DEMOGRAPHIC_MAP:
                            resolved_demos.append(DEMOGRAPHIC_MAP[part])
                elif isinstance(d, int):
                    resolved_demos.append(d)
            if resolved_demos:
                params["demographics"] = resolved_demos

        signed_params = self.bridge.sign(url_path, params=params)

        pairs = []
        for k, v in signed_params.items():
            if isinstance(v, list):
                for item in v:
                    pairs.append((f"{k}[]", item))
            elif isinstance(v, dict):
                for subk, subv in v.items():
                    pairs.append((f"{k}[{subk}]", subv))
            else:
                pairs.append((k, v))

        import urllib.parse
        qs = urllib.parse.urlencode(pairs)
        full_url = f"{API_BASE}{url_path}?{qs}"

        encrypted_json = self._http_get(
            full_url,
            is_json=True,
            extra_headers={"Referer": f"{BASE_URL}/browse"}
        )
        decrypted = self.bridge.decrypt(url_path, encrypted_json)
        return self._extract_items(decrypted)

    def get_top_titles(self, type_filter: str = "trending", days: int = 1, limit: int = 20) -> list:
        """Fetch top or trending titles on Comix.to."""
        if not self.bridge:
            self.bootstrap()

        url_path = "/manga/top"
        params = {"type": type_filter, "days": days, "limit": limit}
        signed = self.bridge.sign(url_path, params=params)
        import urllib.parse
        qs = urllib.parse.urlencode(signed, doseq=True)
        full_url = f"{API_BASE}{url_path}?{qs}"
        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": BASE_URL})
        decrypted = self.bridge.decrypt(url_path, encrypted)
        return self._extract_items(decrypted)

    def get_manga_groups(self, manga_hid: str = None) -> list:
        """Fetch scanlation groups that contributed to a manga."""
        hid = manga_hid or self.manga_hid
        if not hid:
            return []
        if not self.bridge:
            self.bootstrap()

        url_path = f"/manga/{hid}/groups"
        signed = self.bridge.sign(url_path, manga_id=hid)
        sig = signed.get("_", "")
        full_url = f"{API_BASE}{url_path}?_={sig}"
        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": BASE_URL})
        decrypted = self.bridge.decrypt(url_path, encrypted, manga_id=hid)
        return self._extract_items(decrypted)

    def close(self):
        if self.bridge:
            self.bridge.close()
