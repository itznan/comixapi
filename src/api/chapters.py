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

        pages_obj = decrypted.get("pages", {})
        base_url = pages_obj.get("baseUrl", "")
        items = pages_obj.get("items", [])

        images = []
        for p in items:
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

        url_path = f"/manga/{self.manga_hid}/chapters"
        params = {"page": page, "limit": limit}
        if scanlation_group_id is not None:
            params["group_id"] = scanlation_group_id

        signed_params = self.bridge.sign(url_path, params=params)
        qs = "&".join(f"{k}={v}" for k, v in signed_params.items())
        full_url = f"{API_BASE}{url_path}?{qs}"

        encrypted_json = self._http_get(full_url, is_json=True, extra_headers={
            "Referer": f"{BASE_URL}/title/{self.manga_slug}"
        })
        decrypted = self.bridge.decrypt(url_path, encrypted_json)
        items = decrypted.get("items", [])
        meta = decrypted.get("meta", {})

        formatted_chapters = []
        for ch in items:
            group = ch.get("group") or ch.get("scanlation_group") or {}
            ch_copy = ch.copy()
            if isinstance(group, dict) and group:
                ch_copy["scanlation_group"] = {
                    "scanlation_group_id": group.get("id"),
                    "name": group.get("name")
                }
            formatted_chapters.append(ch_copy)

        return {
            "chapters": formatted_chapters,
            "pagination": {
                "current_page": meta.get("page", page),
                "last_page": meta.get("lastPage", page),
                "total": meta.get("total", len(formatted_chapters)),
                "limit": limit
            }
        }
