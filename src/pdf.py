"""
Document export and compilation utilities for PDF, CBZ, and EPUB formats.
Supports both ultra-fast aria2c batch downloading and multithreaded Python downloading.
"""

import time
import shutil
import zipfile
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


def fetch_chapter_images(
    img_urls: list,
    temp_img_dir: Path,
    concurrency: int = 8,
    use_aria2: bool = None,
    desc: str = "Pages"
) -> list:
    """Download images to temporary directory using aria2c or ThreadPoolExecutor."""
    temp_img_dir.mkdir(parents=True, exist_ok=True)

    download_tasks = []
    for i, url in enumerate(img_urls):
        ext = ".webp" if ".webp" in url else ".jpg"
        img_path = temp_img_dir / f"page_{i:04d}{ext}"
        download_tasks.append((url, img_path))

    should_use_aria2 = is_aria2c_available() if use_aria2 is None else (use_aria2 and is_aria2c_available())

    if should_use_aria2:
        aria_concurrency = max(concurrency, 16)
        success = download_images_aria2c(download_tasks, temp_img_dir, concurrency=aria_concurrency, desc=desc)
        if not success:
            print("[!] aria2c reported non-zero exit; falling back to internal threads for remaining files...")
            should_use_aria2 = False

    if not should_use_aria2:
        missing_tasks = [(url, path) for url, path in download_tasks if not path.exists() or path.stat().st_size == 0]
        if missing_tasks:
            with tqdm(total=len(download_tasks), desc=desc, unit="img", leave=False) as pbar:
                pbar.update(len(download_tasks) - len(missing_tasks))
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    futures = {
                        executor.submit(download_single_image, url, path): path
                        for url, path in missing_tasks
                    }
                    for f in as_completed(futures):
                        f.result()
                        pbar.update(1)

    return download_tasks


def build_pdf_from_urls(
    img_urls: list,
    pdf_path: Path,
    concurrency: int = 8,
    use_aria2: bool = None,
    keep_images: bool = False,
    desc: str = "Pages",
    cover_image_path: Path = None
) -> bool:
    """Download images in parallel and compile them sequentially into a PDF file."""
    if not img_urls:
        return False

    temp_img_dir = pdf_path.parent / f".tmp_{pdf_path.stem}"
    download_tasks = fetch_chapter_images(
        img_urls=img_urls,
        temp_img_dir=temp_img_dir,
        concurrency=concurrency,
        use_aria2=use_aria2,
        desc=desc
    )

    pil_images = []
    try:
        if cover_image_path:
            c_path = Path(cover_image_path)
            if c_path.exists() and c_path.stat().st_size > 0:
                try:
                    c_im = Image.open(c_path)
                    if c_im.mode != "RGB":
                        c_im = c_im.convert("RGB")
                    pil_images.append(c_im)
                except Exception as ex:
                    print(f"[!] Warning: Could not decode cover image {c_path.name}: {ex}")

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


def merge_pdf_files(pdf_list: list, final_pdf_path: Path, cover_image_path: Path = None) -> bool:
    """Combine multiple chapter PDFs into a single complete volume PDF."""
    if not pdf_list:
        return False

    print(f"[*] Merging {len(pdf_list)} chapters into single PDF: {final_pdf_path.name}...")
    if HAS_PYMUPDF:
        doc_out = pymupdf.open()
        if cover_image_path:
            c_path = Path(cover_image_path)
            if c_path.exists() and c_path.stat().st_size > 0:
                try:
                    with pymupdf.open(str(c_path)) as c_doc:
                        pdf_bytes = c_doc.convert_to_pdf()
                        with pymupdf.open("pdf", pdf_bytes) as c_pdf:
                            doc_out.insert_pdf(c_pdf)
                except Exception as ex:
                    print(f"[!] Warning: Could not insert cover into merged PDF: {ex}")

        for p in pdf_list:
            with pymupdf.open(str(p)) as doc_in:
                doc_out.insert_pdf(doc_in)
        doc_out.save(str(final_pdf_path))
        doc_out.close()
        return final_pdf_path.exists()
    else:
        # Fallback using PIL
        pil_images = []
        try:
            if cover_image_path:
                c_path = Path(cover_image_path)
                if c_path.exists() and c_path.stat().st_size > 0:
                    c_im = Image.open(c_path).convert("RGB")
                    pil_images.append(c_im)

            for p in pdf_list:
                try:
                    im = Image.open(p)
                    for frame in range(getattr(im, "n_frames", 1)):
                        im.seek(frame)
                        pil_images.append(im.convert("RGB"))
                except Exception as ex:
                    print(f"[!] Warning: Could not read pages from {p.name}: {ex}")

            if not pil_images:
                return False

            pil_images[0].save(
                final_pdf_path,
                save_all=True,
                append_images=pil_images[1:],
                resolution=100.0
            )
            return final_pdf_path.exists()
        finally:
            for im in pil_images:
                try:
                    im.close()
                except Exception:
                    pass


def build_cbz_from_urls(
    img_urls: list,
    cbz_path: Path,
    concurrency: int = 8,
    use_aria2: bool = None,
    keep_images: bool = False,
    desc: str = "Pages",
    cover_image_path: Path = None,
    comic_info_xml_path: Path = None,
    comic_info_xml_str: str = None
) -> bool:
    """
    Download images and compile into a standard CBZ (.zip container) archive.
    Preserves original image fidelity (zero recompression overhead) and embeds ComicInfo.xml metadata.
    """
    if not img_urls:
        return False

    temp_img_dir = cbz_path.parent / f".tmp_{cbz_path.stem}"
    download_tasks = fetch_chapter_images(
        img_urls=img_urls,
        temp_img_dir=temp_img_dir,
        concurrency=concurrency,
        use_aria2=use_aria2,
        desc=desc
    )

    try:
        valid_files = [path for _, path in download_tasks if path.exists() and path.stat().st_size > 0]
        if not valid_files:
            return False

        cbz_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(cbz_path, "w", compression=zipfile.ZIP_STORED) as zf:
            # 1. Embed cover poster if provided
            if cover_image_path:
                c_path = Path(cover_image_path)
                if c_path.exists() and c_path.stat().st_size > 0:
                    ext = c_path.suffix or ".jpg"
                    zf.write(c_path, arcname=f"000_cover{ext}")

            # 2. Embed ComicInfo.xml metadata in root of CBZ for Tachiyomi/Mihon, Komga, Kavita
            if comic_info_xml_str:
                zf.writestr("ComicInfo.xml", comic_info_xml_str.encode("utf-8"))
            elif comic_info_xml_path:
                c_xml = Path(comic_info_xml_path)
                if c_xml.exists() and c_xml.stat().st_size > 0:
                    zf.write(c_xml, arcname="ComicInfo.xml")

            # 3. Add downloaded chapter images sequentially
            for p in sorted(valid_files, key=lambda x: x.name):
                zf.write(p, arcname=p.name)

        return cbz_path.exists() and cbz_path.stat().st_size > 0

    finally:
        if not keep_images and temp_img_dir.exists():
            shutil.rmtree(temp_img_dir, ignore_errors=True)


def merge_cbz_files(
    cbz_list: list,
    final_cbz_path: Path,
    cover_image_path: Path = None,
    comic_info_xml_path: Path = None,
    comic_info_xml_str: str = None
) -> bool:
    """Combine multiple chapter CBZ files into a single complete volume CBZ."""
    if not cbz_list:
        return False

    print(f"[*] Merging {len(cbz_list)} chapters into single CBZ: {final_cbz_path.name}...")
    final_cbz_path.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(final_cbz_path, "w", compression=zipfile.ZIP_STORED) as out_zf:
        if cover_image_path:
            c_path = Path(cover_image_path)
            if c_path.exists() and c_path.stat().st_size > 0:
                ext = c_path.suffix or ".jpg"
                out_zf.write(c_path, arcname=f"000_cover{ext}")

        if comic_info_xml_str:
            out_zf.writestr("ComicInfo.xml", comic_info_xml_str.encode("utf-8"))
        elif comic_info_xml_path:
            c_xml = Path(comic_info_xml_path)
            if c_xml.exists() and c_xml.stat().st_size > 0:
                out_zf.write(c_xml, arcname="ComicInfo.xml")

        for idx, cbz_file in enumerate(cbz_list, 1):
            p = Path(cbz_file)
            if not p.exists():
                continue
            with zipfile.ZipFile(p, "r") as in_zf:
                for item in in_zf.infolist():
                    if item.filename == "ComicInfo.xml" or "000_cover" in item.filename:
                        continue
                    arcname = f"ch{idx:03d}_{item.filename}"
                    out_zf.writestr(arcname, in_zf.read(item.filename))

    return final_cbz_path.exists()


def build_epub_from_urls(
    img_urls: list,
    epub_path: Path,
    concurrency: int = 8,
    use_aria2: bool = None,
    keep_images: bool = False,
    desc: str = "Pages",
    cover_image_path: Path = None,
    title: str = "Manga Chapter",
    author: str = "Unknown"
) -> bool:
    """Download images and compile into an EPUB 3 digital comic publication."""
    if not img_urls:
        return False

    temp_img_dir = epub_path.parent / f".tmp_{epub_path.stem}"
    download_tasks = fetch_chapter_images(
        img_urls=img_urls,
        temp_img_dir=temp_img_dir,
        concurrency=concurrency,
        use_aria2=use_aria2,
        desc=desc
    )

    try:
        valid_files = [path for _, path in download_tasks if path.exists() and path.stat().st_size > 0]
        if not valid_files:
            return False

        epub_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(epub_path, "w") as zf:
            # 1. mimetype (must be uncompressed at offset 0)
            zf.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. META-INF/container.xml
            container_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n'
                '  <rootfiles>\n'
                '    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>\n'
                '  </rootfiles>\n'
                '</container>'
            )
            zf.writestr("META-INF/container.xml", container_xml.encode("utf-8"))

            manifest_items = []
            spine_items = []
            ordered_pages = []

            # Optional Cover
            if cover_image_path:
                c_path = Path(cover_image_path)
                if c_path.exists() and c_path.stat().st_size > 0:
                    ext = c_path.suffix.lower()
                    mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
                    zf.write(c_path, arcname=f"OEBPS/images/cover{ext}")
                    manifest_items.append(f'    <item id="cover-img" href="images/cover{ext}" media-type="{mime}" properties="cover-image"/>')
                    cover_xhtml = (
                        '<?xml version="1.0" encoding="utf-8"?>\n'
                        '<!DOCTYPE html>\n'
                        '<html xmlns="http://www.w3.org/1999/xhtml">\n'
                        '<head><title>Cover</title><style>body{margin:0;padding:0;text-align:center;}img{max-width:100%;height:auto;}</style></head>\n'
                        f'<body><img src="images/cover{ext}" alt="Cover"/></body>\n'
                        '</html>'
                    )
                    zf.writestr("OEBPS/cover.xhtml", cover_xhtml.encode("utf-8"))
                    manifest_items.append('    <item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>')
                    spine_items.append('    <itemref idref="cover-page"/>')

            # Add Image Pages
            for idx, p in enumerate(sorted(valid_files, key=lambda x: x.name), 1):
                ext = p.suffix.lower()
                mime = "image/webp" if ext == ".webp" else ("image/png" if ext == ".png" else "image/jpeg")
                zf.write(p, arcname=f"OEBPS/images/{p.name}")
                manifest_items.append(f'    <item id="img_{idx:04d}" href="images/{p.name}" media-type="{mime}"/>')

                page_xhtml = (
                    '<?xml version="1.0" encoding="utf-8"?>\n'
                    '<!DOCTYPE html>\n'
                    '<html xmlns="http://www.w3.org/1999/xhtml">\n'
                    f'<head><title>Page {idx}</title><style>body{{margin:0;padding:0;text-align:center;}}img{{max-width:100%;height:auto;}}</style></head>\n'
                    f'<body><img src="images/{p.name}" alt="Page {idx}"/></body>\n'
                    '</html>'
                )
                page_name = f"page_{idx:04d}.xhtml"
                zf.writestr(f"OEBPS/{page_name}", page_xhtml.encode("utf-8"))
                manifest_items.append(f'    <item id="page_{idx:04d}" href="{page_name}" media-type="application/xhtml+xml"/>')
                spine_items.append(f'    <itemref idref="page_{idx:04d}"/>')
                ordered_pages.append((idx, page_name))

            # Table of Contents
            toc_xhtml = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<!DOCTYPE html>\n'
                '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
                f'<head><title>{title}</title></head>\n'
                '<body>\n'
                '  <nav epub:type="toc" id="toc">\n'
                f'    <h1>{title}</h1>\n'
                '    <ol>\n'
                f'      <li><a href="{ordered_pages[0][1]}">Start Reading</a></li>\n'
                '    </ol>\n'
                '  </nav>\n'
                '</body>\n'
                '</html>'
            )
            zf.writestr("OEBPS/toc.xhtml", toc_xhtml.encode("utf-8"))
            manifest_items.append('    <item id="toc" href="toc.xhtml" media-type="application/xhtml+xml" properties="nav"/>')

            # content.opf
            content_opf = (
                '<?xml version="1.0" encoding="utf-8"?>\n'
                '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="pub-id">\n'
                '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
                f'    <dc:identifier id="pub-id">urn:uuid:comix-{int(time.time())}</dc:identifier>\n'
                f'    <dc:title>{title}</dc:title>\n'
                f'    <dc:creator>{author}</dc:creator>\n'
                '    <dc:language>en</dc:language>\n'
                f'    <meta property="dcterms:modified">{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}</meta>\n'
                '  </metadata>\n'
                '  <manifest>\n'
                + "\n".join(manifest_items) + "\n"
                '  </manifest>\n'
                '  <spine>\n'
                + "\n".join(spine_items) + "\n"
                '  </spine>\n'
                '</package>'
            )
            zf.writestr("OEBPS/content.opf", content_opf.encode("utf-8"))

        return epub_path.exists() and epub_path.stat().st_size > 0

    finally:
        if not keep_images and temp_img_dir.exists():
            shutil.rmtree(temp_img_dir, ignore_errors=True)
