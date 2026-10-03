# ComixAPI

[![CI](https://github.com/itznan/comixapi/actions/workflows/ci.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/ci.yml)
[![CodeQL](https://github.com/itznan/comixapi/actions/workflows/codeql.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/codeql.yml)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

> **High-performance FastAPI REST API & scraper service for comix.to manga, manhwa & webtoons. Interactive Swagger UI, CORS image proxy, and Docker ready.**

*Looking for the standalone terminal CLI tool? Check out [comix-downloader](https://github.com/itznan/comix-downloader).*

---

## Features

- **Interactive Documentation**: Auto-generated interactive **Swagger UI (`/docs`)** and **ReDoc (`/redoc`)**.
- **CORS & CORP Image Proxy**: Built-in `/api/image` endpoint that bypasses hotlinking restrictions and Cross-Origin Resource Policy (CORP) blocks for web readers.
- **Rich Catalogue & Metadata**: Search comics, browse categories, filter by genre/demographic/status, and retrieve full chapter indices.
- **Client Security Emulation**: Dynamic Node.js security VM bridge (`comix_signer.js`) for signature generation and token decryption.
- **SFW & NSFW Filtering**: Optional content filtering on homepage and search feeds for safe reader applications.
- **User Library Integration**: Endpoints to fetch bookmarks, reading history, and follows (using session cookies).
- **Docker & Production Ready**: Pre-configured `Dockerfile` and `docker-compose.yml` with multi-stage builds and automated testing.

---

## Quick Start

### 1. Run with Docker Compose (Recommended)

Start the production container with persistent caching in a single command:

```bash
docker compose up -d
```

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 2. Run Locally with Python

1. **Clone the repository:**
   ```bash
   git clone https://github.com/itznan/comixapi.git
   cd comixapi
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure Node.js 18+ is installed on your system for client security VM computation).*

3. **Start the API server:**
   ```bash
   python main.py
   # or with custom host/port:
   uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## REST API Endpoints Reference

All responses follow standard HTTP semantics with CORS enabled for frontend web apps.

### Core Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Redirects automatically to `/docs` (Swagger UI) |
| `GET` | `/api/health` | Service health status and system dependencies |
| `GET` | `/api/image?url=...` | High-speed CORS & CORP image proxy for web readers |

### Search & Discovery

| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/api/search` | `q`, `limit`, `type`, `status`, `genre`, `demographic`, `sort` | Search titles with flexible multi-field filtering |
| `GET` | `/api/trending` | `days` (1, 7, 30), `limit`, `type` (`trending`, `follows`) | Fetch trending and top-followed comics |
| `GET` | `/api/manga/home` | `nsfw` (`true`/`false`) | Formatted home feed (trending, latest updates, popular) |
| `GET` | `/api/manga/browse` | `page`, `limit`, `sort`, `type`, `nsfw` | Paginated catalogue browsing |
| `GET` | `/api/collection/{id}` | `page`, `limit` | Retrieve curated reading collections |

### Manga & Chapter Details

| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/api/title/{slug_or_id}` | | Full metadata, synopsis, authors, and genres |
| `GET` | `/api/title/{slug_or_id}/chapters` | `page`, `limit`, `lang`, `group` | List available chapters with scanlator groups |
| `GET` | `/api/chapter/{chapter_id}/pages` | | Decrypted high-resolution image URLs for a chapter |

### User Library (Requires Cookies)

| Method | Endpoint | Query Parameters | Description |
|---|---|---|---|
| `GET` | `/api/following` | `page`, `folder` | Get followed reading list (`reading`, `completed`, etc.) |
| `GET` | `/api/history` | `page` | Get user reading history |

---

## Interactive Documentation

Test queries, inspect request schemas, and execute live API calls directly from your browser:

* **Swagger UI:** `http://localhost:8000/docs`
* **ReDoc:** `http://localhost:8000/redoc`
* **OpenAPI Schema:** `http://localhost:8000/openapi.json`

---

## Configuration & Environment Variables

| Variable | Description | Default |
|---|---|---|
| `HOST` | Server bind interface | `0.0.0.0` |
| `PORT` | Server listen port | `8000` |
| `COOKIE_FILE` | Path to `comix.to_cookies.txt` for authenticated calls | Auto-discovered |

---

## Testing & Quality Assurance

Run the comprehensive test suite with coverage:

```bash
pytest -v --cov=src
```

Lint with Ruff:

```bash
ruff check .
```

---

## Related Projects

- **[comix-downloader](https://github.com/itznan/comix-downloader)**: Interactive CLI tool for searching, syncing libraries, and downloading `.cbz`, `.pdf`, and `.epub` archives with `ComicInfo.xml` metadata.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
