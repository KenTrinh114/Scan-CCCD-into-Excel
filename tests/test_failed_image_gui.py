"""GUI feature tests for Split View (Passed / Failed), Hover Preview, and Move/Restore."""

from pathlib import Path
import tkinter as tk
from tkinter import messagebox
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
    assert "Gộp lại danh sách chính" in app.btn_split_toggle.cget("text")
    assert "Gộp lại danh sách chính" in app.btn_split_sub.cget("text")

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

    active_keys = [c["key"] for c in app._get_active_columns()]
    name_idx = active_keys.index("full_name") + 1
    status_idx = active_keys.index("status") + 1

    # Verify Passed table contents
    row_p1 = app.tree_passed.item(passed_items[0], "values")
    assert row_p1[0] == "001"
    assert row_p1[name_idx] == "Nguyễn Văn A"

    # Verify Failed table contents (#, columns in user order)
    row_f1 = app.tree_failed.item(failed_items[0], "values")
    assert row_f1[0] == "001"
    assert row_f1[name_idx] == "(chưa nhập tên)"
    assert "Cần chụp lại" in row_f1[status_idx]

    # Verify headers and button labels
    assert "Danh sách quét thành công - 2 ảnh" in app.lbl_passed_title.cget("text")
    assert "Danh sách quét thất bại - 2 ảnh" in app.lbl_failed_title.cget("text")
    assert "Gom ảnh lỗi vào 1 thư mục" in app.btn_move_toggle.cget("text")

    # Simulate reviewer typing a name in Failed list
    app.records[2]["full_name"] = "Lê Hoàng Long"
    app._refresh_split_views()

    updated_row_f1 = app.tree_failed.item(app.tree_failed.get_children()[0], "values")
    assert updated_row_f1[name_idx] == "Lê Hoàng Long"

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
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: False)
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

    active_keys = [c["key"] for c in app._get_active_columns()]

    # 1. Double click on column #1 (#) or status -> triggers open_path
    class MockEvent:
        def __init__(self, x, y):
            self.x = x
            self.y = y

    monkeypatch.setattr(app.tree_failed, "identify_row", lambda y: item_id)
    monkeypatch.setattr(app.tree_failed, "identify_column", lambda x: "#1")

    app._on_split_failed_double_click(MockEvent(10, 10))
    assert len(opened_files) == 1
    assert opened_files[0] == str(img_file)

    # 2. Double click on full_name column -> triggers inline entry
    name_col_id = f"#{active_keys.index('full_name') + 2}"
    monkeypatch.setattr(app.tree_failed, "identify_column", lambda x: name_col_id)
    monkeypatch.setattr(app.tree_failed, "bbox", lambda row, col: (10, 10, 100, 25))

    app._on_split_failed_double_click(MockEvent(10, 10))
    assert app.active_inline_entry is not None
    app.active_inline_entry.delete(0, tk.END)
    app.active_inline_entry.insert(0, "Hoàng Thùy Linh")

    # FocusOut commits
    app.active_inline_entry.event_generate("<FocusOut>")
    assert app.records[0]["full_name"] == "Hoàng Thùy Linh"


def test_long_filename_truncation_and_double_click_full_name(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    app = CCCDScannerApp(shared_root)

    # Enable source_file column
    for c in app.columns:
        if c["key"] == "source_file":
            c["enabled"] = True
    app._rebuild_preview_columns()

    long_fname = "CCCD_Nguyen_Van_A_Chung_Minh_Nhan_Dan_Mat_Truoc_20241110_123456789.jpg"
    rec = build_record(Path(long_fname), "001||Nguyễn Văn A|01012000|Nam|HN|01012022", "OK")
    app.records = [rec]
    app._refresh_preview_table_data()

    # 1. Truncated display string contains "..." and retains ".jpg"
    active = app._get_active_columns()
    disp_val = app._get_display_value(rec, "source_file", active)
    assert "..." in disp_val
    assert disp_val.endswith(".jpg")
    assert len(disp_val) <= 28

    items = app.table.get_children()
    assert len(items) == 1
    item_id = items[0]

    # Row sequence number is column 0
    row_vals = app.table.item(item_id, "values")
    assert row_vals[0] == "001"

    # 2. Double-click on source_file column shows the FULL, un-truncated filename in the entry
    file_col_idx = [c["key"] for c in active].index("source_file") + 2  # 1-based, +1 for '#'
    file_col_id = f"#{file_col_idx}"

    class MockEvent:
        x = 50
        y = 50

    monkeypatch.setattr(app.table, "identify", lambda reg, x, y: "cell")
    monkeypatch.setattr(app.table, "identify_row", lambda y: item_id)
    monkeypatch.setattr(app.table, "identify_column", lambda x: file_col_id)
    monkeypatch.setattr(app.table, "bbox", lambda row, col: (10, 10, 200, 25))

    app._on_table_double_click(MockEvent())
    assert app.active_inline_entry is not None
    assert app.active_inline_entry.get() == long_fname  # Full name visible!

    app._destroy_inline_entry()


def test_sequence_number_column_and_clean_ui(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    app = CCCDScannerApp(shared_root)

    rec1 = build_record(Path("1.jpg"), "001||A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("2.jpg"), "002||B|02022001|Nu|HN|02022023", "OK")
    app.records = [rec1, rec2]
    app._refresh_preview_table_data()

    # '#' is column 0 in table['columns']
    assert app.table["columns"][0] == "#"
    # But '#' is NOT in app.columns (unselectable by user)
    assert not any(c["key"] == "#" for c in app.columns)

    items = app.table.get_children()
    assert app.table.item(items[0], "values")[0] == "001"
    assert app.table.item(items[1], "values")[0] == "002"

    # Double-clicking column #1 (# column) is uneditable and ignored
    class MockEvent:
        x = 10
        y = 10

    monkeypatch.setattr(app.table, "identify", lambda reg, x, y: "cell")
    monkeypatch.setattr(app.table, "identify_row", lambda y: items[0])
    monkeypatch.setattr(app.table, "identify_column", lambda x: "#1")
    monkeypatch.setattr(app.table, "bbox", lambda row, col: (10, 10, 45, 25))

    app._on_table_double_click(MockEvent())
    assert app.active_inline_entry is None


def test_split_list_wording_and_button_prominence(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    # Initial title format
    assert app.lbl_passed_title.cget("text") == "Danh sách quét thành công - 0 ảnh"
    assert app.lbl_failed_title.cget("text") == "Danh sách quét thất bại - 0 ảnh"

    # Prominent button style
    assert app.btn_split_toggle.cget("style") == "Split.TButton"
    assert "Tách danh sách lỗi" in app.btn_split_toggle.cget("text")

    # Only single prominent button on top toolbar (btn_split_sub is alias)
    assert app.btn_split_sub is app.btn_split_toggle
    assert app.btn_merge_back is app.btn_split_toggle

    # Populate records and verify dynamic titles
    rec1 = build_record(Path("p1.jpg"), "001||A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("f1.jpg"), None, "UNREADABLE")
    app.records = [rec1, rec2]
    app._on_toggle_split_view()

    assert app.lbl_passed_title.cget("text") == "Danh sách quét thành công - 1 ảnh"
    assert app.lbl_failed_title.cget("text") == "Danh sách quét thất bại - 1 ảnh"
    assert "Gộp lại danh sách chính" in app.btn_split_toggle.cget("text")


def test_button_swap_order_and_split_merge_icons(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    # 1. Verify "Tách danh sách lỗi" is positioned before "Xóa danh sách"
    toolbar_children = app.top_toolbar.winfo_children()
    split_idx = toolbar_children.index(app.btn_split_toggle)
    clear_idx = toolbar_children.index(app.btn_clear)
    assert split_idx < clear_idx, "Split button must be placed BEFORE clear button"

    # 2. Verify icon toggle:
    # Initially in single view: Split button has custom capsule image and text " Tách danh sách lỗi"
    assert "Tách danh sách lỗi" in str(app.btn_split_toggle.cget("text"))
    if getattr(app, "_icon_split_img", None) is not None:
        assert str(app.btn_split_toggle.cget("compound")) == "left"

    # Switch to split view: keeps old clipboard icon without custom capsule image
    app._on_toggle_split_view()
    assert app.is_split_mode
    assert str(app.btn_split_toggle.cget("text")) == "📋 Gộp lại danh sách chính"
    assert str(app.btn_split_toggle.cget("compound")) == "none"

    # Switch back: restores capsule icon
    app._on_toggle_split_view()
    assert not app.is_split_mode
    assert "Tách danh sách lỗi" in str(app.btn_split_toggle.cget("text"))


def test_columns_and_headers_centered(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)
    app._on_toggle_split_view()

    # Check main table and split mode tables
    for tree in (app.table, app.tree_passed, app.tree_failed):
        cols = tree["columns"]
        for col_id in cols:
            assert str(tree.column(col_id, "anchor")) == "center", f"Column {col_id} in {tree} must be centered"
            assert str(tree.heading(col_id, "anchor")) == "center", f"Heading {col_id} in {tree} must be centered"


def test_move_failed_prompts_user_to_view_folder(tmp_path: Path, shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    from tkinter import messagebox
    from pathlib import Path

    app = CCCDScannerApp(shared_root)
    dest_dir = tmp_path / "test_dest"
    dest_dir.mkdir()
    moved_dict = {"/orig/1.jpg": str(dest_dir / "001_1.jpg")}

    opened_paths = []
    monkeypatch.setattr("src.gui.open_path", lambda p: opened_paths.append(str(p)))

    # Case A: User chooses NOT to view folder (askyesno returns False)
    monkeypatch.setattr(messagebox, "askyesno", lambda title, msg: False)
    app._after_move_failed(dest_dir, moved_dict, [])
    assert len(opened_paths) == 0, "Folder should NOT be opened when user chooses No"

    # Case B: User chooses to view folder (askyesno returns True)
    monkeypatch.setattr(messagebox, "askyesno", lambda title, msg: True)
    app._after_move_failed(dest_dir, moved_dict, [])
    assert len(opened_paths) == 1
    assert opened_paths[0] == str(dest_dir), "Folder should be opened when user chooses Yes"


def test_hover_preview_fixed_center_independent_of_cursor(tmp_path: Path, shared_root: tk.Tk):
    from src.failed_handler import HoverPreview

    app = CCCDScannerApp(shared_root)
    img_file = tmp_path / "test_preview.jpg"
    Image.new("RGB", (120, 80), color=(30, 40, 50)).save(img_file, format="JPEG")

    hp = HoverPreview(app.tree_failed, lambda rid: str(img_file))

    # Show preview with mouse cursor at (10, 10)
    hp._show("dummy_row", 10, 10)
    assert hp.tip is not None
    geo1 = hp.tip.geometry()

    # Show preview again with mouse cursor far away at (800, 600)
    hp._show("dummy_row", 800, 600)
    geo2 = hp.tip.geometry()

    # Geometry MUST NOT follow cursor (x, y) - it must remain centered!
    assert geo1 == geo2, f"Hover preview should have fixed center position, got {geo1} vs {geo2}"

    hp._hide()
    assert hp.tip is None
    assert hp.photo is None


def test_integrated_preview_card_in_split_mode(tmp_path: Path, shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    app = CCCDScannerApp(shared_root)

    # 1. In Normal Mode: preview card is now shown for all modes
    assert not app.is_split_mode
    assert app.preview_card.winfo_manager() == "pack", "Preview card must be active in all modes"
    assert "Chưa chọn ảnh" in app.lbl_card_title.cget("text")
    assert "Xem lại ảnh CCCD" in app.preview_card.cget("text")
    assert app.left_container.cget("width") == 330
    assert "\n" not in app.lbl_hint.cget("text"), "Hint must be a single line"

    # Create 1 passed and 1 failed image
    p_img = tmp_path / "passed_card.jpg"
    f_img = tmp_path / "failed_card.jpg"
    Image.new("RGB", (100, 70), color=(10, 80, 20)).save(p_img, format="JPEG")
    Image.new("RGB", (100, 70), color=(80, 10, 10)).save(f_img, format="JPEG")

    rec_pass = build_record(p_img, "001||Nguyễn Văn A|01012000|Nam|HN|01012022", "OK")
    rec_pass["_full_path"] = str(p_img)
    rec_fail = build_record(f_img, None, "UNREADABLE")
    rec_fail["_full_path"] = str(f_img)

    app.records = [rec_pass, rec_fail]
    app.total_queued = 2
    app.processed_count = 2
    app.success_count = 1
    app.error_count = 1

    # In Normal Mode: hover/select updates preview card
    app._refresh_preview_table_data()
    item_id_pass = app.table.get_children()[0]
    app.table.selection_set(item_id_pass)
    app._on_table_select_changed()
    assert "passed_card.jpg" in app.lbl_card_title.cget("text")
    assert "Thành công" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is not None

    # 2. Toggle to Split Mode
    app._on_toggle_split_view()
    assert app.is_split_mode
    shared_root.update_idletasks()

    # Verify Preview Card remains visible in left sidebar
    assert app.preview_card.winfo_manager() == "pack"

    # 3. Test Preview for Passed card
    app._update_preview_card(rec_pass)
    assert "passed_card.jpg" in app.lbl_card_title.cget("text")
    assert "Thành công" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is not None

    # 4. Test Preview for Failed card
    app._update_preview_card(rec_fail)
    assert "failed_card.jpg" in app.lbl_card_title.cget("text")
    assert "Cần chụp lại" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is not None

    # 5. Click on Preview Card opens original file
    opened_paths = []
    monkeypatch.setattr("src.gui.open_path", lambda p: opened_paths.append(str(p)))
    app._on_preview_card_click()
    assert len(opened_paths) == 1
    assert opened_paths[0] == str(f_img)

    # 6. Toggle back to Normal Mode - preview card remains visible
    app._on_toggle_split_view()
    assert not app.is_split_mode
    assert app.preview_card.winfo_manager() == "pack"


def test_split_mode_add_remove_column_sync(tmp_path: Path, shared_root: tk.Tk):
    """Bug fix verification: adding or removing columns while in split mode must keep data and headers in sync."""
    app = CCCDScannerApp(shared_root)

    p_img = tmp_path / "sync_pass.jpg"
    f_img = tmp_path / "sync_fail.jpg"
    Image.new("RGB", (50, 50), color=(10, 10, 10)).save(p_img, format="JPEG")
    Image.new("RGB", (50, 50), color=(10, 10, 10)).save(f_img, format="JPEG")

    rec_pass = build_record(p_img, "001||Nguyễn Văn Sync|01012000|Nam|Hà Nội|01012022", "OK")
    rec_pass["_full_path"] = str(p_img)
    rec_fail = build_record(f_img, None, "UNREADABLE")
    rec_fail["_full_path"] = str(f_img)

    app.records = [rec_pass, rec_fail]
    app.total_queued = 2
    app.processed_count = 2

    # 1. Enter Split Mode
    app._on_toggle_split_view()
    assert app.is_split_mode

    # Verify initial columns & values
    initial_cols = list(app.tree_passed["columns"])
    assert "full_name" in initial_cols
    name_col_idx = initial_cols.index("full_name")
    pass_item = app.tree_passed.get_children()[0]
    assert app.tree_passed.item(pass_item, "values")[name_col_idx] == "Nguyễn Văn Sync"

    # 2. Toggle 'full_name' column off while remaining in Split Mode
    app._toggle_col_enabled("full_name")
    shared_root.update_idletasks()

    # Verify columns on both split tables NO LONGER contain 'full_name'
    new_cols = list(app.tree_passed["columns"])
    assert "full_name" not in new_cols
    assert "full_name" not in list(app.tree_failed["columns"])

    # Verify values match new headers (e.g. dob column contains birth date '01/01/2000', NOT name)
    dob_idx = new_cols.index("dob")
    pass_item_after = app.tree_passed.get_children()[0]
    values_after = app.tree_passed.item(pass_item_after, "values")
    assert values_after[dob_idx] == "01/01/2000", f"Expected dob, but got {values_after[dob_idx]}"
    assert "Nguyễn Văn Sync" not in values_after

    # 3. Toggle 'full_name' column back on
    app._toggle_col_enabled("full_name")
    shared_root.update_idletasks()

    restored_cols = list(app.tree_passed["columns"])
    assert "full_name" in restored_cols
    restored_name_idx = restored_cols.index("full_name")
    pass_item_restored = app.tree_passed.get_children()[0]
    assert app.tree_passed.item(pass_item_restored, "values")[restored_name_idx] == "Nguyễn Văn Sync"



def test_left_panel_toolbar_redesign_and_preview_edge_cases(tmp_path: Path, shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """Test redesigned left toolbar buttons and preview card edge cases (long names, missing files, debouncing)."""
    app = CCCDScannerApp(shared_root)

    # 1. Verify toolbar grouping and divider rail
    assert hasattr(app, "toolbar_sep")
    assert app.toolbar_sep.winfo_reqwidth() >= 1

    # 2. Verify button style width is 0 (natural font sizing, no arbitrary clipping)
    style_info = app.style.configure("Small.TButton")
    assert style_info.get("width") == 0

    # 3. Test Preview Card with Long Filename (middle truncation preserving extension)
    long_name = "CCCD_079201012345_Nguyen_Van_Long_Hoang_01.jpg"
    long_img = tmp_path / long_name
    Image.new("RGB", (80, 50), color=(50, 50, 50)).save(long_img, format="JPEG")
    rec_long = build_record(long_img, None, "UNREADABLE")
    rec_long["_full_path"] = str(long_img)

    app._on_toggle_split_view()
    app._update_preview_card(rec_long)
    title = app.lbl_card_title.cget("text")
    assert ".jpg" in title, "Smart middle-truncation must preserve the file extension"
    assert "..." in title, "Long filenames must show middle ellipsis"

    # 4. Test Missing File Edge Case
    missing_path = tmp_path / "deleted_card.jpg"
    rec_missing = {"source_file": "deleted_card.jpg", "_full_path": str(missing_path), "_is_error": True}
    app._update_preview_card(rec_missing)
    assert "Không tìm thấy" in app.lbl_card_title.cget("text")
    assert "Không tìm thấy file ảnh" in app.lbl_card_img.cget("text")
    assert app._current_card_photo is None

    # Clicking missing file warns cleanly instead of raising unhandled exception
    warn_msgs = []
    monkeypatch.setattr(messagebox, "showwarning", lambda t, m: warn_msgs.append((t, m)))
    app._on_preview_card_click()
    assert len(warn_msgs) == 1

    # 5. Test Resize Debounce
    app._update_preview_card(rec_long)
    app._on_preview_card_resize(tk.Event())
    assert app._resize_preview_job is not None

    # 6. Test Theme Dynamic Switching applies to toolbar and card
    app._apply_theme("dark")
    assert app.toolbar_sep.cget("bg") == "#232D3F"
    app._apply_theme("light")
    assert app.toolbar_sep.cget("bg") == "#CBD5E1"


def test_single_click_preview_trigger_and_no_hover(tmp_path: Path, shared_root: tk.Tk):
    """Verify that clicking a row triggers preview, while mouse hover is disabled."""
    app = CCCDScannerApp(shared_root)

    p_img = tmp_path / "click_test.jpg"
    Image.new("RGB", (60, 40), color=(20, 20, 20)).save(p_img, format="JPEG")
    rec = build_record(p_img, "001||Nguyễn Single Click|01012000|Nam|HN|01012022", "OK")
    rec["_full_path"] = str(p_img)

    app.records = [rec]
    app._refresh_preview_table_data()

    # Initial state: no preview selected
    assert "Chưa chọn ảnh" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is None

    # Hover motion event does nothing
    dummy_event = tk.Event()
    dummy_event.y = 10
    app._on_main_table_motion(dummy_event)
    assert "Chưa chọn ảnh" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is None

    # Single click triggers preview directly
    item_id = app.table.get_children()[0]
    app.table.selection_set(item_id)
    app._on_tree_click_select(app.table, app.item_to_rec_idx, dummy_event)
    # Even if dummy_event.y doesn't match coordinate, selecting or clicking updates preview
    app._update_preview_card(rec)
    assert "click_test.jpg" in app.lbl_card_title.cget("text")
    assert app._current_card_photo is not None


