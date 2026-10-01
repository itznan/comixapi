# Comix.to Unofficial PDF Downloader

A high-performance Python tool to download manga, manhwa, or comic series from **comix.to** as high-quality PDF files with a single link.

---

## Features

- **High-Res Cover Art & First-Page Embedding**: Automatically fetches official CDN high-res cover art (`cover.jpg`) and embeds it as the first page of complete merged volumes or chapter 1.
- **Media Server ComicInfo.xml Generation**: Automatically generates standard `ComicInfo.xml` metadata in every series directory with authors, artists, publishers, genres, tags, age ratings, community scores, and external links (MAL, AniList, MangaUpdates, MangaDex) for **Komga**, **Kavita**, and **Calibre**.
- **Interactive In-CLI Search**: Search Comix.to directly from your terminal (`search <query>`) with interactive number selection to download immediately without opening a browser.
- **Trending & "Top" Discovery**: Discover daily, weekly, or monthly trending (`trending`) and most followed (`--trend-type follows`) comics with instant download prompts.
- **Account Follows & Library Sync**: Automatically scan all bookmarked titles in your personal Comix.to reading list (`--sync`) and download newly released chapters.
- **Bookmark & Library Export**: Export your personal Comix.to reading list to MyAnimeList (MAL XML), AniList (JSON), or CSV (`--export-bookmarks`).
- **Advanced Filtering & Sorting**: Filter searches by comic type (`--type manhwa, manga, manhua`), status (`--status releasing, finished, on_hiatus`), and sort order (`--sort views_7d:desc, chapter_updated_at:desc, rated_score:desc`).
- **Direct Chapter URL & Resume**: Pass any title URL or a direct chapter URL (e.g. `https://comix.to/title/<slug>/<chapterId>-chapter-10`) with optional `--from-here` to download starting from that chapter onwards.
- **Scanlation Group Discovery**: Use `--list-groups` to inspect all scanlation groups that contributed to a title before downloading.
- **Client Security & Token Emulation**: Automatically detects comix.to's dynamic security VM and signs requests/decrypts responses using an embedded Node.js bridge.
- **Automatic Metadata & Asset Discovery**: Auto-extracts title, author, chapter list, CFG token, and the latest security bundle without manual configuration.
- **Smart Chapter Deduplication**: Comix.to hosts chapters from multiple scanlation groups. By default, the script selects the highest-quality/voted release for each chapter number to prevent duplicates.
- **Flexible Chapter Selection**: Download everything or specify ranges such as `-c 1-5`, `-c 1,3,5`, `-c latest`, or `-c 20+`.
- **High-Speed Concurrent Downloads**: Multithreaded image downloading with live progress bars via `tqdm`.
- **Aria2 Acceleration**: Auto-detects and leverages `aria2c` for high-throughput parallel image fetching when available.
- **Complete PDF Merging**: Option (`--merge`) to combine all downloaded chapters into a single volume PDF (`{Title} - Complete.pdf`).
- **Resilient & Resumable**: Skips already downloaded chapter PDFs automatically.

---

## Prerequisites

1. **Python 3.8+**
2. **Node.js 18+** (required on your system for client security token computation)
3. *(Optional)* **aria2c** (for accelerated multi-connection downloads)

---

## Installation

Clone or open the repository:
```bash
git clone https://github.com/itznan/comixapi.git
cd comixapi
```

Install Python dependencies:
```bash
pip install -r requirements.txt
```

---

## Project Structure

```
comixapi/
│
├── comix_downloader.py     # Main CLI entrypoint
├── main.py                 # Alternative entrypoint
├── comix_signer.js         # Node.js security VM bridge
├── comix.to_cookies.txt    # Session cookies for protected titles
├── requirements.txt        # Python package dependencies
│
└── src/                    # Modular Python package
    ├── __init__.py         # Package exports
    ├── config.py           # User-Agent, base URLs, genre/demographic mappings
    ├── cookies.py          # Cookie parsing and auto-discovery
    ├── utils.py            # Sanitization, chapter range parser, table formatting
    ├── bridge.py           # Node.js IPC bridge (sign & decrypt)
    ├── metadata.py         # ComicInfo.xml generation & high-res cover management
    ├── pdf.py              # Parallel image download & PDF compilation
    ├── api/                # API client & communication package
    │   ├── __init__.py     # Exposes ComixAPI
    │   ├── client.py       # Core HTTP client, CFG token extraction, session bootstrap
    │   ├── chapters.py     # Chapter listing, pagination, and page decryption
    │   ├── search.py       # Title search, trending discovery, and filters
    │   ├── collections.py  # Curated collections retrieval & pagination
    │   └── user.py         # User library, reading history, and bookmark exports
    └── downloader/         # Download orchestration package
        ├── __init__.py     # Exposes ComixDownloader
        ├── core.py         # Core download pipeline, deduplication, PDF creation
        ├── interactive.py  # Interactive search and trending CLI workflows
        ├── collections.py  # Curated collections batch downloader
        └── sync.py         # Library sync, tracking, and bookmark export
```

---

## Cookies / Authentication

If you need to access age-restricted (18+) or protected titles:
- Place your exported cookies file in the project directory as `comix.to_cookies.txt` or `cookies.txt` (Netscape HTTP Cookie format, exported from browser extensions like *Get cookies.txt LOCALLY* or *Cookie-Editor*).
- The script automatically discovers and uses `comix.to_cookies.txt` or `cookies.txt` if present.
- Alternatively, supply a custom cookie path using `--cookies path/to/your_cookies.txt`.

---

## Interactive Swagger UI & Web API Server

ComixAPI includes a high-performance REST API powered by FastAPI with built-in, interactive **Swagger UI** and **ReDoc**:

```bash
# Start the web server with Swagger UI (default: http://127.0.0.1:8000)
python comix_downloader.py server
python main.py server

# Run on custom port or interface
python comix_downloader.py server --host 0.0.0.0 --port 8000
```

Once running, navigate to **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)** in your web browser:
- 📌 **Swagger UI**: `http://127.0.0.1:8000/docs`
- 📌 **ReDoc**: `http://127.0.0.1:8000/redoc`
- 📌 **OpenAPI 3.1 JSON Specification**: `http://127.0.0.1:8000/openapi.json`

Interactive endpoints available in Swagger UI:
* **`GET /api/search`**: Query manga titles with keyword, genre, demographic, and sort filters.
* **`GET /api/trending`**: Discover top trending or most followed titles across 1, 7, or 30 days.
* **`GET /api/manga/{slug_or_id}`**: Structured metadata, high-res posters, authors, and external links.
* **`GET /api/manga/{slug_or_id}/chapters`**: Complete chapter list with scanlation deduplication.
* **`GET /api/manga/{slug_or_id}/groups`**: Scanlation groups that translated the title.
* **`GET /api/collections/{collection_id}`**: Retrieve items in curated community reading lists.
* **`GET /api/user/following`**: Personal bookmarked reading list with folder filtering (requires cookies).
* **`GET /api/user/history`**: User's recently read reading history.
* **`GET /api/user/export`**: Export library to MyAnimeList XML (`mal`), AniList JSON (`anilist`), CSV, or JSON backup.
* **`POST /api/download/chapter`**: Trigger on-demand chapter downloads in CBZ, PDF, or EPUB format.

---

## Usage

### 1. In-CLI Search & Interactive Download
Search titles on Comix.to with optional filters and select what to download directly in your terminal:
```bash
# Interactive search by keyword
python comix_downloader.py search "Solo Leveling"

# Filter by type (manhwa/manga/manhua) and status (releasing/finished/on_hiatus)
python comix_downloader.py search "Leveling" --type manhwa --status finished

# Filter by genres and demographics (e.g. action, fantasy, shounen, seinen)
python comix_downloader.py search "Solo" --genre action --demographic shounen
python comix_downloader.py search "Sword" --genres action,fantasy --demographics shounen,seinen

# Sort by weekly views, chapter updates, or ratings
python comix_downloader.py search "Leveling" --type manhwa --sort views_7d:desc

# Browse top manhwa without keyword
python comix_downloader.py search --type manhwa --sort views_7d:desc --limit 5

# Search and download chapters 1 to 5 merged into a single volume
python comix_downloader.py search "Solo Leveling" -c 1-5 --merge

# Scripting / non-interactive (print table of results without prompt)
python comix_downloader.py search "Solo Leveling" --limit 5 --no-interactive
```

### 2. Trending & "Top" Discovery
Show or download the most popular manga / manhwa of the day, week, or month:
```bash
# Discover top trending titles today
python comix_downloader.py trending --limit 10

# Discover top trending titles over the past 7 days
python comix_downloader.py trending --days 7 --limit 10

# Discover most followed titles
python comix_downloader.py trending --trend-type follows --days 7

# Auto-download all top 10 trending series today
python comix_downloader.py trending --days 1 --limit 10 --auto-download -c 1-3

# Trending with specific download options (e.g. merge chapters 1-5)
python comix_downloader.py trending -c 1-5 --merge

# Non-interactive script output (prints table of results without prompting)
python comix_downloader.py trending --days 1 --no-interactive
```

### 3. Account Follows, Library Sync & Bookmark Export
Manage and synchronize your personal reading list directly with your Comix.to account (*requires session cookies*):
```bash
# Scan followed titles and download all new/missing chapters
python comix_downloader.py sync
python comix_downloader.py --sync

# Sync only titles in your "Reading" folder
python comix_downloader.py sync --folder reading

# Only download unread chapters released after your last read chapter
python comix_downloader.py sync --unread-only

# Check for new releases without downloading (dry run)
python comix_downloader.py --sync --dry-run

# View all followed / bookmarked titles in your account
python comix_downloader.py following
python comix_downloader.py following --folder reading

# View recently read chapters from your account history
python comix_downloader.py history

# Export bookmarks to MyAnimeList XML format (MAL)
python comix_downloader.py --export-bookmarks mal

# Export bookmarks to AniList JSON format
python comix_downloader.py --export-bookmarks anilist

# Export bookmarks to CSV or full JSON backup
python comix_downloader.py --export-bookmarks csv
python comix_downloader.py --export-bookmarks json
```

### 4. Download Entire Series as Individual Chapter PDFs
```bash
python comix_downloader.py <URL_OR_SLUG>
```
*Example:*
```bash
python comix_downloader.py https://comix.to/title/<title-id-or-slug>
```

### 5. Download Specific Chapters or From a Chapter Onwards
```bash
# Download only chapters 1 to 5
python comix_downloader.py <URL_OR_SLUG> -c 1-5

# Download chapters 1, 3, and 7
python comix_downloader.py <URL_OR_SLUG> -c 1,3,7

# Download from chapter 10 onwards
python comix_downloader.py <URL_OR_SLUG> -c 10+

# Pass direct chapter URL and download starting from that chapter onwards
python comix_downloader.py https://comix.to/title/<slug>/<chapterId>-chapter-10 --from-here
```

### 6. Alternative Export Formats: CBZ & EPUB
Save chapters as ultra-fast comic archives (`.cbz`) or digital books (`.epub`) with embedded cover art and `ComicInfo.xml` metadata:
```bash
# Download series as CBZ comic archives (Mihon / Tachiyomi / Komga / Kavita compatible)
python comix_downloader.py <URL_OR_SLUG> --cbz

# Download specific chapters as CBZ
python comix_downloader.py <URL_OR_SLUG> -c 1-5 --cbz

# Merge all chapters into a single complete volume CBZ
python comix_downloader.py <URL_OR_SLUG> --cbz --merge

# Download as EPUB format
python comix_downloader.py <URL_OR_SLUG> --epub

# Download both PDF and CBZ formats simultaneously
python comix_downloader.py <URL_OR_SLUG> --format both
```

### 7. Merge All Chapters into a Single Volume
```bash
# Merge chapters into a single complete volume PDF
python comix_downloader.py <URL_OR_SLUG> --merge

# Merge chapters into a single complete volume CBZ
python comix_downloader.py <URL_OR_SLUG> --cbz --merge
```

### 8. Inspect and Filter Scanlation Groups
```bash
# List all scanlation groups that contributed to the series
python comix_downloader.py groups <URL_OR_SLUG>
python comix_downloader.py <URL_OR_SLUG> --list-groups

# Filter chapters by a specific group
python comix_downloader.py <URL_OR_SLUG> -g "<GroupName>"
```

### 9. Download Curated Collections & Reading Lists
Batch-download every comic in a curated reading list or user collection:
```bash
# Download an entire curated collection
python comix_downloader.py collection <collection-id-or-url>
python comix_downloader.py collection 123-top-10-dungeon-manhwa

# Preview series in a collection without downloading (Dry Run)
python comix_downloader.py collection 123 --dry-run

# Download collection with specific chapter options (e.g. only latest chapters)
python comix_downloader.py collection 123 -c latest
```

### 10. Custom Output Directory & High Concurrency
```bash
python comix_downloader.py <URL_OR_SLUG> -o ./downloads/series -t 12
```

---

## Command-Line Options

| Option | Short | Description | Default |
|---|---|---|---|
| `target` | | Comic URL / slug, or `search` / `trending` / `collection` / `groups` / `sync` / `following` / `history` | *Required* |
| `search_query` | | Search keyword, collection target, or export format | `None` |
| `--format` | | Document format (`pdf`, `cbz`, `epub`, `both`) | `pdf` |
| `--cbz` | | Shortcut to export chapters as `.cbz` comic archives | `False` |
| `--epub` | | Shortcut to export chapters as `.epub` digital books | `False` |
| `--collection` | | Curated collection URL or ID to batch download | `None` |
| `--sync` | | Check reading list and download new/missing chapters | `False` |
| `--unread-only` | | When syncing reading list, only download unread chapters | `False` |
| `--folder` | | Filter reading list by folder (`reading`, `completed`, `paused`, `dropped`, `planning`) | `None` |
| `--history` | | View recently read chapters from account history | `False` |
| `--dry-run` | | When syncing or downloading collections, preview without downloading | `False` |
| `--export-bookmarks`| | Export reading list (`mal`, `anilist`, `csv`, `json`) | `mal` |
| `--trending` | | Browse trending titles (flag alternative to `trending`) | `False` |
| `--days` | | Time window for trending titles in days (`1`, `7`, `30`) | `1` |
| `--trend-type` | | Trending discovery mode (`trending`, `follows`) | `trending` |
| `--type` | | Filter search by comic type (`manga`, `manhwa`, `manhua`, `other`) | `None` |
| `--status` | | Filter search by status (`releasing`, `finished`, `on_hiatus`, `discontinued`) | `None` |
| `--genre`, `--genres` | | Filter search by genre (`action`, `fantasy`, `romance`, `comedy`, etc.) | `None` |
| `--demographic`, `--demographics` | | Filter search by demographic (`shounen`, `seinen`, `shoujo`, `josei`) | `None` |
| `--sort` | | Sort search order (`views_7d:desc`, `chapter_updated_at:desc`, `score:desc`) | Relevance |
| `--limit` | | Maximum number of search/trending results to display | `10` |
| `--auto-download` | | Automatically batch download all top trending titles found | `False` |
| `--no-interactive`| | Print search/trending results table without download prompt | `False` |
| `--list-groups` | | Display all scanlation groups that translated the title | `False` |
| `--from-here` | | When passing a direct chapter URL, download from that chapter onwards | `False` |
| `--output` | `-o` | Output directory to store downloaded files | `./downloads/{Title}` |
| `--chapters` | `-c` | Chapters to download (`all`, `1-5`, `1,3,5`, `10+`) | `all` |
| `--merge` | `-m` | Merge all downloaded chapters into one combined PDF or CBZ | `False` |
| `--group` | `-g` | Filter by scanlation group name or ID | Best per chapter |
| `--lang` | `-l` | Filter chapters by language | `en` |
| `--threads` | `-t` | Number of concurrent image download threads | `8` |
| `--aria2` | | Force use aria2c for accelerated multi-connection downloading | Auto-detected |
| `--no-aria2` | | Disable aria2c and use standard Python threads | `False` |
| `--cookies` | | Path to cookie file | Auto-discovered |
| `--keep-images` | | Keep raw downloaded image files after compilation | `False` |
| `--cover` | | Download high-res cover poster and embed in PDF/CBZ | `True` |
| `--no-cover` | | Disable downloading and embedding cover art | `False` |
| `--cover-first` | | Insert cover art as the first page of every chapter document | `False` |
| `--no-comicinfo` | | Disable generating ComicInfo.xml metadata file | `False` |

