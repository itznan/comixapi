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
    │   └── user.py         # User library, reading history, and bookmark exports
    └── downloader/         # Download orchestration package
        ├── __init__.py     # Exposes ComixDownloader
        ├── core.py         # Core download pipeline, deduplication, PDF creation
        ├── interactive.py  # Interactive search and trending CLI workflows
        └── sync.py         # Library sync, tracking, and bookmark export
```

---

## Cookies / Authentication

If you need to access age-restricted (18+) or protected titles:
- Place your exported cookies file in the project directory as `comix.to_cookies.txt` or `cookies.txt` (Netscape HTTP Cookie format, exported from browser extensions like *Get cookies.txt LOCALLY* or *Cookie-Editor*).
- The script automatically discovers and uses `comix.to_cookies.txt` or `cookies.txt` if present.
- Alternatively, supply a custom cookie path using `--cookies path/to/your_cookies.txt`.

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

# Trending with specific download options (e.g. merge chapters 1-5)
python comix_downloader.py trending -c 1-5 --merge

# Non-interactive script output
python comix_downloader.py trending --days 1 --no-interactive
```

### 3. Account Follows, Library Sync & Bookmark Export
Manage and synchronize your personal reading list directly with your Comix.to account (*requires session cookies*):
```bash
# Scan followed titles and download all new/missing chapters
python comix_downloader.py sync
python comix_downloader.py --sync

# Check for new releases without downloading (dry run)
python comix_downloader.py --sync --dry-run

# View all followed / bookmarked titles in your account
python comix_downloader.py following

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

### 6. Merge All Chapters into a Single Volume PDF
```bash
python comix_downloader.py <URL_OR_SLUG> --merge
```

### 7. Inspect and Filter Scanlation Groups
```bash
# List all scanlation groups that contributed to the series
python comix_downloader.py <URL_OR_SLUG> --list-groups

# Filter chapters by a specific group
python comix_downloader.py <URL_OR_SLUG> -g "<GroupName>"
```

### 8. Custom Output Directory & High Concurrency
```bash
python comix_downloader.py <URL_OR_SLUG> -o ./downloads/series -t 12
```

---

## Command-Line Options

| Option | Short | Description | Default |
|---|---|---|---|
| `target` | | Comic URL / slug, or `search` / `trending` / `sync` / `following` | *Required* |
| `search_query` | | Search keyword or export format | `None` |
| `--sync` | | Check reading list and download new/missing chapters | `False` |
| `--dry-run` | | When syncing, inspect new chapters without downloading | `False` |
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
| `--no-interactive`| | Print search/trending results table without download prompt | `False` |
| `--list-groups` | | Display all scanlation groups that translated the title | `False` |
| `--from-here` | | When passing a direct chapter URL, download from that chapter onwards | `False` |
| `--output` | `-o` | Output directory to store downloaded PDFs | `./downloads/{Title}` |
| `--chapters` | `-c` | Chapters to download (`all`, `1-5`, `1,3,5`, `10+`) | `all` |
| `--merge` | `-m` | Merge all downloaded chapters into one combined PDF | `False` |
| `--group` | `-g` | Filter by scanlation group name or ID | Best per chapter |
| `--lang` | `-l` | Filter chapters by language | `en` |
| `--threads` | `-t` | Number of concurrent image download threads | `8` |
| `--aria2` | | Force use aria2c for accelerated multi-connection downloading | Auto-detected |
| `--no-aria2` | | Disable aria2c and use standard Python threads | `False` |
| `--cookies` | | Path to cookie file | Auto-discovered |
| `--keep-images` | | Keep raw downloaded image files after PDF creation | `False` |
| `--cover` | | Download high-res cover poster and embed in PDF | `True` |
| `--no-cover` | | Disable downloading and embedding cover art | `False` |
| `--cover-first` | | Insert cover art as the first page of every chapter PDF | `False` |
| `--no-comicinfo` | | Disable generating ComicInfo.xml metadata file | `False` |

