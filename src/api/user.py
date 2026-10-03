"""
Authenticated user operations: followed titles, reading history, and bookmark exports.
"""

import csv
import io
import json
import urllib.parse
from ..config import BASE_URL, API_BASE

FOLDER_NAME_MAP = {
    1: "reading",
    2: "completed",
    3: "paused",
    4: "dropped",
    5: "planning"
}

FOLDER_ALIAS_MAP = {
    "reading": 1,
    "current": 1,
    "1": 1,
    "completed": 2,
    "finished": 2,
    "2": 2,
    "paused": 3,
    "on_hold": 3,
    "hold": 3,
    "3": 3,
    "dropped": 4,
    "4": 4,
    "planning": 5,
    "plan_to_read": 5,
    "plan": 5,
    "5": 5
}


class UserMixin:
    """Mixin providing authenticated user library and export functionality for ComixAPI."""

    def get_following_titles(self, folder: str | int = None, limit_per_page: int = 50) -> list:
        """Fetch all bookmarked/followed titles in the user's account with automatic pagination."""
        if not self.cookie_header:
            raise RuntimeError("Session cookies required for fetching followed titles. Please provide comix.to_cookies.txt.")

        if not self.bridge:
            self.bootstrap()

        url_path = "/user/following-titles"
        all_items = []
        page = 1

        target_folder_id = None
        if folder is not None:
            norm_key = str(folder).strip().lower().replace("-", "_").replace(" ", "_")
            target_folder_id = FOLDER_ALIAS_MAP.get(norm_key)

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

        if target_folder_id is not None:
            filtered = []
            for it in all_items:
                f_id = (it.get("bookmarkPivot") or {}).get("folderId")
                if f_id == target_folder_id:
                    filtered.append(it)
            return filtered

        return all_items

    def get_user_history(self, page: int = 1, limit: int = 50) -> list:
        """Fetch reading history from the user's account with normalized comic & chapter data."""
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
        raw_items = self._extract_items(decrypted)

        normalized = []
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            manga = it.get("manga")
            ch = it.get("chapter")
            if isinstance(manga, dict):
                entry = dict(manga)
                if isinstance(ch, dict):
                    entry["lastReadChapter"] = ch.get("number")
                    entry["lastReadChapterId"] = ch.get("hid") or ch.get("id")
                    entry["lastReadChapterName"] = ch.get("name") or ch.get("title")
                entry["lastReadAt"] = it.get("updatedAt") or it.get("createdAt")
                entry["rawHistory"] = it
                normalized.append(entry)
            else:
                normalized.append(it)

        return normalized

    def _generate_mal_xml(self, following: list) -> str:
        """Fallback generator for standard MyAnimeList manga export XML."""
        lines = [
            '<?xml version="1.0" encoding="UTF-8" ?>',
            '<!--',
            ' Created by Comix.to Downloader Bookmark Exporter',
            ' Program: MyAnimeList Manga List Export',
            '-->',
            '<myanimelist>',
            '  <myinfo>',
            '    <user_id>0</user_id>',
            '    <user_name>ComixUser</user_name>',
            '    <user_export_type>2</user_export_type>',
            '  </myinfo>'
        ]

        status_map = {
            1: "Reading",
            2: "Completed",
            3: "On-Hold",
            4: "Dropped",
            5: "Plan to Read"
        }

        for item in following:
            pivot = item.get("bookmarkPivot") or {}
            links = item.get("links") or {}
            mal_url = links.get("mal", "")
            mal_id = 0
            if mal_url:
                parts = mal_url.rstrip("/").split("/")
                if parts and parts[-1].isdigit():
                    mal_id = int(parts[-1])

            title = item.get("title") or "Unknown"
            latest_ch = item.get("latestChapter") or 0
            user_ch = pivot.get("userChapter") or 0
            score = pivot.get("userScore") or 0
            folder_id = pivot.get("folderId") or 1
            mal_status = status_map.get(folder_id, "Reading")

            lines.append("  <manga>")
            lines.append(f"    <manga_mangadb_id>{mal_id}</manga_mangadb_id>")
            lines.append(f"    <manga_title><![CDATA[{title}]]></manga_title>")
            lines.append("    <manga_volumes>0</manga_volumes>")
            lines.append(f"    <manga_chapters>{latest_ch}</manga_chapters>")
            lines.append("    <my_read_volumes>0</my_read_volumes>")
            lines.append(f"    <my_read_chapters>{user_ch}</my_read_chapters>")
            lines.append(f"    <my_score>{score}</my_score>")
            lines.append(f"    <my_status>{mal_status}</my_status>")
            lines.append("  </manga>")

        lines.append("</myanimelist>")
        return "\n".join(lines)

    def _generate_csv(self, following: list) -> str:
        """Fallback generator for CSV reading list export."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "Title", "Type", "Status", "UserChapter", "LatestChapter", "UserScore", "Folder", "MAL_URL", "AniList_URL", "Comix_URL"])

        for it in following:
            pivot = it.get("bookmarkPivot") or {}
            links = it.get("links") or {}
            folder_id = pivot.get("folderId") or 1
            folder_name = FOLDER_NAME_MAP.get(folder_id, "reading")
            writer.writerow([
                it.get("id") or it.get("hid") or "",
                it.get("title") or "",
                it.get("type") or "manga",
                it.get("status") or "",
                pivot.get("userChapter") or 0,
                it.get("latestChapter") or 0,
                pivot.get("userScore") or 0,
                folder_name,
                links.get("mal") or "",
                links.get("al") or "",
                it.get("url") or f"/title/{it.get('hid', '')}"
            ])

        return output.getvalue()

    def export_user_bookmarks(self, format_type: str = "mal") -> str:
        """Export user bookmarks/reading list to MAL, AniList, CSV, or JSON format."""
        if not self.cookie_header:
            raise RuntimeError("Session cookies required for exporting bookmarks. Please provide comix.to_cookies.txt.")

        if not self.bridge:
            self.bootstrap()

        fmt = (format_type or "mal").strip().lower()

        # 1. MyAnimeList XML export
        if fmt in ("mal", "myanimelist"):
            url_path = "/user/list-backup/export"
            try:
                signed = self.bridge.sign(url_path, params={"format": "mal"})
                qs = urllib.parse.urlencode(signed, doseq=True)
                full_url = f"{API_BASE}{url_path}?{qs}"
                raw = self._http_get(full_url, is_json=False, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
                if raw and isinstance(raw, str) and ("<myanimelist>" in raw or "<manga>" in raw):
                    return raw
                # Check if wrapped in JSON
                try:
                    js = json.loads(raw)
                    try:
                        decrypted = self.bridge.decrypt(url_path, js)
                        if isinstance(decrypted, dict) and "result" in decrypted and isinstance(decrypted["result"], str):
                            if "<myanimelist>" in decrypted["result"]:
                                return decrypted["result"]
                    except Exception:
                        pass
                    if isinstance(js, dict) and "result" in js and isinstance(js["result"], str):
                        if "<myanimelist>" in js["result"]:
                            return js["result"]
                except Exception:
                    pass
            except Exception:
                pass

            # Fallback: build high-fidelity standard MAL XML from followed titles
            following = self.get_following_titles()
            return self._generate_mal_xml(following)

        # 2. CSV export
        if fmt == "csv":
            url_path = "/user/list-backup/export"
            try:
                signed = self.bridge.sign(url_path, params={"format": "csv"})
                qs = urllib.parse.urlencode(signed, doseq=True)
                full_url = f"{API_BASE}{url_path}?{qs}"
                raw = self._http_get(full_url, is_json=False, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
                if raw and isinstance(raw, str) and not raw.strip().startswith("<") and "," in raw:
                    return raw
            except Exception:
                pass

            following = self.get_following_titles()
            return self._generate_csv(following)

        # 3. Plain text TXT export
        if fmt == "txt":
            url_path = "/user/list-backup/export"
            try:
                signed = self.bridge.sign(url_path, params={"format": "txt"})
                qs = urllib.parse.urlencode(signed, doseq=True)
                full_url = f"{API_BASE}{url_path}?{qs}"
                raw = self._http_get(full_url, is_json=False, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
                if raw and isinstance(raw, str) and not raw.strip().startswith("<") and len(raw) > 5:
                    return raw
            except Exception:
                pass

            following = self.get_following_titles()
            lines = [f"{it.get('title')} (Ch {it.get('latestChapter')})" for it in following]
            return "\n".join(lines)

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

                folder_id = pivot.get("folderId", 1)
                status_str = folder_map.get(folder_id, "CURRENT")

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

        # 5. Full JSON list backup
        if fmt in ("json", "backup"):
            url_path = "/user/list-backup/export"
            try:
                signed = self.bridge.sign(url_path, params={"format": "json"})
                qs = urllib.parse.urlencode(signed, doseq=True)
                full_url = f"{API_BASE}{url_path}?{qs}"
                raw = self._http_get(full_url, is_json=False, extra_headers={"Referer": f"{BASE_URL}/user/list-backup"})
                parsed = json.loads(raw)
                try:
                    decrypted = self.bridge.decrypt(url_path, parsed)
                    if isinstance(decrypted, (dict, list)):
                        return json.dumps(decrypted, indent=2, ensure_ascii=False)
                except Exception:
                    pass
                if isinstance(parsed, (dict, list)):
                    return json.dumps(parsed, indent=2, ensure_ascii=False)
            except Exception:
                pass

            following = self.get_following_titles()
            return json.dumps(following, indent=2, ensure_ascii=False)

        raise ValueError(f"Unsupported export format '{format_type}'. Supported: 'mal', 'anilist', 'csv', 'json', 'txt'")
