# ComixAPI Project Roadmap & Feature Proposals

A curated roadmap of high-value, legitimate features, architecture enhancements, and ecosystem integrations for **ComixAPI**.

---

## 🚀 Status Overview

### ✅ Completed & Shipped
- [x] **Client Security & Dynamic VM Emulation**: Embedded Node.js IPC bridge (`comix_signer.js`) for signature generation and response decryption.
- [x] **Single-Link & Chapter Downloader**: Resilient multithreaded image downloader with `aria2c` acceleration and automatic deduplication.
- [x] **Multi-Format Export (PDF, CBZ, EPUB)**: Support for PDF compilation, raw archive `.cbz` packaging, and standard `.epub` generation with embedded `ComicInfo.xml` and cover art.
- [x] **In-CLI Search & Filtering (`GET /api/v1/manga`)**: Full search by keyword, comic type (`manga`, `manhwa`, `manhua`), status, genres, demographics, and sorting with interactive CLI selection.
- [x] **Trending & Top Discovery (`GET /api/v1/manga/top`)**: Daily, weekly, and monthly trending and most-followed comic discovery with interactive download prompts.
- [x] **Curated Community Collections (`/collections`)**: Browse and batch-download curated community reading lists and staff picks.
- [x] **Account Library Sync (`GET /api/v1/user/following-titles`)**: Synchronizes your personal Comix.to reading list and downloads newly released or missing chapters.
- [x] **Bookmark & Library Export (`GET /api/v1/user/list-backup/export`)**: Direct exports to MyAnimeList XML (`mal`), AniList JSON (`anilist`), CSV (`csv`), and raw JSON backups.
- [x] **Interactive Swagger UI & Web API Server**: Built-in FastAPI application providing interactive OpenAPI documentation, Swagger UI (`/docs`), ReDoc (`/redoc`), and REST endpoints.
- [x] **Comprehensive Test Suite**: Automated tests using `pytest` covering all modules, formats, API calls, and Web server endpoints.
- [x] **Rich Terminal UI**: Formatted console tables via `rich` with automatic plain ASCII fallback.

---

## 📋 Planned Legitimate Features & Improvements

### 1. CBZ & EPUB Output Formats (Comic Reader Ecosystem)
- **Target Audience**: Users of *Komga*, *Kavita*, *CDisplayEx*, *Tachiyomi*, *Mihon*, and e-ink devices (*Kindle*, *Kobo*).
- **Description**: While PDF is great for desktop reading, `.cbz` (Comic Book Zip) is the gold standard for dedicated comic servers and reader apps.
- **Key Capabilities**:
  - Add `--format cbz` / `--format epub` flag (defaulting to `pdf`).
  - Bundle raw uncompressed/lossless images directly into a standard `.cbz` archive.
  - Automatically embed `ComicInfo.xml` metadata (series title, chapter number, writer, artist, genres, tags, synopsis, page count, and scanlation group).
  - Embed the series poster cover image as `cover.jpg` inside the archive.
  - Implement EPUB generation for e-ink devices with proper vertical and page-flip layouts.

---

### 2. Curated Community Collections (`/collections`)
- **Target Audience**: Readers looking to discover curated reading lists (e.g., *"Top 50 Cultivation Manhua"*, *"Best Psychological Thrillers"*).
- **Description**: Comix.to hosts user-curated collections with custom titles and comic groupings.
- **Key Capabilities**:
  - `python comix_downloader.py collection <url-or-id>`: View or download an entire curated collection.
  - `python comix_downloader.py collections`: Browse trending and popular community collections.
  - Batch download options with individual chapter selection and merged volume options.

---

### 3. Webhook Notifications for Scheduled Library Sync
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

### 4. Persistent Configuration File (`~/.comix.json` or `.comixrc`)
- **Target Audience**: All regular CLI users.
- **Description**: Avoids repeating command-line flags on every run.
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
  - CLI management commands:
    ```bash
    python comix_downloader.py config --set format=cbz
    python comix_downloader.py config --show
    ```

---

### 5. Standard Python Packaging & Global CLI (`pyproject.toml`)
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

### 6. Automated Unit Testing Suite (`pytest`)
- **Target Audience**: Developers, contributors, and CI systems.
- **Description**: Ensure code stability, regressions prevention, and automated validation.
- **Key Capabilities**:
  - Tests for chapter range parsing (`1-5`, `1,3,7`, `20+`, `all`).
  - Tests for filename sanitization across Windows, macOS, and Linux.
  - Tests for Netscape cookie file parsing and header injection.
  - Tests for URL and slug parsing (`/title/slug`, `/title/slug/ch-1`).
  - Tests for `ComicInfo.xml` generation and schema validation.
  - Mocked HTTP tests for API queries and pagination.

---

### 7. GitHub Actions Continuous Integration (CI/CD)
- **Target Audience**: Repository maintainers and open-source contributors.
- **Description**: Automated build verification on every pull request and push to `main`.
- **Key Capabilities**:
  - Multi-OS matrix testing (Ubuntu, Windows, macOS).
  - Python version matrix (3.8, 3.9, 3.10, 3.11, 3.12).
  - Node.js runtime verification for `comix_signer.js`.
  - Code quality checks via `ruff` or `flake8`.

---

### 8. Adaptive Rate Limiting & Bandwidth Throttling
- **Target Audience**: Users downloading massive series (100+ chapters) or on metered network connections.
- **Description**: Prevent IP blocks and respect server resources with gentle, configurable pacing.
- **Key Capabilities**:
  - `--rate-limit <mbps>`: Cap download throughput.
  - `--delay <seconds>`: Inter-chapter cooldown delay.
  - Exponential backoff retry handler on HTTP 429 (Too Many Requests).
