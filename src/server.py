"""
FastAPI application for ComixAPI featuring interactive Swagger UI (/docs) and ReDoc (/redoc).
Provides REST endpoints for search, discovery, metadata, collections, user library, and document downloads,
with CORS & CORP bypassing image proxy and SFW content filtering.
"""

from typing import Optional, List
from pathlib import Path
import urllib.parse
import urllib.request
import urllib.error

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from .config import USER_AGENT, BASE_URL
    from .api import ComixAPI
    from .downloader import ComixDownloader
    from .cookies import find_default_cookies, parse_cookie_file, resolve_cookies, test_cookies
    from .pdf import is_aria2c_available
except (ImportError, ValueError):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src.config import USER_AGENT, BASE_URL
    from src.api import ComixAPI
    from src.downloader import ComixDownloader
    from src.cookies import find_default_cookies, parse_cookie_file, resolve_cookies, test_cookies
    from src.pdf import is_aria2c_available


def proxy_image_url(url: Optional[str]) -> Optional[str]:
    """Wrap image URL into local CORS & CORP bypassing proxy endpoint."""
    if not url:
        return None
    url_str = str(url).strip()
    if not url_str:
        return None
    if url_str.startswith("/api/image?url="):
        return url_str
    return f"/api/image?url={url_str}"


def get_item_image_url(item: dict) -> Optional[str]:
    """Extract poster or cover image URL from diverse Comix item structures."""
    if not isinstance(item, dict):
        return None
    poster = item.get("poster")
    if isinstance(poster, dict):
        url = poster.get("large") or poster.get("medium") or poster.get("small")
        if url:
            return url
    elif isinstance(poster, str) and poster:
        return poster

    for key in ("img", "cover", "image", "thumbnail"):
        val = item.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, dict):
            url = val.get("large") or val.get("url") or val.get("medium")
            if url:
                return url
    return None


def is_nsfw_item(item: dict) -> bool:
    """Determine whether a manga item or metadata dict contains mature/NSFW content."""
    if not isinstance(item, dict):
        return False
    # Content rating check
    cr = str(item.get("content_rating") or item.get("contentRating") or "").lower()
    if cr in ("erotica", "hentai", "mature", "smut", "adult", "18+"):
        return True
    if item.get("is_nsfw") or item.get("nsfw") or item.get("is_adult"):
        return True

    # Genres check
    genres = item.get("genres", [])
    if isinstance(genres, list):
        for g in genres:
            g_name = ((g.get("name") or g.get("title") or "") if isinstance(g, dict) else str(g)).strip().lower()
            if g_name in ("hentai", "erotica", "smut", "mature", "ecchi", "adult", "18+"):
                return True

    # Tags check
    tags = item.get("tags", [])
    if isinstance(tags, list):
        for t in tags:
            t_name = ((t.get("name") or t.get("title") or "") if isinstance(t, dict) else str(t)).strip().lower()
            if t_name in ("hentai", "erotica", "smut", "mature", "ecchi", "adult", "18+"):
                return True

    return False


def format_home_item(item: dict) -> dict:
    """Format manga item for /api/manga/home response."""
    hid = item.get("hid", "")
    slug = item.get("slug", "")
    item_id = f"{hid}-{slug}" if (hid and slug) else str(item.get("id") or hid or slug)

    latest_ch = item.get("latest_chapter") or item.get("chapter") or ""
    if isinstance(latest_ch, dict):
        ch_num = latest_ch.get("number") or latest_ch.get("name") or ""
        chapter_str = f"Ch.{ch_num}" if ch_num != "" else ""
    elif isinstance(latest_ch, (int, float)):
        chapter_str = f"Ch.{latest_ch}"
    elif str(latest_ch).strip():
        ch_val = str(latest_ch).strip()
        chapter_str = ch_val if ch_val.startswith("Ch.") else f"Ch.{ch_val}"
    else:
        chapter_str = ""

    raw_genres = item.get("genres", [])
    genre_names = []
    if isinstance(raw_genres, list):
        for g in raw_genres:
            if isinstance(g, dict):
                g_val = g.get("name") or g.get("title")
                if g_val:
                    genre_names.append(g_val)
            elif isinstance(g, str) and g:
                genre_names.append(g)

    return {
        "title": item.get("title", ""),
        "cover": proxy_image_url(get_item_image_url(item)),
        "chapter": chapter_str,
        "genres": genre_names,
        "id": item_id
    }


def format_search_item(item: dict) -> dict:
    """Format manga item for /api/manga/search, /browse, and /filter response."""
    hid = item.get("hid", "")
    slug = item.get("slug", "")
    item_id = f"{hid}-{slug}" if (hid and slug) else str(item.get("id") or hid or slug)

    score_val = item.get("score") or item.get("rating")
    try:
        score = float(score_val) if score_val is not None else 0.0
    except (ValueError, TypeError):
        score = 0.0

    return {
        "id": item_id,
        "title": item.get("title", ""),
        "img": proxy_image_url(get_item_image_url(item)),
        "status": item.get("status", 1),
        "score": score,
        "type": item.get("type") or item.get("comic_type") or "manga"
    }


def raise_upstream_error(e: Exception, context: str = "") -> None:
    """Normalize upstream HTTP and Cloudflare errors with appropriate status codes and actionable advice."""
    if isinstance(e, HTTPException):
        raise e

    err = e
    while err:
        if isinstance(err, urllib.error.HTTPError):
            if err.code == 403:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        "Comix.to returned 403 Forbidden (Cloudflare challenge active or cookies expired). "
                        "Please update your cookies in 'comix.to_cookies.txt', set the COOKIE_FILE / COMIX_COOKIE env var, "
                        "or run 'python -m src.cookies' to inspect connectivity."
                    )
                )
            if err.code == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"{context} not found on Comix.to." if context else "Resource not found on Comix.to."
                )
            raise HTTPException(
                status_code=err.code,
                detail=f"Upstream Comix.to error ({err.code}): {err.reason}"
            )
        err = getattr(err, "__cause__", None) or getattr(err, "__context__", None)

    err_str = str(e).lower()
    if "403" in err_str or "forbidden" in err_str or "cloudflare" in err_str:
        raise HTTPException(
            status_code=403,
            detail=(
                "Comix.to returned 403 Forbidden (Cloudflare protection active or cookies expired). "
                "Please update your cookies in 'comix.to_cookies.txt' or set the COOKIE_FILE / COMIX_COOKIE env var. "
                "Run 'python -m src.cookies' to inspect connectivity."
            )
        )
    if "not found" in err_str or "404" in err_str:
        raise HTTPException(
            status_code=404,
            detail=f"{context} not found on Comix.to." if context else "Resource not found on Comix.to."
        )

    raise HTTPException(status_code=500, detail=f"{context}: {str(e)}" if context else str(e))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance with Swagger UI."""
    app = FastAPI(
        title="ComixAPI",
        description="""
# 📚 ComixAPI — High-Performance Manga & Manhwa REST API & Proxy

Welcome to the interactive **Swagger UI** for **ComixAPI**!
This RESTful service acts as a complete wrapper and CORS proxy for the Comix manga platform:
* **🛡️ Bypass CORS & CORP**: All manga pages and cover images are proxied through `/api/image` to render seamlessly in `<img>` tags.
* **🔞 SFW Content Filter**: Filter out mature/NSFW content (Hentai, Erotica, Smut) with `?sfw=true`.
* **🔍 Search & Browse**: Query manga by keywords, genre, demographic, status, and sort order.
* **🔥 Trending & Top Discovery**: Real-time daily, weekly, and monthly top charts.
* **📖 Metadata & Chapters**: Fetch title metadata, paginated chapter lists, and scanlation teams.
* **📂 Curated Collections**: Discover and browse community-curated reading lists.
* **👤 User Library & Sync**: Access bookmarked series, reading history, and export to MAL/AniList/CSV.
* **⬇️ Document Downloads**: Download chapters in PDF, CBZ (Tachiyomi/Mihon compatible), and EPUB.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "docExpansion": "list",
            "displayRequestDuration": True,
            "filter": True,
            "syntaxHighlight.theme": "monokai"
        },
        openapi_tags=[
            {
                "name": "System",
                "description": "System health check, cookie authentication status, and aria2 accelerator state."
            },
            {
                "name": "Image Proxy",
                "description": "Bypass CORS & CORP image proxy. Wraps all CDN images to render directly in browser `<img>` tags."
            },
            {
                "name": "Comix Manga API",
                "description": "REST API with feature parity for web reader apps, Discord bots, and personal dashboards."
            },
            {
                "name": "Manga Details",
                "description": "Detailed comic metadata, scanlation teams, and deduplicated chapter lists."
            },
            {
                "name": "Collections",
                "description": "Browse and batch-read curated reading lists and staff picks."
            },
            {
                "name": "Discovery",
                "description": "Legacy title search and trending charts."
            },
            {
                "name": "User Account",
                "description": "Personal library synchronization, bookmarks export (MAL/AniList), and reading history."
            },
            {
                "name": "Downloader",
                "description": "On-demand document packaging for chapters into CBZ, PDF, and EPUB."
            }
        ]
    )

    # Enable CORS for external web dashboards and reader apps
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------
    # Pydantic Request & Response Models
    # ---------------------------------------------------------
    class DownloadChapterRequest(BaseModel):
        manga: str = Field(..., description="Manga slug or URL, e.g. 'emqg8-solo-leveling' or 'https://comix.to/title/...'")
        chapter_number: float = Field(..., description="Chapter number to download, e.g. 1 or 40.5")
        format: str = Field("cbz", description="Output format: 'cbz', 'pdf', 'epub', or 'both'")
        preferred_group: Optional[str] = Field(None, description="Scanlation group filter (e.g. 'AsuraScans')")

    class DownloadSeriesRequest(BaseModel):
        manga: str = Field(..., description="Manga slug or URL")
        chapter_range: str = Field("latest", description="Chapter range spec (e.g. '1-5', 'latest', '10+', 'all')")
        format: str = Field("cbz", description="Output format: 'cbz', 'pdf', 'epub'")
        merge: bool = Field(False, description="Merge downloaded chapters into a single volume file")
        preferred_group: Optional[str] = Field(None, description="Scanlation group filter")

    # ---------------------------------------------------------
    # Health and Index Routes
    # ---------------------------------------------------------
    @app.get(
        "/",
        include_in_schema=False,
        summary="Redirect to Swagger UI"
    )
    def index():
        """Redirects root URL directly to the interactive Swagger UI."""
        return RedirectResponse(url="/docs")

    @app.get(
        "/api/health",
        tags=["System"],
        summary="System Health & Capabilities"
    )
    def health_check():
        """Check server status, aria2c availability, and active cookie configuration."""
        cookie_file = find_default_cookies()
        cookie_data = resolve_cookies()
        has_cookies = bool(cookie_data and len(cookie_data) > 0)
        return {
            "status": "healthy",
            "version": "1.0.0",
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "aria2_accelerator": is_aria2c_available(),
            "authenticated_session": has_cookies,
            "cookie_file": cookie_file if has_cookies else None
        }

    @app.get(
        "/api/cookies/status",
        tags=["System"],
        summary="Check Comix.to Cookie & Cloudflare Bypass Status"
    )
    def check_cookies_status():
        """Tests live connectivity to Comix.to using currently configured cookies."""
        cookie_data = resolve_cookies()
        result = test_cookies(cookie_data)
        cookie_file = find_default_cookies()
        return {
            "has_cookie_configured": bool(cookie_data),
            "cookie_source": cookie_file if cookie_file else ("env:COMIX_COOKIE" if cookie_data else "none"),
            "cookie_length": len(cookie_data),
            "cloudflare_bypassed": result["success"],
            "status_code": result["status_code"],
            "message": result["message"]
        }

    # ---------------------------------------------------------
    # Image Proxy System (Bypass CORS & CORP)
    # ---------------------------------------------------------
    @app.get(
        "/api/image",
        tags=["Image Proxy"],
        summary="Bypass CORS & CORP Image Proxy"
    )
    def proxy_image(url: str = Query(..., description="Target image URL to fetch and proxy")):
        """
        Fetches the image serverside and pipes it directly to your frontend
        with permissive CORS and Cross-Origin-Resource-Policy headers, bypassing
        browser CDN blocks and 403 Forbidden errors.
        """
        raw_url = url.strip()
        while raw_url.startswith("/api/image?url="):
            raw_url = urllib.parse.unquote(raw_url[len("/api/image?url="):]).strip()

        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raise HTTPException(status_code=400, detail="Invalid image URL. Must begin with http:// or https://")

        try:
            req = urllib.request.Request(
                raw_url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Referer": BASE_URL,
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                content_type = resp.headers.get("Content-Type", "image/jpeg")
                return Response(
                    content=data,
                    media_type=content_type,
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Cross-Origin-Resource-Policy": "cross-origin",
                        "Cache-Control": "public, max-age=86400, s-maxage=86400"
                    }
                )
        except urllib.error.HTTPError as he:
            raise HTTPException(status_code=he.code if he.code in (403, 404) else 502, detail=f"CDN image error: {str(he)}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to proxy image: {str(e)}")

    # ---------------------------------------------------------
    # Comix Manga API: Home, Search, Browse, Filter, Read
    # ---------------------------------------------------------
    @app.get(
        "/api/manga/home",
        tags=["Comix Manga API"],
        summary="Home: Popular & Latest Updates"
    )
    def get_manga_home(
        sfw: bool = Query(False, description="Filter out mature/NSFW content"),
        nsfw: Optional[bool] = Query(None, description="Set to false to filter out mature/NSFW content")
    ):
        """Fetches the 'Most Recent Popular' and 'Latest Updates' from the homepage."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        is_sfw = sfw or (nsfw is False)
        try:
            raw_popular = api.get_top_titles(type_filter="trending", days=1, limit=15)
            raw_latest = api.search_titles(sort="latest", limit=15)

            if is_sfw:
                raw_popular = [p for p in raw_popular if not is_nsfw_item(p)]
                raw_latest = [l for l in raw_latest if not is_nsfw_item(l)]

            popular = [format_home_item(p) for p in raw_popular]
            latest = [format_home_item(l) for l in raw_latest]

            return {
                "popular": popular,
                "latest": latest
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch home manga: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/manga/search",
        tags=["Comix Manga API"],
        summary="Search Manga with Advanced Filters"
    )
    def search_manga_advanced(
        q: str = Query("", description="The search query"),
        sfw: bool = Query(False, description="Filter out NSFW content"),
        nsfw: Optional[bool] = Query(None, description="Set to false to filter out NSFW content"),
        types: Optional[List[str]] = Query(None, alias="types[]"),
        type: Optional[str] = Query(None, description="Comic type filter (e.g. 'manga', 'manhwa')"),
        status: Optional[str] = Query(None, description="Filter status: releasing, finished, on_hiatus, etc."),
        genres: Optional[List[str]] = Query(None, alias="genres[]"),
        genre: Optional[str] = Query(None, description="Comma-separated genres, e.g. 'action,fantasy'"),
        content_rating: Optional[List[str]] = Query(None, alias="content_rating[]"),
        demographic: Optional[List[str]] = Query(None, alias="demographic[]"),
        demographics: Optional[str] = Query(None, description="Comma-separated demographics"),
        sort: Optional[str] = Query(None, description="Sort order: views, rating, latest, newest"),
        year_from: Optional[int] = Query(None, description="Starting release year"),
        year_to: Optional[int] = Query(None, description="Ending release year"),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=50, description="Items per page")
    ):
        """Searches for mangas based on a keyword with advanced type, genre, demographic, and rating filters."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        is_sfw = sfw or (nsfw is False)
        try:
            resolved_types = list(types) if types else []
            if type:
                resolved_types.extend([t.strip() for t in type.split(",") if t.strip()])

            resolved_genres = list(genres) if genres else []
            if genre:
                resolved_genres.extend([g.strip() for g in genre.split(",") if g.strip()])

            resolved_demos = list(demographic) if demographic else []
            if demographics:
                resolved_demos.extend([d.strip() for d in demographics.split(",") if d.strip()])

            cr = content_rating
            if is_sfw and not cr:
                cr = ["safe", "suggestive"]

            raw_items, meta = api.search_titles(
                keyword=q,
                limit=limit,
                page=page,
                manga_type=resolved_types if resolved_types else None,
                status=status,
                genres=resolved_genres if resolved_genres else None,
                demographics=resolved_demos if resolved_demos else None,
                content_ratings=cr,
                sort=sort,
                year_from=year_from,
                year_to=year_to,
                return_meta=True
            )

            if is_sfw:
                raw_items = [it for it in raw_items if not is_nsfw_item(it)]

            results = [format_search_item(it) for it in raw_items]
            current_p = meta.get("page") or meta.get("currentPage") or page
            last_p = meta.get("lastPage") or meta.get("last_page") or page

            return {
                "results": results,
                "pagination": {
                    "current_page": current_p,
                    "last_page": last_p
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Manga search failed: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/manga/browse",
        tags=["Comix Manga API"],
        summary="Browse Manga (Newest by Default)"
    )
    def browse_manga(
        sfw: bool = Query(False, description="Filter out NSFW content"),
        nsfw: Optional[bool] = Query(None, description="Set to false to filter out NSFW content"),
        sort: Optional[str] = Query("newest", description="Sort order (default: 'newest')"),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=50, description="Items per page"),
        types: Optional[List[str]] = Query(None, alias="types[]"),
        type: Optional[str] = Query(None, description="Comic type filter (e.g. 'manga', 'manhwa')"),
        status: Optional[str] = Query(None, description="Status filter"),
        demographic: Optional[List[str]] = Query(None, alias="demographic[]"),
        demographics: Optional[str] = Query(None, description="Demographic filter")
    ):
        """Browse manga sorted by newest by default. Supports sfw/nsfw and custom sort filters."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        is_sfw = sfw or (nsfw is False)
        try:
            resolved_types = list(types) if types else []
            if type:
                resolved_types.extend([t.strip() for t in type.split(",") if t.strip()])

            resolved_demos = list(demographic) if demographic else []
            if demographics:
                resolved_demos.extend([d.strip() for d in demographics.split(",") if d.strip()])

            cr = ["safe", "suggestive"] if is_sfw else None
            raw_items, meta = api.search_titles(
                sort=sort or "newest",
                limit=limit,
                page=page,
                manga_type=resolved_types if resolved_types else None,
                status=status,
                demographics=resolved_demos if resolved_demos else None,
                content_ratings=cr,
                return_meta=True
            )
            if is_sfw:
                raw_items = [it for it in raw_items if not is_nsfw_item(it)]

            return {
                "results": [format_search_item(it) for it in raw_items],
                "pagination": {
                    "current_page": meta.get("page") or page,
                    "last_page": meta.get("lastPage") or page
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Browse failed: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/manga/filter",
        tags=["Comix Manga API"],
        summary="Filter Manga by Genres & Criteria"
    )
    def filter_manga(
        genres: Optional[str] = Query(None, description="Comma-separated genres, e.g. action,adventure"),
        genre: Optional[str] = Query(None, description="Alternative singular genre parameter"),
        genres_list: Optional[List[str]] = Query(None, alias="genres[]"),
        types: Optional[List[str]] = Query(None, alias="types[]"),
        type: Optional[str] = Query(None, description="Comic type filter"),
        status: Optional[str] = Query(None, description="Status filter"),
        demographic: Optional[List[str]] = Query(None, alias="demographic[]"),
        demographics: Optional[str] = Query(None, description="Demographic filter"),
        content_rating: Optional[List[str]] = Query(None, alias="content_rating[]"),
        sort: Optional[str] = Query(None, description="Sort order"),
        sfw: bool = Query(False, description="Filter out NSFW content"),
        nsfw: Optional[bool] = Query(None, description="Set to false to filter out NSFW content"),
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=50, description="Items per page")
    ):
        """Filter manga requiring specific criteria (e.g. genres). Supports sfw filter."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        is_sfw = sfw or (nsfw is False)
        try:
            resolved_genres = []
            if genres:
                resolved_genres.extend([g.strip() for g in genres.split(",") if g.strip()])
            if genre:
                resolved_genres.extend([g.strip() for g in genre.split(",") if g.strip()])
            if genres_list:
                resolved_genres.extend(genres_list)

            resolved_types = list(types) if types else []
            if type:
                resolved_types.extend([t.strip() for t in type.split(",") if t.strip()])

            resolved_demos = list(demographic) if demographic else []
            if demographics:
                resolved_demos.extend([d.strip() for d in demographics.split(",") if d.strip()])

            cr = content_rating
            if is_sfw and not cr:
                cr = ["safe", "suggestive"]

            raw_items, meta = api.search_titles(
                genres=resolved_genres if resolved_genres else None,
                manga_type=resolved_types if resolved_types else None,
                status=status,
                demographics=resolved_demos if resolved_demos else None,
                content_ratings=cr,
                sort=sort,
                limit=limit,
                page=page,
                return_meta=True
            )
            if is_sfw:
                raw_items = [it for it in raw_items if not is_nsfw_item(it)]

            return {
                "results": [format_search_item(it) for it in raw_items],
                "pagination": {
                    "current_page": meta.get("page") or page,
                    "last_page": meta.get("lastPage") or page
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Filter failed: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/manga/read",
        tags=["Comix Manga API"],
        summary="Read Chapter Images (Proxied)"
    )
    def read_chapter_images(
        chapterId: Optional[str] = Query(None, description="The specific ID of the chapter"),
        chapter_id: Optional[str] = Query(None, description="Alternative parameter for chapter ID")
    ):
        """Fetches CDN comic pages to render a chapter. All image URLs returned are wrapped in the local proxy."""
        cid = chapterId or chapter_id
        if not cid:
            raise HTTPException(status_code=400, detail="Missing required 'chapterId' query parameter.")

        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        try:
            api.bootstrap()
            chapter_data = api.get_chapter_images(cid)
            for img in chapter_data.get("images", []):
                raw_url = img.get("url")
                if raw_url:
                    img["url"] = proxy_image_url(raw_url)
            return chapter_data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch chapter images: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/chapter/{chapter_id}/pages",
        tags=["Comix Manga API"],
        summary="Decrypted Chapter Image URLs (Proxied)"
    )
    def get_chapter_pages_endpoint(chapter_id: str):
        """Fetch decrypted chapter image pages by chapter ID wrapped in image proxy."""
        return read_chapter_images(chapterId=chapter_id)

    @app.get(
        "/api/manga/collections/{id}",
        tags=["Comix Manga API"],
        summary="Manga Curated Collection"
    )
    def get_manga_collection_details(id: str):
        """Proxies public user-created collections from Comix.to and returns structured collection metadata and mapped manga items."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        try:
            collection_meta = api.get_collection(id)
            if not collection_meta:
                raise HTTPException(status_code=404, detail=f"Collection '{id}' not found.")

            raw_items = api.get_collection_items(id)
            results = []
            for it in raw_items:
                hid = it.get("hid", "")
                slug = it.get("slug", "")
                cid = f"{hid}-{slug}" if (hid and slug) else str(it.get("id") or hid or slug)
                img_url = get_item_image_url(it)
                ch_obj = it.get("latest_chapter") or it.get("chapter") or ""
                if isinstance(ch_obj, dict):
                    ch_str = f"Ch.{ch_obj.get('number', '')}"
                elif str(ch_obj).strip():
                    ch_str = str(ch_obj) if str(ch_obj).startswith("Ch.") else f"Ch.{ch_obj}"
                else:
                    ch_str = ""

                score_val = it.get("score") or it.get("rating")
                try:
                    score = float(score_val) if score_val is not None else 0.0
                except (ValueError, TypeError):
                    score = 0.0

                results.append({
                    "id": cid,
                    "slug": slug or cid,
                    "title": it.get("title", ""),
                    "img": proxy_image_url(img_url) if img_url else "",
                    "chapter": ch_str,
                    "status": it.get("status") or "releasing",
                    "score": score,
                    "type": it.get("type") or "manhwa"
                })

            return {
                "collection": {
                    "id": collection_meta.get("id", id),
                    "name": collection_meta.get("name") or collection_meta.get("title") or f"Collection #{id}",
                    "description": collection_meta.get("description", ""),
                    "itemCount": collection_meta.get("itemCount") or collection_meta.get("item_count") or len(results),
                    "likeCount": collection_meta.get("likeCount") or collection_meta.get("like_count") or 0,
                    "cover": collection_meta.get("cover") or {}
                },
                "results": results
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch collection: {str(e)}")
        finally:
            api.close()

    # ---------------------------------------------------------
    # Manga Details, Chapters, and Scanlation Groups
    # ---------------------------------------------------------
    @app.get(
        "/api/manga/{slug_or_id}",
        tags=["Manga Details"],
        summary="Comic Details & Metadata"
    )
    def get_manga_info(
        slug_or_id: str,
        sfw: bool = Query(False, description="Set to true to return 404 if the comic contains NSFW content")
    ):
        """Retrieve rich structured metadata for a manga title including posters, authors, tags, and external IDs."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI(slug_or_id, cookie_header=c_header)
        try:
            api.bootstrap()
            meta = api.metadata or {}

            if sfw and is_nsfw_item(meta):
                raise HTTPException(status_code=404, detail="Manga is classified as NSFW/mature and filtered out.")

            cover_url = proxy_image_url(get_item_image_url(meta))
            groups = api.get_manga_groups()
            scan_groups = [
                {
                    "scanlation_group_id": g.get("id"),
                    "name": g.get("name") or g.get("title")
                }
                for g in groups if isinstance(g, dict)
            ]

            raw_authors = meta.get("authors", [])
            authors_str = ", ".join((a.get("name") or a.get("title", "")) if isinstance(a, dict) else str(a) for a in raw_authors) if isinstance(raw_authors, list) else str(raw_authors)

            raw_artists = meta.get("artists", [])
            artists_str = ", ".join((a.get("name") or a.get("title", "")) if isinstance(a, dict) else str(a) for a in raw_artists) if isinstance(raw_artists, list) else str(raw_artists)

            raw_genres = meta.get("genres", [])
            genres_list = [(g.get("name") or g.get("title")) if isinstance(g, dict) else str(g) for g in raw_genres] if isinstance(raw_genres, list) else []

            demo_val = meta.get("demographic") or meta.get("demographics") or ""
            demo_str = demo_val.get("name", "") if isinstance(demo_val, dict) else str(demo_val)

            synopsis = meta.get("desc") or meta.get("synopsis") or meta.get("description") or ""

            comic_obj = {
                "id": api.manga_slug or slug_or_id,
                "title": api.manga_title or meta.get("title", ""),
                "cover": cover_url,
                "demographics": demo_str,
                "authors": authors_str,
                "artists": artists_str,
                "synopsis": synopsis,
                "genres": genres_list,
                "scanlation_groups": scan_groups
            }

            return {
                "comic": comic_obj,
                "title": api.manga_title,
                "slug": api.manga_slug,
                "hid": api.manga_hid,
                "metadata": api.metadata
            }
        except HTTPException:
            raise
        except Exception as e:
            raise_upstream_error(e, context=f"Manga '{slug_or_id}'")
        finally:
            api.close()

    @app.get(
        "/api/title/{slug_or_id}",
        tags=["Manga Details"],
        summary="Comic Details & Metadata (Alias)"
    )
    def get_title_info(
        slug_or_id: str,
        sfw: bool = Query(False, description="Set to true to return 404 if the comic contains NSFW content")
    ):
        """Alias for /api/manga/{slug_or_id}."""
        return get_manga_info(slug_or_id=slug_or_id, sfw=sfw)

    @app.get(
        "/api/manga/{slug_or_id}/chapters",
        tags=["Manga Details"],
        summary="Get Manga Chapters List"
    )
    def get_manga_chapters(
        slug_or_id: str,
        lang: str = Query("en", description="Filter chapter language (default: 'en')"),
        group: Optional[str] = Query(None, description="Filter by preferred scanlation group"),
        range: str = Query("all", description="Chapter range spec (e.g. 'all', '1-10', 'latest')"),
        page: int = Query(1, ge=1, description="Page number for pagination"),
        limit: int = Query(30, ge=1, le=100, description="Items per page"),
        scanlation_group_id: Optional[int] = Query(None, description="Scanlation group ID filter")
    ):
        """Fetch chapters for a comic title with quality deduplication, language and scanlation filters."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI(slug_or_id, cookie_header=c_header)
        try:
            api.bootstrap()
            if range == "all" and group is None and lang == "en":
                paginated = api.fetch_chapters_page(page=page, limit=limit, scanlation_group_id=scanlation_group_id)
                return {
                    "title": api.manga_title,
                    "total_available": paginated["pagination"]["total"],
                    "chapters": paginated["chapters"],
                    "pagination": paginated["pagination"]
                }

            # Downloader deduplicated mode
            downloader = ComixDownloader(
                target_url=slug_or_id,
                cookie_file=find_default_cookies(),
                lang=lang,
                preferred_group=group
            )
            try:
                downloader.api.bootstrap()
                raw_chapters = downloader.api.fetch_all_chapters()
                chapters = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec=range)
                return {
                    "title": downloader.api.manga_title,
                    "total_available": len(chapters),
                    "chapters": chapters
                }
            finally:
                downloader.api.close()
        except Exception as e:
            raise_upstream_error(e, context=f"Chapters for '{slug_or_id}'")
        finally:
            api.close()

    @app.get(
        "/api/title/{slug_or_id}/chapters",
        tags=["Manga Details"],
        summary="Get Manga Chapters List (Alias)"
    )
    def get_title_chapters(
        slug_or_id: str,
        lang: str = Query("en", description="Filter chapter language (default: 'en')"),
        group: Optional[str] = Query(None, description="Filter by preferred scanlation group"),
        range: str = Query("all", description="Chapter range spec (e.g. 'all', '1-10', 'latest')"),
        page: int = Query(1, ge=1, description="Page number for pagination"),
        limit: int = Query(30, ge=1, le=100, description="Items per page"),
        scanlation_group_id: Optional[int] = Query(None, description="Scanlation group ID filter")
    ):
        """Alias for /api/manga/{slug_or_id}/chapters."""
        return get_manga_chapters(
            slug_or_id=slug_or_id,
            lang=lang,
            group=group,
            range=range,
            page=page,
            limit=limit,
            scanlation_group_id=scanlation_group_id
        )

    @app.get(
        "/api/manga/{slug_or_id}/groups",
        tags=["Manga Details"],
        summary="List Available Scanlation Groups"
    )
    def get_manga_groups(slug_or_id: str):
        """List all scanlation groups and translation teams that contributed to this comic."""
        c_header = resolve_cookies()
        api = ComixAPI(slug_or_id, cookie_header=c_header)
        try:
            api.bootstrap()
            groups = api.get_manga_groups()
            return {
                "title": api.manga_title,
                "count": len(groups),
                "groups": groups
            }
        except Exception as e:
            raise_upstream_error(e, context=f"Groups for '{slug_or_id}'")
        finally:
            api.close()

    @app.get(
        "/api/title/{slug_or_id}/groups",
        tags=["Manga Details"],
        summary="List Available Scanlation Groups (Alias)"
    )
    def get_title_groups(slug_or_id: str):
        """Alias for /api/manga/{slug_or_id}/groups."""
        return get_manga_groups(slug_or_id=slug_or_id)

    # ---------------------------------------------------------
    # Legacy Discovery Routes (Backwards Compatibility)
    # ---------------------------------------------------------
    @app.get(
        "/api/search",
        tags=["Discovery"],
        summary="Search Manga with Rich Filters"
    )
    def search_manga(
        q: str = Query("", description="Keyword search query (e.g. 'Solo Leveling', 'Sword')"),
        type: Optional[str] = Query(None, description="Filter comic type: 'manga', 'manhwa', 'manhua', 'other'"),
        status: Optional[str] = Query(None, description="Filter status: 'releasing', 'finished', 'on_hiatus', 'discontinued'"),
        genres: Optional[str] = Query(None, description="Comma-separated genres, e.g. 'Action,Fantasy'"),
        genre: Optional[str] = Query(None, description="Singular genre filter alias"),
        demographics: Optional[str] = Query(None, description="Comma-separated demographics, e.g. 'shounen,seinen'"),
        demographic: Optional[str] = Query(None, description="Singular demographic filter alias"),
        sort: Optional[str] = Query(None, description="Sort order: 'views_7d:desc', 'chapter_updated_at:desc', 'score:desc'"),
        limit: int = Query(10, ge=1, le=50, description="Maximum number of titles to return")
    ):
        """Search titles by keyword and apply rich genre, demographic, and ranking filters."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        raw_genres = genres or genre
        raw_demos = demographics or demographic
        genre_list = [g.strip() for g in raw_genres.split(",")] if raw_genres else None
        demo_list = [d.strip() for d in raw_demos.split(",")] if raw_demos else None
        try:
            results = api.search_titles(
                keyword=q,
                manga_type=type,
                status=status,
                genres=genre_list,
                demographics=demo_list,
                sort=sort,
                limit=limit
            )
            return {
                "count": len(results),
                "items": results
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/trending",
        tags=["Discovery"],
        summary="Trending & Most Followed Manga"
    )
    def get_trending(
        trend_type: str = Query("trending", description="Discovery mode: 'trending' or 'follows'"),
        type: Optional[str] = Query(None, description="Discovery mode alias: 'trending' or 'follows'"),
        days: int = Query(1, description="Time window in days: 1, 7, or 30 (follows max: 7)"),
        limit: int = Query(10, ge=1, le=50, description="Maximum titles to return")
    ):
        """Retrieve real-time trending comics or most followed titles over a daily, weekly, or monthly window."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        active_type = type or trend_type
        try:
            results = api.get_top_titles(type_filter=active_type, days=days, limit=limit)
            return {
                "trend_type": active_type,
                "days": days,
                "count": len(results),
                "items": results
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch trending titles: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/collections/{collection_id}",
        tags=["Collections"],
        summary="Get Curated Collection Items"
    )
    def get_collection(collection_id: str):
        """Retrieve all comics inside a curated reading list or user collection."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        try:
            items = api.get_collection_items(collection_id)
            if not items:
                raise HTTPException(status_code=404, detail=f"Collection '{collection_id}' not found or empty.")
            return {
                "collection": collection_id,
                "count": len(items),
                "items": items
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch collection: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/collection/{id}",
        tags=["Collections"],
        summary="Get Curated Collection Items (Alias)"
    )
    def get_collection_alias(id: str):
        """Alias for /api/collections/{collection_id}."""
        return get_collection(collection_id=id)

    # ---------------------------------------------------------
    # User Library & History (Authenticated)
    # ---------------------------------------------------------
    @app.get(
        "/api/user/following",
        tags=["User Account"],
        summary="Get Bookmarked / Followed Titles"
    )
    def get_following_titles(
        folder: Optional[str] = Query(None, description="Folder filter: 'reading', 'completed', 'paused', 'dropped', 'planning'"),
        limit: int = Query(50, ge=1, le=100, description="Items per page")
    ):
        """Fetch all bookmarked series from your Comix.to account (requires session cookies)."""
        c_file = find_default_cookies()
        if not c_file:
            raise HTTPException(status_code=401, detail="Session cookies required. Place 'comix.to_cookies.txt' in working directory.")
        c_header = parse_cookie_file(c_file)
        api = ComixAPI("", cookie_header=c_header)
        try:
            following = api.get_following_titles(folder=folder, limit_per_page=limit)
            return {
                "count": len(following),
                "folder": folder or "all",
                "items": following
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch following titles: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/following",
        tags=["User Account"],
        summary="Get Bookmarked / Followed Titles (Alias)"
    )
    def get_following_titles_alias(
        folder: Optional[str] = Query(None, description="Folder filter: 'reading', 'completed', 'paused', 'dropped', 'planning'"),
        limit: int = Query(50, ge=1, le=100, description="Items per page")
    ):
        """Alias for /api/user/following."""
        return get_following_titles(folder=folder, limit=limit)

    @app.get(
        "/api/user/history",
        tags=["User Account"],
        summary="Get Reading History"
    )
    def get_user_history(
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=50, description="Items per page")
    ):
        """Fetch recently read titles and chapter progress from your account history."""
        c_file = find_default_cookies()
        if not c_file:
            raise HTTPException(status_code=401, detail="Session cookies required.")
        c_header = parse_cookie_file(c_file)
        api = ComixAPI("", cookie_header=c_header)
        try:
            history = api.get_user_history(page=page, limit=limit)
            return {
                "page": page,
                "count": len(history),
                "items": history
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch user history: {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/history",
        tags=["User Account"],
        summary="Get Reading History (Alias)"
    )
    def get_user_history_alias(
        page: int = Query(1, ge=1, description="Page number"),
        limit: int = Query(20, ge=1, le=50, description="Items per page")
    ):
        """Alias for /api/user/history."""
        return get_user_history(page=page, limit=limit)

    @app.get(
        "/api/user/export",
        tags=["User Account"],
        summary="Export Reading List (MAL, AniList, CSV, JSON)"
    )
    def export_bookmarks(
        format: str = Query("mal", description="Format type: 'mal' (XML), 'anilist' (JSON), 'csv', 'json', or 'txt'")
    ):
        """Export bookmarked reading list directly to MyAnimeList XML, AniList JSON, CSV, or raw JSON backup."""
        c_file = find_default_cookies()
        if not c_file:
            raise HTTPException(status_code=401, detail="Session cookies required for export.")
        c_header = parse_cookie_file(c_file)
        api = ComixAPI("", cookie_header=c_header)
        try:
            data = api.export_user_bookmarks(format_type=format)
            fmt_clean = format.strip().lower()
            if fmt_clean in ("mal", "myanimelist"):
                media_type = "application/xml; charset=utf-8"
            elif fmt_clean in ("anilist", "al", "json", "backup"):
                media_type = "application/json; charset=utf-8"
            elif fmt_clean == "csv":
                media_type = "text/csv; charset=utf-8"
            else:
                media_type = "text/plain; charset=utf-8"
            return Response(content=data, media_type=media_type)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
        finally:
            api.close()

    # ---------------------------------------------------------
    # Download Execution Routes
    # ---------------------------------------------------------
    @app.post(
        "/api/download/chapter",
        tags=["Downloader"],
        summary="Download Single Chapter (CBZ, PDF, EPUB)"
    )
    def download_chapter_endpoint(
        req: DownloadChapterRequest,
        background_tasks: BackgroundTasks
    ):
        """Trigger single chapter download and conversion to CBZ archive, PDF, or EPUB."""
        output_dir = Path("./downloads")
        downloader = ComixDownloader(
            target_url=req.manga,
            output_dir=str(output_dir),
            preferred_group=req.preferred_group,
            export_format=req.format
        )
        try:
            downloader.api.bootstrap()
            raw_chapters = downloader.api.fetch_all_chapters()

            def _match_ch(c, num):
                n = c.get("number")
                if n is None:
                    return False
                if n == num:
                    return True
                try:
                    return float(n) == float(num)
                except (ValueError, TypeError):
                    return False

            matching = [c for c in raw_chapters if _match_ch(c, req.chapter_number)]
            if not matching:
                raise HTTPException(status_code=404, detail=f"Chapter {req.chapter_number} not found for '{req.manga}'.")

            # Run download
            from .utils import sanitize_filename
            slug_or_title = downloader.api.manga_title or downloader.api.manga_slug or "manga"
            target_folder = output_dir / sanitize_filename(slug_or_title)
            target_folder.mkdir(parents=True, exist_ok=True)
            saved_file = downloader.download_chapter(matching[0], target_folder)

            if not saved_file or not saved_file.exists():
                raise HTTPException(status_code=500, detail="Failed to compile chapter document.")

            return {
                "success": True,
                "manga": downloader.api.manga_title,
                "chapter": req.chapter_number,
                "format": req.format,
                "file_name": saved_file.name,
                "file_path": str(saved_file.resolve()),
                "file_size_kb": saved_file.stat().st_size // 1024
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
        finally:
            downloader.api.close()

    @app.post(
        "/api/download/series",
        tags=["Downloader"],
        summary="Download Multiple Chapters or Full Series (CBZ, PDF, EPUB)"
    )
    def download_series_endpoint(
        req: DownloadSeriesRequest,
        background_tasks: BackgroundTasks
    ):
        """Trigger multi-chapter or series download and optional volume merge into CBZ, PDF, or EPUB."""
        output_dir = Path("./downloads")
        downloader = ComixDownloader(
            target_url=req.manga,
            output_dir=str(output_dir),
            preferred_group=req.preferred_group,
            export_format=req.format,
            merge_all=req.merge
        )
        try:
            downloader.api.bootstrap()
            raw_chapters = downloader.api.fetch_all_chapters()
            chapters = downloader.filter_and_deduplicate(raw_chapters, chapter_range_spec=req.chapter_range)
            if not chapters:
                raise HTTPException(status_code=404, detail=f"No chapters found matching range '{req.chapter_range}' for '{req.manga}'.")

            from .utils import sanitize_filename
            slug_or_title = downloader.api.manga_title or downloader.api.manga_slug or "manga"
            target_folder = output_dir / sanitize_filename(slug_or_title)
            target_folder.mkdir(parents=True, exist_ok=True)

            downloaded_files = []
            for ch in chapters:
                saved = downloader.download_chapter(ch, target_folder)
                if saved and saved.exists():
                    downloaded_files.append(saved)

            if not downloaded_files:
                raise HTTPException(status_code=500, detail="Failed to compile series chapters.")

            return {
                "success": True,
                "manga": downloader.api.manga_title or req.manga,
                "chapter_range": req.chapter_range,
                "format": req.format,
                "total_downloaded": len(downloaded_files),
                "folder_path": str(target_folder.resolve()),
                "files": [f.name for f in downloaded_files]
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Series download failed: {str(e)}")
        finally:
            downloader.api.close()

    return app


app = create_app()


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the Uvicorn ASGI server hosting ComixAPI with Swagger UI."""
    import uvicorn
    print("\n==========================================================")
    print("🚀 Starting ComixAPI Web Server with Swagger UI")
    print(f"📌 Swagger UI Documentation: http://{host}:{port}/docs")
    print(f"📌 ReDoc Documentation:      http://{host}:{port}/redoc")
    print("==========================================================\n")
    target_app = "src.server:app" if reload else app
    uvicorn.run(target_app, host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
