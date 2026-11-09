"""Unit tests for failed image handling: safe_name, make_preview, move_failed, and restore_moved."""

import csv
from pathlib import Path
from PIL import Image
import pytest

from src.failed_handler import safe_name, make_preview, move_failed, restore_moved


def test_safe_name():
    assert safe_name("Nguyễn Văn A") == "Nguyễn Văn A"
    assert safe_name('Trần/Thị:Lan*?') == "TrầnThịLan"
    assert safe_name("   Lê Văn C...  ") == "Lê Văn C"
    assert safe_name("A" * 100, max_len=60) == "A" * 60
    assert safe_name("") == ""
    assert safe_name(None) == ""


def test_make_preview(tmp_path: Path):
    img_file = tmp_path / "test_card.jpg"
    img = Image.new("RGB", (1200, 800), color=(200, 100, 50))
    img.save(img_file, format="JPEG")

    preview = make_preview(img_file, max_side=400)
    assert preview is not None
    assert max(preview.size) <= 400
    assert preview.size[0] == 400 or preview.size[1] == 400

    # Test cache returns same object or runs without error
    preview_cached = make_preview(img_file, max_side=400)
    assert preview_cached is not None


def test_move_and_restore_failed(tmp_path: Path):
    src_dir = tmp_path / "originals"
    src_dir.mkdir()
    f1 = src_dir / "IMG_0001.jpg"
    f2 = src_dir / "IMG_0002.png"

    Image.new("RGB", (100, 100), color=(10, 20, 30)).save(f1, format="JPEG")
    Image.new("RGB", (100, 100), color=(40, 50, 60)).save(f2, format="PNG")

    items = [
        (str(f1), "Nguyễn Văn A"),
        (str(f2), ""),  # unnamed
    ]

    dest_root = tmp_path / "retakes"
    progress_called = []

    def on_progress(i, total):
        progress_called.append((i, total))

    dest_dir, moved, errors = move_failed(items, dest_root, progress=on_progress)

    assert len(errors) == 0
    assert len(moved) == 2
    assert not f1.exists()
    assert not f2.exists()
    assert len(progress_called) == 2
    assert progress_called == [(1, 2), (2, 2)]

    # Check files in dest_dir
    moved_files = list(dest_dir.glob("*"))
    file_names = [p.name for p in moved_files]

    assert "001_Nguyễn Văn A.jpg" in file_names
    assert "002_unnamed_IMG_0002.png" in file_names
    assert "_moved_log.csv" in file_names

    # Check _moved_log.csv
    log_csv = dest_dir / "_moved_log.csv"
    with open(log_csv, encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 2
        assert reader[0]["original_path"] == str(f1)
        assert reader[0]["new_path"] == moved[str(f1)]

    # Now test restore_moved
    restored, restore_errors = restore_moved(log_csv)
    assert len(restore_errors) == 0
    assert len(restored) == 2

    # Verify files are restored back to originals
    assert f1.exists()
    assert f2.exists()
