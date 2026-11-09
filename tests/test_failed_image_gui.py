"""GUI feature tests for Split View (Passed / Failed), Hover Preview, and Move/Restore."""

from pathlib import Path
import tkinter as tk
import pytest
from PIL import Image

from src.gui import CCCDScannerApp
from src.parser import build_record


def test_split_view_toggle(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    assert hasattr(app, "btn_split_toggle")
    assert hasattr(app, "btn_split_sub")
    assert hasattr(app, "split_container")
    assert hasattr(app, "tree_passed")
    assert hasattr(app, "tree_failed")
    assert not app.is_split_mode

    # Toggle to split mode
    app._on_toggle_split_view()
    assert app.is_split_mode
    assert app.btn_split_toggle.cget("text") == "📋 Gộp lại danh sách chính"
    assert app.btn_split_sub.cget("text") == "📋 Gộp lại danh sách chính"

    # Toggle back to single view
    app._on_toggle_split_view()
    assert not app.is_split_mode
    assert "Tách danh sách lỗi" in app.btn_split_toggle.cget("text")
    assert "Tách danh sách lỗi" in app.btn_split_sub.cget("text")


def test_split_view_population_and_data_sync(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    rec1 = build_record(Path("cccd_good_01.jpg"), "001||Nguyễn Văn A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("cccd_good_02.jpg"), "002||Trần Thị B|02022001|Nu|HN|02022023", "OK")
    rec3 = build_record(Path("cccd_fail_01.jpg"), None, "UNREADABLE")
    rec4 = build_record(Path("cccd_fail_02.jpg"), None, "UNREADABLE")

    app.records = [rec1, rec2, rec3, rec4]
    app.total_queued = 4
    app.processed_count = 4
    app.success_count = 2
    app.error_count = 2

    # Switch to split view
    app._on_toggle_split_view()
    assert app.is_split_mode

    passed_items = app.tree_passed.get_children()
    failed_items = app.tree_failed.get_children()

    assert len(passed_items) == 2
    assert len(failed_items) == 2

    # Verify Passed table contents
    row_p1 = app.tree_passed.item(passed_items[0], "values")
    assert row_p1[0] == "001"
    assert row_p1[1] == "cccd_good_01.jpg"
    assert row_p1[2] == "Nguyễn Văn A"

    # Verify Failed table contents (#, file, name, status)
    row_f1 = app.tree_failed.item(failed_items[0], "values")
    assert row_f1[0] == "001"
    assert row_f1[1] == "cccd_fail_01.jpg"
    assert row_f1[2] == "(chưa nhập tên)"
    assert "Cần chụp lại" in row_f1[3]

    # Verify headers and button labels
    assert "2 thẻ thành công" in app.lbl_passed_title.cget("text")
    assert "2 ảnh lỗi" in app.lbl_failed_title.cget("text")
    assert "Gom ảnh lỗi vào 1 thư mục" in app.btn_move_toggle.cget("text")

    # Simulate reviewer typing a name in Failed list
    app.records[2]["full_name"] = "Lê Hoàng Long"
    app._refresh_split_views()

    updated_row_f1 = app.tree_failed.item(app.tree_failed.get_children()[0], "values")
    assert updated_row_f1[2] == "Lê Hoàng Long"

    # Toggle back to single view - verify name is preserved in the main table
    app._on_toggle_split_view()
    assert not app.is_split_mode
    main_items = app.table.get_children()
    assert len(main_items) == 4
    assert app.records[2]["full_name"] == "Lê Hoàng Long"


def test_split_view_delete(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    rec1 = build_record(Path("1.jpg"), "001||A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("bad.jpg"), None, "UNREADABLE")
    app.records = [rec1, rec2]
    app.total_queued = 2
    app.processed_count = 2
    app.success_count = 1
    app.error_count = 1

    app._on_toggle_split_view()
    failed_items = app.tree_failed.get_children()
    assert len(failed_items) == 1

    # Select and delete failed row
    app.tree_failed.selection_set(failed_items[0])
    app._on_split_failed_delete()

    assert len(app.records) == 1
    assert len(app.tree_failed.get_children()) == 0
    assert len(app.tree_passed.get_children()) == 1
    assert app.error_count == 0
    assert app.success_count == 1


def test_move_failed_auto_folder_and_instant_undo(tmp_path: Path, shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    from tkinter import messagebox

    app = CCCDScannerApp(shared_root)

    # Create dummy images in a source folder
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    f1 = src_dir / "failed_01.jpg"
    Image.new("RGB", (50, 50), color=(100, 100, 100)).save(f1, format="JPEG")

    rec1 = build_record(f1, None, "UNREADABLE")
    rec1["_full_path"] = str(f1)
    rec1["full_name"] = "Nguyễn Văn Test"

    app.records = [rec1]
    app.total_queued = 1
    app.processed_count = 1
    app.error_count = 1
    app._on_toggle_split_view()

    # Verify initial button state
    assert app.btn_move_toggle.cget("text") == "📁 Gom ảnh lỗi vào 1 thư mục"
    assert len(app.tree_failed.get_children()) == 1

    # Mock dialogs
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr("src.gui.open_path", lambda p: None)

    # 1. Perform move - automatically creates "Ảnh lỗi" folder in same dir
    app._on_move_failed_images()

    # Wait for worker thread
    import time
    for _ in range(20):
        shared_root.update()
        time.sleep(0.05)
        if app.has_moved_failed_images:
            break

    assert app.has_moved_failed_images is True
    error_folder = src_dir / "Ảnh lỗi"
    assert error_folder.exists()
    assert not f1.exists()

    moved_file = error_folder / "001_Nguyễn Văn Test.jpg"
    assert moved_file.exists()

    # Verify that the failed list is now EMPTY and empty message is placed
    assert len(app.tree_failed.get_children()) == 0

    # Verify button changed to State 2: "↩ Hoàn tác gom ảnh"
    assert app.btn_move_toggle.cget("text") == "↩ Hoàn tác gom ảnh"

    # 2. Click Undo - ONE CLICK, ZERO DIALOGS
    app._on_handle_failed_images_action()

    # Verify files restored to original path
    assert f1.exists()
    assert not moved_file.exists()

    # Verify "Ảnh lỗi" folder was deleted
    assert not error_folder.exists()

    # Verify record in app restored
    assert app.records[0]["_full_path"] == str(f1)
    assert app.records[0]["source_file"] == "failed_01.jpg"
    assert app.has_moved_failed_images is False

    # Verify all failed items appear back on the list!
    assert len(app.tree_failed.get_children()) == 1

    # Verify button reset to State 1
    assert app.btn_move_toggle.cget("text") == "📁 Gom ảnh lỗi vào 1 thư mục"


def test_hover_preview_interactions(tmp_path: Path, shared_root: tk.Tk):
    from src.failed_handler import HoverPreview

    app = CCCDScannerApp(shared_root)
    img_file = tmp_path / "card.jpg"
    Image.new("RGB", (100, 100), color=(50, 50, 50)).save(img_file, format="JPEG")

    hp = HoverPreview(app.tree_failed, lambda rid: str(img_file))
    assert hp.tip is None
    assert hp._job is None

    # Simulate show
    hp._show("dummy_row", 100, 100)
    assert hp.tip is not None
    assert hp.photo is not None

    # Simulate hide
    hp._hide()
    assert hp.tip is None


def test_failed_double_click_actions(tmp_path: Path, shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    app = CCCDScannerApp(shared_root)

    img_file = tmp_path / "failed_card.jpg"
    Image.new("RGB", (60, 60), color=(10, 20, 30)).save(img_file, format="JPEG")

    rec = build_record(img_file, None, "UNREADABLE")
    rec["_full_path"] = str(img_file)
    app.records = [rec]
    app._on_toggle_split_view()

    items = app.tree_failed.get_children()
    assert len(items) == 1
    item_id = items[0]

    opened_files = []
    monkeypatch.setattr("src.gui.open_path", lambda p: opened_files.append(str(p)))

    # 1. Double click on column #2 (source_file) -> triggers open_path
    class MockEvent:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    monkeypatch.setattr(app.tree_failed, "identify_row", lambda y: item_id)
    monkeypatch.setattr(app.tree_failed, "identify_column", lambda x: "#2")

    app._on_split_failed_double_click(MockEvent(10, 10))
    assert len(opened_files) == 1
    assert opened_files[0] == str(img_file)

    # 2. Double click on column #3 (full_name) -> triggers inline entry
    monkeypatch.setattr(app.tree_failed, "identify_column", lambda x: "#3")
    monkeypatch.setattr(app.tree_failed, "bbox", lambda row, col: (10, 10, 100, 25))

    app._on_split_failed_double_click(MockEvent(10, 10))
    assert app.active_inline_entry is not None
    app.active_inline_entry.delete(0, tk.END)
    app.active_inline_entry.insert(0, "Hoàng Thùy Linh")

    # FocusOut commits
    app.active_inline_entry.event_generate("<FocusOut>")
    assert app.records[0]["full_name"] == "Hoàng Thùy Linh"
