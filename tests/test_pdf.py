"""
Unit tests for PDF compilation and cover art insertion.
"""

import sys
from pathlib import Path
from PIL import Image
import pytest

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pdf import merge_pdf_files, HAS_PYMUPDF
if HAS_PYMUPDF:
    import pymupdf


def create_dummy_pdf(path: Path, num_pages: int = 1, color: str = "white"):
    images = [Image.new("RGB", (100, 100), color=color) for _ in range(num_pages)]
    images[0].save(path, save_all=True, append_images=images[1:], resolution=100.0)
    for im in images:
        im.close()


def create_dummy_image(path: Path, color: str = "blue"):
    im = Image.new("RGB", (120, 180), color=color)
    im.save(path, format="JPEG")
    im.close()


def test_merge_pdf_files_with_cover(tmp_path):
    if not HAS_PYMUPDF:
        pytest.skip("PyMuPDF not installed")

    ch1_pdf = tmp_path / "Ch1.pdf"
    ch2_pdf = tmp_path / "Ch2.pdf"
    cover_img = tmp_path / "cover.jpg"
    merged_pdf = tmp_path / "Merged.pdf"

    create_dummy_pdf(ch1_pdf, num_pages=2, color="red")
    create_dummy_pdf(ch2_pdf, num_pages=3, color="green")
    create_dummy_image(cover_img, color="blue")

    success = merge_pdf_files(
        pdf_list=[ch1_pdf, ch2_pdf],
        final_pdf_path=merged_pdf,
        cover_image_path=cover_img
    )
    assert success is True
    assert merged_pdf.exists()

    # Total pages: 1 (cover) + 2 (ch1) + 3 (ch2) = 6 pages
    with pymupdf.open(str(merged_pdf)) as doc:
        assert doc.page_count == 6


def test_merge_pdf_files_without_cover(tmp_path):
    if not HAS_PYMUPDF:
        pytest.skip("PyMuPDF not installed")

    ch1_pdf = tmp_path / "Ch1.pdf"
    ch2_pdf = tmp_path / "Ch2.pdf"
    merged_pdf = tmp_path / "Merged_No_Cover.pdf"

    create_dummy_pdf(ch1_pdf, num_pages=2)
    create_dummy_pdf(ch2_pdf, num_pages=3)

    success = merge_pdf_files(
        pdf_list=[ch1_pdf, ch2_pdf],
        final_pdf_path=merged_pdf,
        cover_image_path=None
    )
    assert success is True
    with pymupdf.open(str(merged_pdf)) as doc:
        assert doc.page_count == 5
