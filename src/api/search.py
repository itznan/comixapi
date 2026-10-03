"""
Manga search, trending discovery, category filtering, and scanlation group metadata.
"""

import urllib.parse
from typing import Any
from ..config import BASE_URL, API_BASE, GENRE_MAP, DEMOGRAPHIC_MAP


class SearchMixin:
    """Mixin providing search, trending, filtering, and group retrieval for ComixAPI."""

    def search_titles(
        self,
        keyword: str = "",
        limit: int = 10,
        page: int = 1,
        manga_type: str = None,
        status: str = None,
        sort: str = None,
        genres: list = None,
        demographics: list = None,
        content_ratings: list = None,
        year_from: int = None,
        year_to: int = None,
        return_meta: bool = False
    ) -> Any:
        """Search manga on Comix.to with optional filters, sorting, and pagination metadata."""
        if not self.bridge:
            self.bootstrap()

        url_path = "/manga"
        params = {"limit": limit, "page": page}
        if keyword and str(keyword).strip():
            params["keyword"] = str(keyword).strip()

        type_aliases = {
            "manga": "manga",
            "manhwa": "manhwa",
            "manhua": "manhua",
            "korean": "manhwa",
            "japanese": "manga",
            "chinese": "manhua",
            "webtoon": "manhwa",
            "comic": "other",
            "other": "other",
        }
        status_aliases = {
            "ongoing": "releasing",
            "releasing": "releasing",
            "completed": "finished",
            "finished": "finished",
            "hiatus": "on_hiatus",
            "on_hiatus": "on_hiatus",
            "dropped": "discontinued",
            "cancelled": "discontinued",
            "canceled": "discontinued",
            "discontinued": "discontinued",
        }
        sort_aliases = {
            "views": ("views_7d", "desc"),
            "views_7d": ("views_7d", "desc"),
            "views_30d": ("views_30d", "desc"),
            "views_total": ("views_total", "desc"),
            "popular": ("views_7d", "desc"),
            "trending": ("views_7d", "desc"),
            "rating": ("score", "desc"),
            "score": ("score", "desc"),
            "rated": ("score", "desc"),
            "latest": ("chapter_updated_at", "desc"),
            "updated": ("chapter_updated_at", "desc"),
            "chapter_updated_at": ("chapter_updated_at", "desc"),
            "created": ("created_at", "desc"),
            "created_at": ("created_at", "desc"),
            "newest": ("created_at", "desc"),
            "oldest": ("created_at", "asc"),
            "title": ("title", "asc"),
            "name": ("title", "asc"),
            "az": ("title", "asc"),
            "za": ("title", "desc"),
            "follows": ("follows_total", "desc"),
            "bookmarks": ("follows_total", "desc"),
        }

        if manga_type:
            raw_types = [manga_type] if isinstance(manga_type, str) else manga_type
            resolved_types = []
            for t in raw_types:
                for sub_t in str(t).split(","):
                    clean_t = sub_t.strip().lower()
                    if clean_t:
                        resolved_types.append(type_aliases.get(clean_t, clean_t))
            if resolved_types:
                params["types"] = resolved_types

        if status:
            raw_statuses = [status] if isinstance(status, str) else status
            resolved_statuses = []
            for s in raw_statuses:
                for sub_s in str(s).split(","):
                    clean_s = sub_s.strip().lower()
                    if clean_s:
                        resolved_statuses.append(status_aliases.get(clean_s, clean_s))
            if resolved_statuses:
                params["statuses"] = resolved_statuses

        if sort:
            sort_val = str(sort).strip().lower()
            if ":" in sort_val:
                col, direction = sort_val.split(":", 1)
                col = col.strip()
                direction = direction.strip()
                if col in sort_aliases:
                    col = sort_aliases[col][0]
                params["order"] = {col: direction}
            elif sort_val in sort_aliases:
                col, direction = sort_aliases[sort_val]
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

        if content_ratings:
            if isinstance(content_ratings, (str, int)):
                content_ratings = [content_ratings]
            resolved_ratings = []
            for r in content_ratings:
                if isinstance(r, str):
                    for part in r.split(","):
                        clean_r = part.strip().lower()
                        if clean_r:
                            resolved_ratings.append(clean_r)
                elif r:
                    resolved_ratings.append(str(r).lower())
            if resolved_ratings:
                params["content_rating"] = resolved_ratings

        if year_from is not None:
            try:
                params["year_from"] = int(year_from)
            except (ValueError, TypeError):
                pass

        if year_to is not None:
            try:
                params["year_to"] = int(year_to)
            except (ValueError, TypeError):
                pass

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

        qs = urllib.parse.urlencode(pairs)
        full_url = f"{API_BASE}{url_path}?{qs}"

        encrypted_json = self._http_get(
            full_url,
            is_json=True,
            extra_headers={"Referer": f"{BASE_URL}/browse"}
        )
        decrypted = self.bridge.decrypt(url_path, encrypted_json)
        items = self._extract_items(decrypted)
        if return_meta:
            meta = decrypted.get("meta") or {}
            if not meta and isinstance(decrypted.get("result"), dict):
                meta = decrypted["result"].get("meta", {})
            return items, meta
        return items

    def get_top_titles(self, type_filter: str = "trending", days: int = 1, limit: int = 20) -> list:
        """Fetch top or trending titles on Comix.to."""
        if not self.bridge:
            self.bootstrap()

        url_path = "/manga/top"
        trend_type = (type_filter or "trending").strip().lower()
        if trend_type in ("follow", "following", "bookmarks"):
            trend_type = "follows"
        elif trend_type not in ("trending", "follows"):
            trend_type = "trending"

        # Comix.to supports days 1, 7, 30 for trending; 1, 7 for follows
        valid_days = int(days) if str(days).isdigit() else 1
        if trend_type == "follows" and valid_days > 7:
            valid_days = 7
        elif valid_days not in (1, 7, 30):
            valid_days = 1 if valid_days < 4 else (7 if valid_days < 15 else 30)

        params = {"type": trend_type, "days": valid_days, "limit": limit}
        signed = self.bridge.sign(url_path, params=params)
        qs = urllib.parse.urlencode(signed, doseq=True)
        full_url = f"{API_BASE}{url_path}?{qs}"
        encrypted = self._http_get(full_url, is_json=True, extra_headers={"Referer": BASE_URL})
        decrypted = self.bridge.decrypt(url_path, encrypted)
        return self._extract_items(decrypted)

    def get_manga_groups(self, manga_hid: str = None) -> list:
        """Fetch scanlation groups that contributed to a manga."""
        raw_hid = manga_hid or self.manga_hid or ""
        hid = raw_hid.split("-")[0].strip()
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

    search_manga = search_titles
