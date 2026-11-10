"""Unit and integration tests for edge cases, button synchronization, and optimizations."""

from pathlib import Path
import tkinter as tk
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest
from PIL import Image

from src.failed_handler import (
    BatchMoveResult,
    get_unique_dest_path,
    make_preview,
    move_failed,
    read_image_unicode,
    restore_moved,
    to_long_path,
)
from src.gui import CCCDScannerApp
from src.parser import build_record
from src.qr_engine import CCCDQRScanner, get_thread_wechat_detector
from src.excel_exporter import export_records_to_excel, append_records_to_excel
import openpyxl


def test_filename_collisions_across_subfolders(tmp_path: Path):
    """
    Verify that files with identical filenames from different subfolders
    (e.g. batch_1/img.jpg and batch_2/img.jpg) do not overwrite each other.
    """
    root_scan = tmp_path / "scans"
    sub1 = root_scan / "Batch_1"
    sub2 = root_scan / "Batch_2"
    sub1.mkdir(parents=True)
    sub2.mkdir(parents=True)

    f1 = sub1 / "card.jpg"
    f2 = sub2 / "card.jpg"

    Image.new("RGB", (60, 60), color=(10, 20, 30)).save(f1, format="JPEG")
    Image.new("RGB", (60, 60), color=(40, 50, 60)).save(f2, format="JPEG")

    items = [
        (str(f1), "Nguyen Van A"),
        (str(f2), "Nguyen Van A"),
    ]

    dest_dir = tmp_path / "failed_out"
    result = move_failed(items, dest_dir, folder_name="failed_out", root_scan_dir=root_scan)

    assert len(result.errors) == 0
    assert len(result.moved) == 2
    assert result.moved[str(f1)] != result.moved[str(f2)]

    # Both moved files exist on disk with distinct names
    p1 = Path(result.moved[str(f1)])
    p2 = Path(result.moved[str(f2)])
    assert p1.exists()
    assert p2.exists()
    assert p1.name != p2.name


def test_get_unique_dest_path_collision_avoidance(tmp_path: Path):
    dest = tmp_path / "dest"
    dest.mkdir()
    src = tmp_path / "photo.jpg"
    src.touch()

    # Initial path
    cand1 = get_unique_dest_path(dest, src, preferred_stem="test")
    assert cand1.name == "test.jpg"
    cand1.touch()

    # Second path should get suffix _1
    cand2 = get_unique_dest_path(dest, src, preferred_stem="test")
    assert cand2.name == "test_1.jpg"
    cand2.touch()

    # Third path should get suffix _2
    cand3 = get_unique_dest_path(dest, src, preferred_stem="test")
    assert cand3.name == "test_2.jpg"


def test_avoid_recursive_ingest_of_failed_folder(tmp_path: Path):
    """
    Verify that files already residing in the destination folder are skipped cleanly.
    """
    dest = tmp_path / "Ảnh lỗi"
    dest.mkdir()
    already_inside = dest / "001_old_fail.jpg"
    already_inside.touch()

    items = [(str(already_inside), "")]
    result = move_failed(items, dest, folder_name="Ảnh lỗi")

    assert len(result.moved) == 0
    assert str(already_inside) in result.skipped
    assert already_inside.exists()


def test_to_long_path_extended_prefix():
    short_p = "C:\\test\\file.txt"
    assert to_long_path(short_p) == str(Path(short_p).resolve())

    long_p = "C:\\" + ("a" * 260) + "\\file.txt"
    converted = to_long_path(long_p)
    if openpyxl.__name__:  # on Windows
        import os
        if os.name == "nt":
            assert converted.startswith("\\\\?\\")


def test_safe_image_loading_and_zero_file_lock(tmp_path: Path):
    """
    Verify that reading images via read_image_unicode and make_preview releases
    the OS file lock immediately so the file can be moved/deleted right away.
    """
    img_path = tmp_path / "test_lock.png"
    cv2.imwrite(str(img_path), np.full((100, 100, 3), 120, dtype=np.uint8))

    # Read via OpenCV safe unicode helper
    img_cv = read_image_unicode(img_path)
    assert img_cv is not None
    assert img_cv.shape == (100, 100, 3)

    # Read preview via Pillow
    prev = make_preview(img_path, max_side=80)
    assert prev is not None

    # Immediate rename/unlink on Windows must NOT raise PermissionError [WinError 32]
    new_path = tmp_path / "test_lock_renamed.png"
    img_path.rename(new_path)
    assert new_path.exists()
    assert not img_path.exists()
    new_path.unlink()
    assert not new_path.exists()


def test_wechat_detector_thread_local_singleton():
    """
    Verify that multiple CCCDQRScanner instances in the same thread
    share the same underlying thread-local WeChat detector without reloading models.
    """
    scanner1 = CCCDQRScanner()
    scanner2 = CCCDQRScanner()

    det1 = scanner1.wechat_detector
    det2 = scanner2.wechat_detector

    # Both detectors must be identical thread-local reference
    assert det1 is det2
    assert det1 is get_thread_wechat_detector()


def test_qr_engine_caches_gray_between_fast_and_rescue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Verify scan_fast caches the loaded grayscale image and scan_rescue reuses it
    without reading from disk a second time.
    """
    scanner = CCCDQRScanner()
    img_path = tmp_path / "test_reuse.png"
    cv2.imwrite(str(img_path), np.full((100, 100), 150, dtype=np.uint8))

    # First call fast scan (will fail on blank image)
    res, note = scanner.scan_fast(img_path)
    assert res is None
    assert scanner._last_gray is not None
    assert scanner._last_path == img_path

    # Mock _load_grayscale so if called again it raises an error
    def fail_load(p):
        raise AssertionError("Disk read should not have been called again!")

    monkeypatch.setattr(scanner, "_load_grayscale", fail_load)

    # scan_rescue must reuse cached gray without calling _load_grayscale
    res_rescue, note_rescue = scanner.scan_rescue(img_path)
    assert res_rescue is None


def test_excel_single_pass_column_widths(tmp_path: Path):
    """
    Verify export_records_to_excel and append_records_to_excel correctly auto-fit column
    widths based on content in a single pass.
    """
    out_file = tmp_path / "test_single_pass.xlsx"
    active_cols = [
        {"key": "source_file", "label": "Tên file"},
        {"key": "full_name", "label": "Họ và tên"},
        {"key": "permanent_address", "label": "Địa chỉ thường trú"},
    ]
    records = [
        {
            "source_file": "card1.jpg",
            "full_name": "Nguyễn Văn A",
            "permanent_address": "Số 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP Hồ Chí Minh",
            "_is_error": False,
        }
    ]

    export_records_to_excel(records, active_cols, str(out_file))
    assert out_file.exists()

    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    # Column C (permanent_address) width should be expanded to fit the long address
    col_c_width = ws.column_dimensions["C"].width
    assert col_c_width > 30

    # Append records test
    records_append = [
        {
            "source_file": "card2.jpg",
            "full_name": "Trần Thị B",
            "permanent_address": "Xã Tân Bình, Huyện Vĩnh Cửu, Tỉnh Đồng Nai",
            "_is_error": False,
        }
    ]
    append_records_to_excel(records_append, active_cols, str(out_file))
    wb2 = openpyxl.load_workbook(str(out_file))
    ws2 = wb2.active
    assert ws2.max_row == 3


def test_gui_deduplicate_scanned_files(shared_root: tk.Tk, tmp_path: Path):
    """
    Verify that re-adding the same image file does not duplicate entries in app.records.
    """
    app = CCCDScannerApp(shared_root)

    img_file = tmp_path / "test_unique.jpg"
    Image.new("RGB", (50, 50), color=(10, 20, 30)).save(img_file, format="JPEG")

    app._start_scanning([img_file])
    assert len(app.records) == 1

    # Adding the exact same file again must be deduplicated
    app._start_scanning([img_file])
    assert len(app.records) == 1


def test_gui_button_state_synchronization(shared_root: tk.Tk):
    """
    Verify _update_action_button_states accurately synchronizes btn_move_toggle and btn_delete_failed.
    """
    app = CCCDScannerApp(shared_root)

    # 1. Initially no records -> move and delete-failed disabled
    app._update_action_button_states()
    assert "disabled" in app.btn_move_toggle.state()
    assert "disabled" in app.btn_delete_failed.state()

    # 2. Add an error record -> buttons become enabled
    rec = build_record(Path("fail.jpg"), None, "UNREADABLE")
    app.records = [rec]
    app._update_action_button_states()
    assert "!disabled" in app.btn_move_toggle.state() or "disabled" not in app.btn_move_toggle.state()
    assert "!disabled" in app.btn_delete_failed.state() or "disabled" not in app.btn_delete_failed.state()

    # 3. While scanning -> move button is disabled to prevent race conditions
    app.is_scanning = True
    app._update_action_button_states()
    assert "disabled" in app.btn_move_toggle.state()

    # 4. Finish scanning, mark moved -> button toggles to Undo state
    app.is_scanning = False
    app.has_moved_failed_images = True
    app._update_action_button_states()
    assert "Hoàn tác" in app.btn_move_toggle.cget("text")
    assert "!disabled" in app.btn_move_toggle.state() or "disabled" not in app.btn_move_toggle.state()
