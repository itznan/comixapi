"""
FastAPI application for ComixAPI featuring interactive Swagger UI (/docs) and ReDoc (/redoc).
Provides REST endpoints for search, discovery, metadata, collections, user library, and document downloads.
"""

from typing import Optional, List, Any, Dict
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, status
from fastapi.responses import RedirectResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .api import ComixAPI
from .downloader import ComixDownloader
from .cookies import find_default_cookies, parse_cookie_file
from .pdf import is_aria2c_available


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance with Swagger UI."""
    app = FastAPI(
        title="ComixAPI",
        description="""
# 📚 ComixAPI — High-Performance Manga & Manhwa REST API

Welcome to the interactive **Swagger UI** for **ComixAPI**!
This RESTful service provides programmatic access to Comix.to resources:
* **🔍 Search & Browse**: Query manga by keywords, genre, demographic, and sort order.
* **🔥 Trending & Top Discovery**: Real-time daily, weekly, and monthly top charts.
* **📖 Metadata & Chapters**: Fetch title metadata, chapter lists, and scanlation teams.
* **📂 Curated Collections**: Discover and browse community-curated reading lists.
* **👤 User Library & Sync**: Access bookmarked series, reading history, and export to MAL/AniList/CSV.
* **⬇️ Document Downloads**: Download chapters in PDF, CBZ (Tachiyomi/Mihon compatible), and EPUB.
        """,
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
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
        has_cookies = bool(cookie_file and Path(cookie_file).exists() and Path(cookie_file).stat().st_size > 0)
        return {
            "status": "healthy",
            "version": "1.0.0",
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "aria2_accelerator": is_aria2c_available(),
            "authenticated_session": has_cookies,
            "cookie_file": cookie_file if has_cookies else None
        }

    # ---------------------------------------------------------
    # Search and Discovery Routes
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
        demographics: Optional[str] = Query(None, description="Comma-separated demographics, e.g. 'shounen,seinen'"),
        sort: Optional[str] = Query(None, description="Sort order: 'views_7d:desc', 'chapter_updated_at:desc', 'score:desc'"),
        limit: int = Query(10, ge=1, le=50, description="Maximum number of titles to return")
    ):
        """Search titles by keyword and apply rich genre, demographic, and ranking filters."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        genre_list = [g.strip() for g in genres.split(",")] if genres else None
        demo_list = [d.strip() for d in demographics.split(",")] if demographics else None
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
        days: int = Query(1, description="Time window in days: 1, 7, or 30 (follows max: 7)"),
        limit: int = Query(10, ge=1, le=50, description="Maximum titles to return")
    ):
        """Retrieve real-time trending comics or most followed titles over a daily, weekly, or monthly window."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI("", cookie_header=c_header)
        try:
            results = api.get_top_titles(type_filter=trend_type, days=days, limit=limit)
            return {
                "trend_type": trend_type,
                "days": days,
                "count": len(results),
                "items": results
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch trending titles: {str(e)}")
        finally:
            api.close()

    # ---------------------------------------------------------
    # Manga Details, Chapters, and Scanlation Groups
    # ---------------------------------------------------------
    @app.get(
        "/api/manga/{slug_or_id}",
        tags=["Manga Details"],
        summary="Get Manga Metadata & Info"
    )
    def get_manga_info(slug_or_id: str):
        """Retrieve rich structured metadata for a manga title including posters, authors, tags, and external IDs."""
        c_header = parse_cookie_file(find_default_cookies())
        api = ComixAPI(slug_or_id, cookie_header=c_header)
        try:
            api.bootstrap()
            return {
                "title": api.manga_title,
                "slug": api.manga_slug,
                "hid": api.manga_hid,
                "metadata": api.metadata
            }
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Failed to retrieve manga '{slug_or_id}': {str(e)}")
        finally:
            api.close()

    @app.get(
        "/api/manga/{slug_or_id}/chapters",
        tags=["Manga Details"],
        summary="Get Manga Chapters List"
    )
    def get_manga_chapters(
        slug_or_id: str,
        lang: str = Query("en", description="Filter chapter language (default: 'en')"),
        group: Optional[str] = Query(None, description="Filter by preferred scanlation group"),
        range: str = Query("all", description="Chapter range spec (e.g. 'all', '1-10', 'latest')")
    ):
        """Fetch all chapters for a comic title, deduplicated by scanlation quality and votes."""
        c_header = parse_cookie_file(find_default_cookies())
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
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch chapters: {str(e)}")
        finally:
            downloader.api.close()

    @app.get(
        "/api/manga/{slug_or_id}/groups",
        tags=["Manga Details"],
        summary="List Available Scanlation Groups"
    )
    def get_manga_groups(slug_or_id: str):
        """List all scanlation groups and translation teams that contributed to this comic."""
        c_header = parse_cookie_file(find_default_cookies())
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
            raise HTTPException(status_code=500, detail=f"Failed to fetch groups: {str(e)}")
        finally:
            api.close()

    # ---------------------------------------------------------
    # Curated Collections
    # ---------------------------------------------------------
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
            media_type = "application/xml" if format in ("mal", "myanimelist") else ("application/json" if format in ("anilist", "json") else "text/plain")
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
            matching = [c for c in raw_chapters if c.get("number") == req.chapter_number]
            if not matching:
                raise HTTPException(status_code=404, detail=f"Chapter {req.chapter_number} not found for '{req.manga}'.")

            # Run download
            target_folder = output_dir / downloader.api.manga_slug
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

    return app


app = create_app()


def start_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False):
    """Start the Uvicorn ASGI server hosting ComixAPI with Swagger UI."""
    import uvicorn
    print(f"\n==========================================================")
    print(f"🚀 Starting ComixAPI Web Server with Swagger UI")
    print(f"📌 Swagger UI Documentation: http://{host}:{port}/docs")
    print(f"📌 ReDoc Documentation:      http://{host}:{port}/redoc")
    print(f"==========================================================\n")
    uvicorn.run("src.server:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    start_server()
