# Comix.to Unofficial PDF Downloader

A high-performance Python tool to download manga, manhwa, or comic series from **comix.to** as high-quality PDF files with a single link.

---

## Features

- **Single Link Downloading**: Pass any title URL (e.g. `https://comix.to/title/<title-slug>`) or slug to download all chapters automatically.
- **Client Security & Token Emulation**: Automatically detects comix.to's dynamic security VM and signs requests/decrypts responses using an embedded Node.js bridge.
- **Automatic Metadata & Asset Discovery**: Auto-extracts title, author, chapter list, CFG token, and the latest security bundle without manual configuration.
- **Smart Chapter Deduplication**: Comix.to hosts chapters from multiple scanlation groups. By default, the script selects the highest-quality/voted release for each chapter number to prevent duplicates.
- **Flexible Chapter Selection**: Download everything or specify ranges such as `-c 1-10`, `-c 1,3,5`, or `-c 20+`.
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
└── src/                    # Modular implementation
    ├── __init__.py         # Package exports
    ├── config.py           # User-Agent, base URLs, constants
    ├── cookies.py          # Cookie parsing and auto-discovery
    ├── utils.py            # Sanitization, chapter range parser, progress bar
    ├── bridge.py           # Node.js IPC bridge (sign & decrypt)
    ├── api.py              # Metadata fetching, chapter & page discovery
    ├── pdf.py              # Parallel image download & PDF compilation
    └── downloader.py       # High-level download orchestrator
```

---

## Cookies / Authentication

If you need to access age-restricted (18+) or protected titles:
- Place your exported cookies file in the project directory as `comix.to_cookies.txt` or `cookies.txt` (Netscape HTTP Cookie format, exported from browser extensions like *Get cookies.txt LOCALLY* or *Cookie-Editor*).
- The script automatically discovers and uses `comix.to_cookies.txt` or `cookies.txt` if present.
- Alternatively, supply a custom cookie path using `--cookies path/to/your_cookies.txt`.

---

## Usage

### 1. Download Entire Series as Individual Chapter PDFs
```bash
python comix_downloader.py <URL_OR_SLUG>
```
*Example:*
```bash
python comix_downloader.py https://comix.to/title/<title-id-or-slug>
```

### 2. Download Specific Chapters
```bash
# Download only chapters 1 to 5
python comix_downloader.py <URL_OR_SLUG> -c 1-5

# Download chapters 1, 3, and 7
python comix_downloader.py <URL_OR_SLUG> -c 1,3,7

# Download from chapter 10 onwards
python comix_downloader.py <URL_OR_SLUG> -c 10+
```

### 3. Merge All Chapters into a Single Volume PDF
```bash
python comix_downloader.py <URL_OR_SLUG> --merge
```

### 4. Filter by Scanlation Group
```bash
python comix_downloader.py <URL_OR_SLUG> -g "<GroupName>"
```

### 5. Custom Output Directory & High Concurrency
```bash
python comix_downloader.py <URL_OR_SLUG> -o ./downloads/series -t 12
```

---

## Command-Line Options

| Option | Short | Description | Default |
|---|---|---|---|
| `url` | | Comic URL or ID/slug (e.g. `https://comix.to/title/<title-id-or-slug>`) | *Required* |
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
