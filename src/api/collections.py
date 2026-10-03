"""
Curated collections and reading lists retrieval (/collections/{id}/items).
"""

import urllib.parse
from ..config import BASE_URL, API_BASE


class CollectionMixin:
    """Mixin providing curated collection retrieval for ComixAPI."""

    @staticmethod
    def parse_collection_id(target: str) -> str:
        """Extract numeric or alphanumeric collection ID from URL, path, or string."""
        if not target:
            return ""
        target = str(target).strip()

        # Handle full URL or path
        if "/" in target:
            parts = [p for p in target.split("/") if p]
            for i, p in enumerate(parts):
                if p.lower() in ("collection", "collections") and i + 1 < len(parts):
                    target = parts[i + 1]
                    break
            else:
                target = parts[-1]

        # Strip query parameters or URL anchors
        target = target.split("?")[0].split("#")[0]

        # Comix.to collection slugs are formatted as <id>-<slug>, e.g. 123-top-10-manhwa
        id_part = target.split("-")[0]
        return id_part or target

    def get_collection(self, collection_id: str) -> dict:
        """Fetch metadata for a curated collection (name, description, owner)."""
        cid = self.parse_collection_id(collection_id)
        if not cid:
            return {}

        if not self.bridge:
            self.bootstrap()

        url_path = f"/collections/{cid}"
        try:
            signed = self.bridge.sign(url_path)
            sig = signed.get("_", "")
            full_url = f"{API_BASE}{url_path}" + (f"?_={sig}" if sig else "")
            encrypted = self._http_get(
                full_url,
                is_json=True,
                extra_headers={"Referer": f"{BASE_URL}/collection/{cid}"}
            )
            decrypted = self.bridge.decrypt(url_path, encrypted)
            if isinstance(decrypted, dict):
                res = decrypted.get("result") or decrypted.get("data") or decrypted
                if isinstance(res, dict):
                    return res
        except Exception:
            pass

        return {"id": cid, "title": f"Collection #{cid}"}

    def get_collection_items(self, collection_id: str, limit_per_page: int = 50) -> list:
        """Fetch all comic series in a curated collection with automatic pagination."""
        cid = self.parse_collection_id(collection_id)
        if not cid:
            return []

        if not self.bridge:
            self.bootstrap()

        url_path = f"/collections/{cid}/items"
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
                extra_headers={"Referer": f"{BASE_URL}/collection/{cid}"}
            )
            decrypted = self.bridge.decrypt(url_path, encrypted)
            raw_items = self._extract_items(decrypted)
            if not raw_items:
                break

            for it in raw_items:
                if isinstance(it, dict) and "manga" in it and isinstance(it["manga"], dict):
                    m_obj = it["manga"].copy()
                    if "order" in it:
                        m_obj["collection_order"] = it["order"]
                    all_items.append(m_obj)
                elif isinstance(it, dict):
                    all_items.append(it)

            # Check pagination metadata
            meta = {}
            if isinstance(decrypted, dict):
                meta = decrypted.get("meta") or {}
                if not meta and isinstance(decrypted.get("result"), dict):
                    meta = decrypted["result"].get("meta", {})

            has_next = meta.get("hasNext") if "hasNext" in meta else meta.get("has_next")
            last_page = meta.get("lastPage") or meta.get("last_page") or page
            if has_next is False or page >= last_page:
                break
            page += 1

        return all_items
