# ComixAPI

[![CI](https://github.com/itznan/comixapi/actions/workflows/ci.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/ci.yml)
[![CodeQL](https://github.com/itznan/comixapi/actions/workflows/codeql.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/codeql.yml)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

> **High-performance Python CLI downloader & scraper for comix.to manga, manhwa & webtoons. In-CLI search, library sync, ComicInfo.xml, and PDF generation.**

ComixAPI is a complete, dual-mode toolkit for **comix.to**:
1. **Interactive CLI Downloader**: High-speed multithreaded downloader with in-terminal search, reading list synchronization, aria2 acceleration, and automated `.cbz` / `.pdf` / `.epub` compilation with `ComicInfo.xml` metadata.
2. **Production REST API**: FastAPI web service featuring interactive **Swagger UI (/docs)**, ReDoc (/redoc), CORS/CORP image proxying, and asynchronous background compilation.

---

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
  - [1. CLI Downloader](#1-cli-downloader)
  - [2. REST API & Swagger UI](#2-rest-api--swagger-ui)
  - [3. Docker Compose](#3-docker-compose)
- [CLI Downloader Usage & Examples](#cli-downloader-usage--examples)
  - [Interactive Search](#interactive-search)
  - [Download by Title or Chapter URL](#download-by-title-or-chapter-url)
  - [CBZ, PDF, and EPUB Formats](#cbz-pdf-and-epub-formats)
  - [Sync Account Library](#sync-account-library)
  - [Export Bookmarks](#export-bookmarks)
- [CLI Command-Line Options](#cli-command-line-options)
- [REST API Endpoints Reference](#rest-api-endpoints-reference)
- [Media Server ComicInfo.xml Support](#media-server-comicinfoxml-support)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [License](#license)

---

## Features

- **Document Formats**: Export chapters as `.pdf` files, `.cbz` comic book archives, or `.epub` digital books.
- **Media Server ComicInfo.xml**: Automatically creates standard `ComicInfo.xml` metadata in every series directory for **Komga**, **Kavita**, and **Calibre**.
- **Interactive Terminal Search**: Search directly from terminal (`search <query>`) with instant number selection.
- **Trending & Discovery**: Discover daily, weekly, or monthly trending titles (`trending`).
- **Account Follows & Library Sync**: Scan your Comix.to bookmarks (`--sync`) and download newly released chapters.
- **Bookmark & Library Export**: Export reading lists to MyAnimeList (MAL XML), AniList (JSON), or CSV.
- **Smart Deduplication**: Automatically selects the highest-voted scanlation group to prevent duplicate chapter numbers.
- **Flexible Ranges**: Specify `-c 1-10`, `-c 1,3,5`, `-c latest`, or `-c 20+`.
- **Aria2 Acceleration**: Auto-detects and leverages `aria2c` for high-throughput parallel downloads.
- **Client Security Emulation**: Dynamic Node.js security VM bridge (`comix_signer.js`) for signature generation and token decryption.
- **Complete REST API**: FastAPI app with interactive OpenAPI/Swagger docs and image proxying.

---

## Quick Start

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/itznan/comixapi.git
   cd comixapi
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Ensure Node.js 18+ is installed on your system for client security VM computation).*

---

### 1. CLI Downloader

Run the downloader directly using `main.py` or `comix_downloader.py`:

```bash
# Search and download interactively
python main.py search "Solo Leveling"

# Or download a title directly
python main.py https://comix.to/title/example-comic -c 1-5 --cbz
```

---

### 2. REST API & Swagger UI

Launch the FastAPI web server:

```bash
python main.py --server
# or
uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
```

* **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc Documentation:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 3. Docker Compose

Run the entire API service in a production container with persistent storage:

```bash
docker compose up -d
```

---

## CLI Downloader Usage & Examples

### Interactive Search
```bash
python main.py search "Chainsaw Man"
```

### Download by Title or Chapter URL
```bash
# Download chapters 1 to 10
python main.py https://comix.to/title/example-comic -c 1-10

# Resume from a specific chapter onwards
python main.py https://comix.to/title/example-comic/12345-chapter-20 --from-here
```

### CBZ, PDF, and EPUB Formats
```bash
# Download as CBZ archives (standard for comic readers)
python main.py https://comix.to/title/example-comic --cbz

# Download all chapters as PDF and merge into a single volume
python main.py https://comix.to/title/example-comic -m
```

### Sync Account Library
```bash
# Sync reading list and download new unread chapters
python main.py --sync --unread-only
```

### Export Bookmarks
```bash
# Export bookmarks to MyAnimeList XML
python main.py --export-bookmarks mal
```

---

## CLI Command-Line Options

| Option | Short | Description | Default |
|---|---|---|---|
| `target` | | Comic URL / slug, or `search`, `trending`, `collection`, `sync` | *Required* |
| `--format` | | Document format (`pdf`, `cbz`, `epub`, `both`) | `pdf` |
| `--cbz` | | Shortcut to export chapters as `.cbz` archives | `False` |
| `--epub` | | Shortcut to export chapters as `.epub` books | `False` |
| `--chapters` | `-c` | Chapters to download (`all`, `1-5`, `1,3,5`, `latest`, `10+`) | `all` |
| `--merge` | `-m` | Merge chapters into one combined PDF or CBZ | `False` |
| `--sync` | | Check reading list and download new/missing chapters | `False` |
| `--unread-only` | | Only download unread chapters when syncing | `False` |
| `--folder` | | Filter reading list by folder (`reading`, `completed`, etc.) | `None` |
| `--export-bookmarks`| | Export reading list (`mal`, `anilist`, `csv`, `json`) | `mal` |
| `--trending` | | Browse trending titles (`--days 1`, `7`, `30`) | `False` |
| `--output` | `-o` | Output directory | `./downloads/{Title}` |
| `--lang` | `-l` | Filter chapters by language | `en` |
| `--threads` | `-t` | Concurrent download threads | `8` |
| `--aria2` | | Force use aria2c for accelerated downloading | Auto-detected |
| `--cookies` | | Path to cookie file for private/restricted titles | Auto-discovered |
| `--no-comicinfo` | | Disable generating ComicInfo.xml metadata | `False` |

---

## REST API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Redirects to interactive `/docs` Swagger UI |
| `GET` | `/api/health` | System health, cookie authentication, and aria2 accelerator status |
| `GET` | `/api/manga/home` | Frontpage popular, trending, and latest releases |
| `GET` | `/api/manga/search` | Search titles with advanced filters (genres, demographic, type, sort) |
| `GET` | `/api/manga/browse` | Paginated catalog browsing with sorting |
| `GET` | `/api/manga/filter` | Available genre, demographic, and type taxonomy mappings |
| `GET` | `/api/manga/{slug_or_id}` | Full comic metadata, tags, description, and external database links |
| `GET` | `/api/manga/{slug_or_id}/chapters` | Complete chapter list with scanlator groups and release timestamps |
| `GET` | `/api/manga/{slug_or_id}/groups` | All scanlation groups contributing to a title |
| `GET` | `/api/manga/read` | Fetch decrypted image URLs for direct in-browser reading |
| `GET` | `/api/manga/collections/{id}` | Curated community collections and reading lists |
| `GET` | `/api/trending` | Top trending comics over 1d, 7d, or 30d timeframes |
| `GET` | `/api/image` | Local CORS & CORP bypassing image proxy |
| `GET` | `/api/user/following` | Retrieve bookmarked reading list (requires session cookies) |
| `GET` | `/api/user/history` | Retrieve user reading history |
| `GET` | `/api/user/export` | Export reading list to MyAnimeList (MAL XML), AniList (JSON), or CSV |
| `POST` | `/api/download/chapter` | Trigger asynchronous background chapter compilation (`pdf`, `cbz`, `epub`) |

---

## Media Server ComicInfo.xml Support

Every downloaded series automatically includes a standardized `ComicInfo.xml` compatible with all major comic media servers:

```xml
<?xml version="1.0" encoding="utf-8"?>
<ComicInfo xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <Series>Solo Leveling</Series>
  <Writer>Chugong</Writer>
  <Penciller>DUBU (REDICE STUDIO)</Penciller>
  <Genre>Action, Fantasy</Genre>
  <Manga>YesAndRightToLeft</Manga>
</ComicInfo>
```

Compatible with:
* [Komga](https://komga.org/)
* [Kavita](https://www.kavitareader.com/)
* [Calibre](https://calibre-ebook.com/)

---

## Testing & Quality Assurance

Run the test suite with coverage:
```bash
pytest --cov=src --cov-report=term-missing
```

Format and check with Ruff:
```bash
ruff check .
```

All Pull Requests and commits to `main` are automatically validated by GitHub Actions across Python `3.10`, `3.11`, `3.12`, and `3.13`.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
