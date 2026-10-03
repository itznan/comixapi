# ComixAPI

[![CI](https://github.com/itznan/comixapi/actions/workflows/ci.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/ci.yml)
[![CodeQL](https://github.com/itznan/comixapi/actions/workflows/codeql.yml/badge.svg)](https://github.com/itznan/comixapi/actions/workflows/codeql.yml)
![Python Versions](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688.svg?logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/docker-ready-2496ED.svg?logo=docker&logoColor=white)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Production-grade, asynchronous REST API for **comix.to**. Features interactive **Swagger UI & ReDoc**, catalog search & discovery, full metadata extraction with **ComicInfo.xml** media server integration (Komga, Kavita, Calibre), asynchronous **CBZ / PDF / EPUB** document compilation, image proxying, and automated security token computation.

> Looking for the standalone command-line downloader? Check out [comix-downloader](../comix-downloader).

---

## Table of Contents
- [Quick Start](#quick-start)
  - [Run with Docker Compose (Recommended)](#run-with-docker-compose-recommended)
  - [Run Locally](#run-locally)
- [REST API Endpoints](#rest-api-endpoints)
- [Interactive API Documentation](#interactive-api-documentation)
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

Downloaded documents and cached images persist in `./downloads`.

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
   python main.py
   # or
   uvicorn src.server:app --host 0.0.0.0 --port 8000 --reload
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

## Interactive API Documentation

Once the server is running, explore the interactive documentation:

* **Swagger UI:** `http://localhost:8000/docs`
  * Test queries, inspect response schemas, and execute requests directly from the browser.
* **ReDoc:** `http://localhost:8000/redoc`
  * Clean, comprehensive, and searchable API documentation.

---

## Media Server & ComicInfo.xml Support

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
