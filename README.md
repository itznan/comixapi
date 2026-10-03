# ComixAPI

[![CI](https://github.com/itznan/comixapi/actions/workflows/ci.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/ci.yml)
[![CodeQL](https://github.com/itznan/comixapi/actions/workflows/codeql.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/codeql.yml)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

High-performance, async-ready REST API and CLI toolkit for **comix.to**. Features interactive **Swagger UI / ReDoc**, full metadata extraction with **ComicInfo.xml** media server integration (Komga, Kavita, Calibre), **CBZ / PDF / EPUB** document compilation, multi-threaded downloads, and dynamic client-token security signing.

---

## Table of Contents
- [Quick Start](#quick-start)
  - [Run with Docker Compose (Recommended)](#run-with-docker-compose-recommended)
  - [Run Locally](#run-locally)
- [REST API Endpoints](#rest-api-endpoints)
- [CLI Downloader Features](#cli-downloader-features)
- [CLI Examples & Usage](#cli-examples--usage)
- [Command-Line Options Reference](#command-line-options-reference)
- [Media Server & ComicInfo.xml Support](#media-server--comicinfoxml-support)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [License](#license)

---

## Quick Start

### Run with Docker Compose (Recommended)

Start the production-ready API container with a single command:

```bash
docker compose up -d
```

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

Downloaded files and cached chapters persist in `./downloads`.

---

### Run Locally

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
   python main.py --server
   # or
   uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Or run the CLI downloader:**
   ```bash
   python main.py search "Solo Leveling"
   ```

---

## REST API Endpoints

All responses follow standard HTTP semantics with CORS & CORP enabled for web applications.

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

## CLI Downloader Features

- **Document Formats**: Export chapters as `.cbz` comic archives, `.pdf` files, or `.epub` books.
- **Media Server ComicInfo.xml**: Automatically generates standard `ComicInfo.xml` metadata in every series directory for **Komga**, **Kavita**, and **Calibre**.
- **Interactive Terminal Search**: Search directly from terminal (`search <query>`) with instant number selection.
- **Trending Discovery**: Browse trending titles by views or follows (`trending --trend-type follows`).
- **Account Follows & Library Sync**: Automatically check bookmarked reading lists (`--sync`) and download new chapters.
- **Smart Deduplication**: Automatically picks the highest-voted scanlation group to prevent duplicate chapter numbers.
- **Flexible Ranges**: Specify `-c 1-10`, `-c 1,3,5`, `-c latest`, or `-c 20+`.
- **Aria2 Acceleration**: Automatically accelerates multi-connection parallel image downloads when `aria2c` is present.
- **Merged Volume Support**: `--merge` compiles multiple chapters into a unified volume.

---

## CLI Examples & Usage

### 1. Interactive Search
```bash
python main.py search "Solo Leveling"
```

### 2. Download Chapters as CBZ or PDF
```bash
# Download chapters 1 to 5 as CBZ comic archives
python main.py https://comix.to/title/example-comic -c 1-5 --cbz

# Download all chapters as PDF and merge into a single complete volume
python main.py https://comix.to/title/example-comic -m
```

### 3. Sync Reading List
```bash
# Scan bookmarks and download newly released unread chapters
python main.py --sync --unread-only
```

### 4. Export Bookmarks
```bash
# Export bookmarks to MyAnimeList XML
python main.py --export-bookmarks mal
```

---

## Command-Line Options Reference

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
| `--cookies` | | Path to cookie file for private titles | Auto-discovered |
| `--no-comicinfo` | | Disable generating ComicInfo.xml metadata | `False` |

---

## Media Server & ComicInfo.xml Support

Every series download automatically includes a standardized `ComicInfo.xml` compatible with all major comic media servers:

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
