"""
Authenticated user operations: followed titles, reading history, and bookmark exports.
"""

import json
import urllib.parse
from ..config import BASE_URL, API_BASE


class UserMixin:
    """Mixin providing authenticated user library and export functionality for ComixAPI."""

    def get_following_titles(self, limit_per_page: int = 50) -> list:
        """Fetch all bookmarked/followed titles in the user's account with automatic pagination."""
        if not self.cookie_header:
            raise RuntimeError("Session cookies required for fetching followed titles. Please provide comix.to_cookies.txt.")

        if not self.bridge:
            self.bootstrap()

        url_path = "/user/following-titles"
        all_items = []
        page = 1

        while True:
            params = {"page": page, "limit": limit_per_page}
            signed = self.bridge.sign(url_path, params=params)
            qs = urllib.parse.urlencode(signed, doseq=True)
            full_url = f"{API_BASE}{url_path}?{qs}"

            encrypted = self._http_get(
                full_url,
                is_json=True,
                extra_headers={"Referer": f"{BASE_URL}/user/bookmark"}
            )
            decrypted = self.bridge.decrypt(url_path, encrypted)
            items = self._extract_items(decrypted)
            if not items:
                break

            all_items.extend(items)

            # Check pagination metadata
            meta = {}
            if isinstance(decrypted, dict):
                res = decrypted.get("result", {})
                if isinstance(res, dict):
                    meta = res.get("meta", {})

            has_next = meta.get("hasNext")
            last_page = meta.get("lastPage", page)

            if has_next is False or page >= last_page:
                break
            page += 1

        return all_items

    def get_user_history(self, page: int = 1, limit: int = 50) -> list:
        """Fetch reading history from the user's account."""
        if not self.cookie_header:
            raise RuntimeError("Session cookies required for fetching user history. Please provide comix.to_cookies.txt.")

        if not self.bridge:
            self.bootstrap()

        url_path = "/user/history"
        params = {"page": page, "limit": limit}
        signed = self.bridge.sign(url_path, params=params)
        qs = urllib.parse.urlencode(signed, doseq=True)
        full_url = f"{API_BASE}{url_path}?{qs}"

        encrypted = self._http_get(
            full_url,
            is_json=True,
            extra_headers={"Referer": f"{BASE_URL}/user/history"}
        )
        decrypted = self.bridge.decrypt(url_path, encrypted)
        return self._extract_items(decrypted)

    def export_user_bookmarks(self, format_type: str = "mal") -> str:
        """Export user bookmarks/reading list to MAL, AniList, CSV, or JSON format."""
        if not self.cookie_header:
            raise RuntimeError("Session cookies required for exporting bookmarks. Please provide comix.to_cookies.txt.")

        if not self.bridge:
            self.bootstrap()

        fmt = (format_type or "mal").strip().lower()

        # 1. Native MAL XML export
        if fmt in ("mal", "myanimelist"):
            url_path = "/user/list-backup/export"
            signed = self.bridge.sign(url_path, params={"format": "mal"})
            qs = urllib.parse.urlencode(signed, doseq=True)
            full_url = f"{API_BASE}{url_path}?{qs}"
            res = self._http_get(full_url, is_json=True, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
            if isinstance(res, dict) and "result" in res:
                return res["result"]
            return str(res)

        # 2. Native CSV export
        if fmt == "csv":
            url_path = "/user/list-backup/export"
            signed = self.bridge.sign(url_path, params={"format": "csv"})
            qs = urllib.parse.urlencode(signed, doseq=True)
            full_url = f"{API_BASE}{url_path}?{qs}"
            res = self._http_get(full_url, is_json=True, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
            if isinstance(res, dict) and "result" in res:
                return res["result"]
            return str(res)

        # 3. Native TXT export
        if fmt == "txt":
            url_path = "/user/list-backup/export"
            signed = self.bridge.sign(url_path, params={"format": "txt"})
            qs = urllib.parse.urlencode(signed, doseq=True)
            full_url = f"{API_BASE}{url_path}?{qs}"
            res = self._http_get(full_url, is_json=True, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
            if isinstance(res, dict) and "result" in res:
                return res["result"]
            return str(res)

        # 4. AniList JSON export (derived from followed titles + AniList IDs/links)
        if fmt in ("anilist", "al"):
            following = self.get_following_titles()
            folder_map = {
                1: "CURRENT",
                2: "COMPLETED",
                3: "PAUSED",
                4: "DROPPED",
                5: "PLANNING"
            }
            anilist_data = []
            for item in following:
                pivot = item.get("bookmarkPivot") or {}
                links = item.get("links") or {}
                al_url = links.get("al", "")
                mal_url = links.get("mal", "")
                al_id = None
                if al_url:
                    parts = al_url.rstrip("/").split("/")
                    if parts and parts[-1].isdigit():
                        al_id = int(parts[-1])
                mal_id = None
                if mal_url:
                    parts = mal_url.rstrip("/").split("/")
                    if parts and parts[-1].isdigit():
                        mal_id = int(parts[-1])

                folder_id = pivot.get("folderId", 5)
                status_str = folder_map.get(folder_id, "PLANNING")

                anilist_data.append({
                    "title": item.get("title"),
                    "anilist_id": al_id,
                    "anilist_url": al_url,
                    "mal_id": mal_id,
                    "status": status_str,
                    "progress": pivot.get("userChapter", 0),
                    "score": pivot.get("userScore", 0),
                    "total_chapters": item.get("latestChapter"),
                    "updated_at": item.get("updatedAtFormatted")
                })
            return json.dumps(anilist_data, indent=2, ensure_ascii=False)

        # 5. Raw JSON backup of all bookmarks
        if fmt == "json":
            following = self.get_following_titles()
            return json.dumps(following, indent=2, ensure_ascii=False)

        raise ValueError(f"Unsupported export format '{format_type}'. Supported: 'mal', 'anilist', 'csv', 'json', 'txt'")
