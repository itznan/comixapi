"""
Chapter retrieval, pagination, page extraction, and image decryption logic.
"""

from urllib.parse import urljoin
from ..config import BASE_URL, API_BASE


class ChapterMixin:
    """Mixin providing chapter retrieval and page decryption functionality for ComixAPI."""

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

    def fetch_all_chapters(self) -> list:
        """Fetch and decrypt all chapters using API pagination."""
        if not self.bridge:
            self.bootstrap()

        if not self.manga_hid:
            raise ValueError("Manga HID or URL must be set to fetch chapters.")

        print("[*] Fetching chapters list...")
        all_chapters = []
        page = 1
        limit = 100

        while True:
            url_path = f"/manga/{self.manga_hid}/chapters"
            signed_params = self.bridge.sign(url_path, params={"limit": limit, "page": page})
            qs = "&".join(f"{k}={v}" for k, v in signed_params.items())
            full_url = f"{API_BASE}{url_path}?{qs}"

            referer = f"{BASE_URL}/title/{self.manga_slug}" if self.manga_slug else BASE_URL
            encrypted_json = self._http_get(full_url, is_json=True, extra_headers={
                "Referer": referer
            })
            decrypted = self.bridge.decrypt(url_path, encrypted_json)
            items = self._extract_items(decrypted)
            if not items:
                break
            all_chapters.extend(items)

            meta = {}
            if isinstance(decrypted, dict):
                meta = decrypted.get("meta") or {}
                if not meta and isinstance(decrypted.get("result"), dict):
                    meta = decrypted["result"].get("meta", {})

            last_page = meta.get("lastPage") or meta.get("last_page") or 1
            has_next = meta.get("hasNext") if "hasNext" in meta else meta.get("has_next", False)
            if page >= last_page or has_next is False:
                break
            page += 1

        print(f"[*] Found {len(all_chapters)} chapter releases across all scanlators/languages.")
        return all_chapters

    def fetch_chapter_pages(self, chapter: dict) -> list:
        """Fetch and decrypt images for a specific chapter."""
        if not self.bridge:
            self.bootstrap()

        ch_id = str(chapter.get("id") or chapter.get("hid") or "").strip()
        if not ch_id:
            return []

        url_path = f"/chapters/{ch_id}"
        signed_params = self.bridge.sign(url_path, chapter_id=ch_id)
        sig = signed_params.get("_", "")
        full_url = f"{API_BASE}{url_path}?_={sig}"

        ch_url = chapter.get("url", "")
        referer = f"{BASE_URL}{ch_url}" if ch_url else (f"{BASE_URL}/title/{self.manga_slug}" if self.manga_slug else f"{BASE_URL}/chapter/{ch_id}")

        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": referer})
        decrypted = self.bridge.decrypt(url_path, encrypted, chapter_id=ch_id)

        pages_obj = {}
        if isinstance(decrypted, dict):
            pages_obj = decrypted.get("pages")
            if not isinstance(pages_obj, dict):
                res = decrypted.get("result") or decrypted.get("data") or decrypted.get("chapter")
                if isinstance(res, dict):
                    pages_obj = res.get("pages")
            if not isinstance(pages_obj, dict):
                pages_obj = {}

        base_url = pages_obj.get("baseUrl", "")
        items = pages_obj.get("items", [])
        if not isinstance(items, list):
            items = []

        img_urls = []
        for p in items:
            if not isinstance(p, dict):
                continue
            raw_url = p.get("url", "")
            if not raw_url:
                continue
            if raw_url.startswith("http"):
                img_urls.append(raw_url)
            else:
                img_urls.append(urljoin(base_url, raw_url))
        return img_urls

    def get_chapter_images(self, chapter_id: str) -> dict:
        """Fetch and decrypt images with dimension metadata for a specific chapter ID."""
        ch_id = str(chapter_id).strip()
        if not self.bridge:
            self.bootstrap()

        url_path = f"/chapters/{ch_id}"
        signed_params = self.bridge.sign(url_path, chapter_id=ch_id)
        sig = signed_params.get("_", "")
        full_url = f"{API_BASE}{url_path}?_={sig}"
        referer = f"{BASE_URL}/chapter/{ch_id}"

        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": referer})
        decrypted = self.bridge.decrypt(url_path, encrypted, chapter_id=ch_id)

        pages_obj = {}
        if isinstance(decrypted, dict):
            pages_obj = decrypted.get("pages")
            if not isinstance(pages_obj, dict):
                res = decrypted.get("result") or decrypted.get("data") or decrypted.get("chapter")
                if isinstance(res, dict):
                    pages_obj = res.get("pages")
            if not isinstance(pages_obj, dict):
                pages_obj = {}

        base_url = pages_obj.get("baseUrl", "")
        items = pages_obj.get("items", [])
        if not isinstance(items, list):
            items = []

        images = []
        for p in items:
            if not isinstance(p, dict):
                continue
            raw_url = p.get("url", "")
            if not raw_url:
                continue
            full_img_url = raw_url if raw_url.startswith("http") else urljoin(base_url, raw_url)
            width = p.get("width") or p.get("w")
            height = p.get("height") or p.get("h")
            entry = {"url": full_img_url}
            if width is not None:
                entry["width"] = width
            if height is not None:
                entry["height"] = height
            images.append(entry)

        return {
            "chapterId": ch_id,
            "total_images": len(images),
            "images": images
        }

    def fetch_chapters_page(self, page: int = 1, limit: int = 30, scanlation_group_id: int = None) -> dict:
        """Fetch a single page of chapters with pagination and optional scanlation group filter."""
        if not self.bridge:
            self.bootstrap()

        if not self.manga_hid:
            raise ValueError("Manga HID or URL must be set to fetch chapters.")

        url_path = f"/manga/{self.manga_hid}/chapters"
        params = {"page": page, "limit": limit}
        if scanlation_group_id is not None:
            params["group_id"] = scanlation_group_id

        signed_params = self.bridge.sign(url_path, params=params)
        qs = "&".join(f"{k}={v}" for k, v in signed_params.items())
        full_url = f"{API_BASE}{url_path}?{qs}"

        referer = f"{BASE_URL}/title/{self.manga_slug}" if self.manga_slug else BASE_URL
        encrypted_json = self._http_get(full_url, is_json=True, extra_headers={
            "Referer": referer
        })
        decrypted = self.bridge.decrypt(url_path, encrypted_json)
        items = self._extract_items(decrypted)

        meta = {}
        if isinstance(decrypted, dict):
            meta = decrypted.get("meta") or {}
            if not meta and isinstance(decrypted.get("result"), dict):
                meta = decrypted["result"].get("meta", {})

        formatted_chapters = []
        for ch in items:
            if not isinstance(ch, dict):
                continue
            group = ch.get("group") or ch.get("scanlation_group") or ch.get("scanlationGroup") or {}
            ch_copy = ch.copy()
            if isinstance(group, dict) and group:
                ch_copy["scanlation_group"] = {
                    "scanlation_group_id": group.get("id"),
                    "name": group.get("name") or group.get("title")
                }
            formatted_chapters.append(ch_copy)

        current_p = meta.get("page") or meta.get("currentPage") or page
        last_p = meta.get("lastPage") or meta.get("last_page") or page
        total_count = meta.get("total") or meta.get("totalCount") or len(formatted_chapters)

        return {
            "chapters": formatted_chapters,
            "pagination": {
                "current_page": current_p,
                "last_page": last_p,
                "total": total_count,
                "limit": limit
            }
        }
