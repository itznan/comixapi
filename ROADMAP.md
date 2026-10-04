# ComixAPI Project Roadmap & Feature Status

A curated roadmap of implemented capabilities, architectural enhancements, and future ecosystem milestones for **ComixAPI**.

---

## 🚀 Status Overview

### ✅ Completed & Shipped

- [x] **Decoupled Playwright Session Worker & SessionBroker**: Asynchronous browser daemon (`src/browser_worker.py`) maintaining persistent browser profiles (`~/.cache/comixapi/profile`) to resolve Cloudflare Turnstile challenges and automatically refresh sessions in the background.
- [x] **TLS & Fingerprint Synchronization**: Dynamic engine version detection (`map_user_agent_to_impersonate`) ensuring `curl_cffi` requests match the exact TLS, HTTP/2, and User-Agent profile of the browser session.
- [x] **Client Security & Dynamic VM Emulation**: Embedded Node.js IPC bridge (`comix_signer.js`) for signature generation and response decryption.
- [x] **Single-Link & Chapter Downloader**: Resilient multithreaded image downloader with `aria2c` acceleration and automatic deduplication.
- [x] **Multi-Format Export (PDF, CBZ, EPUB)**: Support for PDF compilation, raw archive `.cbz` packaging, and standard `.epub` generation with embedded `ComicInfo.xml` and cover art.
- [x] **Curated Community Collections (`/collections`)**: Browse and batch-download curated community reading lists and staff picks with paginated item mappings.
- [x] **In-CLI Search & Filtering (`GET /api/v1/manga`)**: Full search by keyword, comic type (`manga`, `manhwa`, `manhua`), status, genres, demographics, and sorting.
- [x] **Trending & Top Discovery (`GET /api/v1/manga/top`)**: Real-time daily, weekly, and monthly trending and most-followed comic discovery endpoints.
- [x] **Account Library Sync (`GET /api/v1/user/following-titles`)**: Synchronizes personal Comix.to reading lists and tracks unread chapters.
- [x] **Bookmark & Library Export (`GET /api/v1/user/list-backup/export`)**: Direct exports to MyAnimeList XML (`mal`), AniList JSON (`anilist`), CSV (`csv`), and raw JSON backups.
- [x] **Interactive Swagger UI & Web API Server**: Built-in FastAPI application providing interactive OpenAPI documentation, Swagger UI (`/docs`), ReDoc (`/redoc`), and REST endpoints.
- [x] **Bypass CORS & CORP Image Proxy (`/api/image`)**: Built-in image proxy providing permissive cross-origin headers to safely embed manga pages and posters into web applications.
- [x] **SFW Content Filtering (`?sfw=true`)**: Single query parameter content filter to suppress mature/NSFW titles across `/home`, `/search`, `/browse`, `/filter`, and `/api/manga/{id}`.
- [x] **Comprehensive Test Suite**: 96 automated tests using `pytest` covering all modules, formats, API calls, cookie handling, and Web server endpoints.
- [x] **Automated 1-Click Session Initializer (`test/open_browser_profile.py`)**: Real Chrome launcher that automatically detects challenge clearance and serializes cookies to `comix.to_cookies.txt`.

---

## 📋 Planned Features & Production Enhancements

### 1. Distributed Redis Session Synchronization
- **Target Audience**: Multi-container and Kubernetes deployments.
- **Description**: Expand `SessionBroker` to distribute session tokens and clearance state across multiple load-balanced FastAPI instances via Redis Pub/Sub.
- **Key Capabilities**:
  - Centralized session invalidation broadcast across API nodes.
  - Dedicated singleton worker container refreshing state for all API replicas.

---

### 2. Webhook Notifications for Scheduled Library Sync
- **Target Audience**: Power users running `--sync` as a background daemon or recurring cron job on a home server or VPS.
- **Description**: Sends instant notifications whenever new chapters are found and downloaded.
- **Key Capabilities**:
  - Discord and Telegram webhook support (`--webhook <url>`).
  - Rich embed notifications containing:
    - Manga cover thumbnail.
    - Title name and link.
    - Number of newly downloaded chapters.
    - Execution summary (time elapsed, storage used).

---

### 3. Persistent Configuration File (`~/.comix.json` or `.comixrc`)
- **Target Audience**: Regular CLI and API users.
- **Description**: Avoids repeating command-line flags or environment variables on every run.
- **Key Capabilities**:
  - Store default preferences:
    ```json
    {
      "format": "cbz",
      "output_dir": "~/Manga",
      "concurrency": 12,
      "use_aria2": true,
      "cookie_file": "~/.config/comix/cookies.txt",
      "preferred_group": "AsuraScans",
      "webhook_url": "https://discord.com/api/webhooks/..."
    }
    ```

---

### 4. Standard Python Packaging & Global CLI (`pyproject.toml`)
- **Target Audience**: Anyone installing via `pip` or package managers.
- **Description**: Transform the repository into a standard PEP 517/621 Python package.
- **Key Capabilities**:
  - Install locally via `pip install -e .` or publish to PyPI.
  - Expose a clean global command `comix`:
    ```bash
    comix search "Solo Leveling"
    comix trending --days 7
    comix sync
    comix https://comix.to/title/...
    ```

---

### 5. Adaptive Rate Limiting & Bandwidth Throttling
- **Target Audience**: Users downloading massive series (100+ chapters) or on metered network connections.
- **Description**: Prevent IP blocks and respect server resources with gentle, configurable pacing.
- **Key Capabilities**:
  - `--rate-limit <mbps>`: Cap download throughput.
  - `--delay <seconds>`: Inter-chapter cooldown delay.
  - Exponential backoff retry handler on HTTP 429 (Too Many Requests).
