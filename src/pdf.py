"""
PDF compilation, image fetching, and document merging utilities.
Supports both ultra-fast aria2c batch downloading and multithreaded Python downloading.
"""

import time
import shutil
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
from PIL import Image

from .config import USER_AGENT, BASE_URL
from .utils import tqdm

try:
    import pymupdf
    HAS_PYMUPDF = True
except ImportError:
    try:
        import fitz as pymupdf
        HAS_PYMUPDF = True
    except ImportError:
        HAS_PYMUPDF = False


def is_aria2c_available() -> bool:
    """Check if aria2c binary exists in system PATH."""
    return shutil.which("aria2c") is not None


def download_single_image(img_url: str, save_path: Path, retries: int = 4) -> bool:
    """Download single image file using Python urllib with retries."""
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": BASE_URL
    }
    for attempt in range(retries):
        try:
            req = urllib.request.Request(img_url, headers=headers)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            save_path.write_bytes(data)
            return True
        except Exception:
            time.sleep(1.0 * (attempt + 1))
    return False


def download_images_aria2c(download_tasks: list, temp_dir: Path, concurrency: int = 16, desc: str = "Pages") -> bool:
    """Fast batch download using aria2c."""
    input_file = temp_dir / "_aria2_input.txt"
    temp_dir_str = str(temp_dir).replace("\\", "/")

    lines = []
    for url, path in download_tasks:
        lines.append(f"{url}")
        lines.append(f"  dir={temp_dir_str}")
        lines.append(f"  out={path.name}")
        lines.append(f"  header=User-Agent: {USER_AGENT}")
        lines.append(f"  header=Referer: {BASE_URL}")

    input_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "aria2c",
        "-i", str(input_file),
        "-j", str(concurrency),
        "-s", "4",
        "-x", "4",
        "--allow-overwrite=true",
        "--auto-file-renaming=false",
        "--console-log-level=warn",
        "--summary-interval=1",
        "--download-result=hide"
    ]

    print(f"[*] {desc}: Downloading with aria2c ({len(download_tasks)} pages, -j {concurrency})...")
    res = subprocess.run(cmd)
    try:
        input_file.unlink(missing_ok=True)
    except Exception:
        pass
    return res.returncode == 0


def build_pdf_from_urls(img_urls: list, pdf_path: Path, concurrency: int = 8,
                       use_aria2: bool = None, keep_images: bool = False,
                       desc: str = "Pages") -> bool:
    """Download images in parallel and compile them sequentially into a PDF file."""
    if not img_urls:
        return False

    temp_img_dir = pdf_path.parent / f".tmp_{pdf_path.stem}"
    temp_img_dir.mkdir(parents=True, exist_ok=True)

    download_tasks = []
    for i, url in enumerate(img_urls):
        ext = ".webp" if ".webp" in url else ".jpg"
        img_path = temp_img_dir / f"page_{i:04d}{ext}"
        download_tasks.append((url, img_path))

    # Determine downloader backend
    should_use_aria2 = is_aria2c_available() if use_aria2 is None else (use_aria2 and is_aria2c_available())

    if should_use_aria2:
        aria_concurrency = max(concurrency, 16)
        success = download_images_aria2c(download_tasks, temp_img_dir, concurrency=aria_concurrency, desc=desc)
        if not success:
            print("[!] aria2c reported non-zero exit; falling back to internal threads for remaining files...")
            should_use_aria2 = False

    if not should_use_aria2:
        # Fallback to Python ThreadPoolExecutor
        missing_tasks = [(url, path) for url, path in download_tasks if not path.exists() or path.stat().st_size == 0]
        if missing_tasks:
            with tqdm(total=len(download_tasks), desc=desc, unit="img", leave=False) as pbar:
                # Update progress for already downloaded files if any
                pbar.update(len(download_tasks) - len(missing_tasks))
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = {
                        executor.submit(download_single_image, url, path): path
                        for url, path in missing_tasks
                    }
                    for f in as_completed(futures):
                        f.result()
                        pbar.update(1)

    pil_images = []
    try:
        for _, img_path in download_tasks:
            if not img_path.exists() or img_path.stat().st_size == 0:
                continue
            try:
                im = Image.open(img_path)
                if im.mode != "RGB":
                    im = im.convert("RGB")
                pil_images.append(im)
            except Exception as e:
                print(f"[!] Warning: Could not decode image {img_path.name}: {e}")

        if not pil_images:
            return False

        pil_images[0].save(
            pdf_path,
            save_all=True,
            append_images=pil_images[1:],
            resolution=100.0,
            quality=95
        )
        return True

    finally:
        for im in pil_images:
            try:
                im.close()
            except Exception:
                pass
        if not keep_images and temp_img_dir.exists():
            shutil.rmtree(temp_img_dir, ignore_errors=True)


def merge_pdf_files(pdf_list: list, final_pdf_path: Path) -> bool:
    """Combine multiple chapter PDFs into a single complete volume PDF."""
    if not pdf_list:
        return False

    print(f"[*] Merging {len(pdf_list)} chapters into single PDF: {final_pdf_path.name}...")
    if HAS_PYMUPDF:
        doc_out = pymupdf.open()
        for p in pdf_list:
            with pymupdf.open(str(p)) as doc_in:
                doc_out.insert_pdf(doc_in)
        doc_out.save(str(final_pdf_path))
        doc_out.close()
        print(f"[OK] Merged complete PDF saved: {final_pdf_path} ({final_pdf_path.stat().st_size // (1024*1024)} MB)")
        return True
    else:
        print("[!] PyMuPDF is not installed. Skipping automatic merge.")
        return False
