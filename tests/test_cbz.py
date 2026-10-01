"""
Unit tests for CBZ and EPUB export formats and compilation.
"""

import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image

from src.pdf import build_cbz_from_urls, merge_cbz_files, build_epub_from_urls
from src.downloader.core import ComixDownloader


def create_dummy_image(path: Path, color: str = "blue"):
    im = Image.new("RGB", (100, 100), color=color)
    im.save(path, format="JPEG")
    im.close()


def test_build_cbz_from_urls(tmp_path):
    img1 = tmp_path / "page1.jpg"
    img2 = tmp_path / "page2.jpg"
    cover = tmp_path / "cover.jpg"
    create_dummy_image(img1, "red")
    create_dummy_image(img2, "green")
    create_dummy_image(cover, "yellow")

    cbz_out = tmp_path / "test_chapter.cbz"
    fake_urls = ["http://example.com/p1.jpg", "http://example.com/p2.jpg"]
    comicinfo = "<ComicInfo><Title>Test</Title></ComicInfo>"

    def mock_fetch(img_urls, temp_img_dir, **kwargs):
        temp_img_dir.mkdir(parents=True, exist_ok=True)
        p1 = temp_img_dir / "page_0000.jpg"
        p2 = temp_img_dir / "page_0001.jpg"
        create_dummy_image(p1, "red")
        create_dummy_image(p2, "green")
        return [("http://example.com/p1.jpg", p1), ("http://example.com/p2.jpg", p2)]

    with patch("src.pdf.fetch_chapter_images", side_effect=mock_fetch):
        success = build_cbz_from_urls(
            img_urls=fake_urls,
            cbz_path=cbz_out,
            cover_image_path=cover,
            comic_info_xml_str=comicinfo
        )
        assert success is True
        assert cbz_out.exists()

        # Verify contents of CBZ archive
        with zipfile.ZipFile(cbz_out, "r") as zf:
            names = zf.namelist()
            assert "000_cover.jpg" in names
            assert "ComicInfo.xml" in names
            assert "page_0000.jpg" in names
            assert "page_0001.jpg" in names
            assert zf.read("ComicInfo.xml").decode("utf-8") == comicinfo


def test_merge_cbz_files(tmp_path):
    cbz1 = tmp_path / "Ch1.cbz"
    cbz2 = tmp_path / "Ch2.cbz"
    cover = tmp_path / "cover.jpg"
    create_dummy_image(cover, "blue")

    img1 = tmp_path / "p1.jpg"
    create_dummy_image(img1, "white")

    # Create dummy Ch1.cbz
    with zipfile.ZipFile(cbz1, "w") as zf:
        zf.write(img1, arcname="page_0000.jpg")
        zf.writestr("ComicInfo.xml", "<ComicInfo><Number>1</Number></ComicInfo>")

    # Create dummy Ch2.cbz
    with zipfile.ZipFile(cbz2, "w") as zf:
        zf.write(img1, arcname="page_0000.jpg")
        zf.writestr("ComicInfo.xml", "<ComicInfo><Number>2</Number></ComicInfo>")

    merged_cbz = tmp_path / "Merged.cbz"
    success = merge_cbz_files(
        cbz_list=[cbz1, cbz2],
        final_cbz_path=merged_cbz,
        cover_image_path=cover,
        comic_info_xml_str="<ComicInfo><Title>Merged Series</Title></ComicInfo>"
    )

    assert success is True
    assert merged_cbz.exists()

    with zipfile.ZipFile(merged_cbz, "r") as zf:
        names = zf.namelist()
        assert "000_cover.jpg" in names
        assert "ComicInfo.xml" in names
        assert "ch001_page_0000.jpg" in names
        assert "ch002_page_0000.jpg" in names


def test_build_epub_from_urls(tmp_path):
    epub_out = tmp_path / "test_book.epub"
    fake_urls = ["http://example.com/p1.jpg"]

    def mock_fetch(img_urls, temp_img_dir, **kwargs):
        temp_img_dir.mkdir(parents=True, exist_ok=True)
        p1 = temp_img_dir / "page_0000.jpg"
        create_dummy_image(p1, "purple")
        return [("http://example.com/p1.jpg", p1)]

    with patch("src.pdf.fetch_chapter_images", side_effect=mock_fetch):
        success = build_epub_from_urls(
            img_urls=fake_urls,
            epub_path=epub_out,
            title="EPUB Comic Test",
            author="Author Name"
        )
        assert success is True
        assert epub_out.exists()

        with zipfile.ZipFile(epub_out, "r") as zf:
            names = zf.namelist()
            assert "mimetype" in names
            assert "META-INF/container.xml" in names
            assert "OEBPS/content.opf" in names
            assert "OEBPS/toc.xhtml" in names
            assert "OEBPS/images/page_0000.jpg" in names
            assert zf.read("mimetype") == b"application/epub+zip"


def test_downloader_cbz_integration(tmp_path):
    downloader = ComixDownloader(
        target_url="https://comix.to/title/test-manga",
        output_dir=str(tmp_path),
        export_format="cbz"
    )
    downloader.api.manga_title = "Test Manga"
    downloader.api.fetch_chapter_pages = MagicMock(return_value=["http://example.com/img1.jpg"])

    chapter = {"number": 1, "name": "Start", "hid": "ch1"}

    with patch("src.downloader.core.build_cbz_from_urls", return_value=True) as mock_cbz:
        # Create dummy file so exists() returns True
        saved = tmp_path / "Test Manga - Ch 001 - Start.cbz"
        saved.write_text("dummy cbz")

        res = downloader.download_chapter(chapter, tmp_path)
        assert res == saved
        assert mock_cbz.called
