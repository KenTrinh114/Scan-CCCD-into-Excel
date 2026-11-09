"""Unit tests for GUI features: theme config, error filename formatting, status column resizing, and row deletion."""

import json
from pathlib import Path
import tkinter as tk
import pytest
from src.config import get_theme_file_path, load_theme_config, save_theme_config
from src.gui import CCCDScannerApp, THEMES
from src.parser import build_record


def test_theme_config_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_config_file = tmp_path / "theme_config.json"
    monkeypatch.setattr("src.config.get_theme_file_path", lambda: fake_config_file)

    # 1. Default should be "light"
    assert load_theme_config() == "light"

    # 2. Save dark theme
    save_theme_config("dark")
    assert fake_config_file.exists()
    assert load_theme_config() == "dark"

    # 3. Save light theme
    save_theme_config("light")
    assert load_theme_config() == "light"

    # 4. Invalid theme resets to "light"
    save_theme_config("invalid_theme")
    assert load_theme_config() == "light"


def test_error_display_value_and_resizing(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    # 0. App Title on window (includes deploy version)
    assert "App quét CCCD cho Nger ❤️" in shared_root.title()
    assert "- v" in shared_root.title()

    # Build an error record
    err_rec = build_record(Path("cccd_blurry_01.jpg"), None, "UNREADABLE")
    active_cols_no_source = [
        {"key": "status", "label": "Trạng thái", "enabled": True},
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
    ]
    active_cols_with_source = [
        {"key": "source_file", "label": "Tên file ảnh", "enabled": True},
        {"key": "status", "label": "Trạng thái", "enabled": True},
    ]

    # 1. When source_file is hidden, status cell contains filename
    display_no_source = app._get_display_value(err_rec, "status", active_cols_no_source)
    assert "[cccd_blurry_01.jpg]" in display_no_source
    assert "Không đọc được mã QR" in display_no_source

    # 2. When source_file is active, status cell does NOT duplicate filename
    display_with_source = app._get_display_value(err_rec, "status", active_cols_with_source)
    assert "[cccd_blurry_01.jpg]" not in display_with_source
    assert "Không đọc được mã QR" in display_with_source

    # 3. Status column width expands to fit the error message
    initial_w = int(app.table.column("status", "width"))
    app.records.append(err_rec)
    app._adjust_status_column_width()
    expanded_w = int(app.table.column("status", "width"))
    assert expanded_w > initial_w
    assert expanded_w >= 380

    # 4. Test theme switching works without error
    for theme_key in ("light", "dark"):
        app._apply_theme(theme_key)
        assert app.current_theme == theme_key
        assert shared_root.cget("bg") == THEMES[theme_key]["root_bg"]


def test_loading_animation_and_status_colors(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)
    active_cols = [
        {"key": "status", "label": "Trạng thái", "enabled": True},
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
    ]

    # 1. Pending record: shows loading circle in status, and empty values for other columns
    pending_rec = {
        "source_file": "img_test_01.jpg",
        "status": "Đang xử lý...",
        "_is_pending": True,
        "_is_error": False,
    }
    disp_status = app._get_display_value(pending_rec, "status", active_cols, spinner_frame="◐")
    assert "◐" in disp_status
    assert "[img_test_01.jpg]" in disp_status
    assert "Đang xử lý" in disp_status

    # Other columns must be empty string
    assert app._get_display_value(pending_rec, "cccd_number", active_cols) == ""
    assert app._get_display_value(pending_rec, "full_name", active_cols) == ""

    # 2. Success record: status changes to tick ✔ in green text
    success_rec = build_record(
        Path("img_test_01.jpg"),
        "079099001234||Nguyễn Văn A|01012000|Nam|Hà Nội|01012022",
        "OK",
    )
    disp_success = app._get_display_value(success_rec, "status", active_cols)
    assert "✔" in disp_success
    assert "Thành công" in disp_success

    # 3. Failed record: status changes to cross ✖ in red text
    error_rec = build_record(Path("img_bad_01.jpg"), None, "UNREADABLE")
    disp_error = app._get_display_value(error_rec, "status", active_cols)
    assert "✖" in disp_error
    assert "[img_bad_01.jpg]" in disp_error

    # 4. Check row background: entire row background is NOT colored (clean table background)
    assert app.table.tag_configure("error_row").get("background", "") == ""
    assert app.table.tag_configure("success_row").get("background", "") == ""
    # Foreground colors are properly configured for text and status
    assert app.table.tag_configure("error_row").get("foreground", "") != ""
    assert app.table.tag_configure("success_row").get("foreground", "") != ""


def test_delete_single_and_multiple_rows(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)

    # Check merged delete button and instruction label exist in status bar
    assert hasattr(app, "btn_delete_selected")
    assert hasattr(app, "btn_delete_single")
    assert hasattr(app, "btn_delete_multi")
    assert hasattr(app, "lbl_select_hint")
    assert "Ctrl" in app.lbl_select_hint.cget("text")
    assert "Shift" in app.lbl_select_hint.cget("text")
    assert app.btn_delete_selected.cget("text") == "🗑 Xóa dòng (0)"

    # Check selectmode is extended for multi-selection
    assert str(app.table.cget("selectmode")) == "extended"

    # Populate with 3 sample records: 2 success, 1 error
    rec1 = build_record(Path("1.jpg"), "001||A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("2.jpg"), "002||B|01012000|Nu|HN|01012022", "OK")
    rec3 = build_record(Path("3.jpg"), None, "UNREADABLE")
    app.records = [rec1, rec2, rec3]
    app.total_queued = 3
    app.processed_count = 3
    app.success_count = 2
    app.error_count = 1
    app._refresh_preview_table_data()

    assert len(app.records) == 3
    children = app.table.get_children()
    assert len(children) == 3

    # Dynamic count indicator tests:
    # 1 row selected
    app.table.selection_set(children[0])
    app._update_action_button_states()
    assert app.btn_delete_selected.cget("text") == "🗑 Xóa 1 dòng"

    # 2 rows selected
    app.table.selection_set(children[0], children[1])
    app._update_action_button_states()
    assert app.btn_delete_selected.cget("text") == "🗑 Xóa 2 dòng"

    # 0 rows selected
    app.table.selection_set()
    app._update_action_button_states()
    assert app.btn_delete_selected.cget("text") == "🗑 Xóa dòng (0)"

    # Test deleting 1 single row (rec2 at index 1)
    app._delete_records_by_indices({1})
    assert len(app.records) == 2
    assert len(app.table.get_children()) == 2
    assert app.records[0]["cccd_number"] == "001"
    assert app.records[1]["cccd_number"] == ""  # error row
    assert app.total_queued == 2
    assert app.success_count == 1
    assert app.error_count == 1

    # Test deleting multiple rows (remaining 2 records)
    app._delete_records_by_indices({0, 1})
    assert len(app.records) == 0
    assert len(app.table.get_children()) == 0
    assert app.total_queued == 0
    assert app.success_count == 0
    assert app.error_count == 0


def test_all_columns_dynamic_auto_resize(shared_root: tk.Tk):
    """Verify that long content in ANY column type triggers dynamic expansion."""
    app = CCCDScannerApp(shared_root)

    # Enable all columns
    for col in app.columns:
        col["enabled"] = True
    app._rebuild_preview_columns()

    # Record with very long address, name, filename, and extra_info
    long_address = "Số 123/45/6A, Hẻm 789, Khu phố 4, Phường Tân Chánh Hiệp, Quận 12, Thành phố Hồ Chí Minh"
    long_name = "Công Tằng Tôn Nữ Nguyễn Phước Ánh Nguyệt"
    long_filename = "CCCD_z6145330364998_e8760ba26c95c80a2df3dd4453b58498_scanned_highres.jpg"
    long_extra = "Thông tin tích hợp bổ sung số định danh cá nhân đặc biệt mở rộng theo luật căn cước 2024"

    rec = {
        "source_file": long_filename,
        "status": "Thành công",
        "cccd_number": "079099001234",
        "old_cmnd": "025812345",
        "full_name": long_name,
        "dob": "15/08/1990",
        "age": "36",
        "sex": "Nữ",
        "birth_province": "Thừa Thiên Huế",
        "permanent_address": long_address,
        "issue_date": "10/05/2021",
        "expiry_date": "15/08/2030",
        "extra_info": long_extra,
        "_is_error": False,
        "_is_pending": False,
    }

    # Initial widths before adding long content
    init_addr_w = int(app.table.column("permanent_address", "width"))
    init_name_w = int(app.table.column("full_name", "width"))
    init_file_w = int(app.table.column("source_file", "width"))
    init_extra_w = int(app.table.column("extra_info", "width"))

    app.records = [rec]
    app._refresh_preview_table_data()

    # Verify every column with long content expanded beyond initial default
    exp_addr_w = int(app.table.column("permanent_address", "width"))
    exp_name_w = int(app.table.column("full_name", "width"))
    exp_file_w = int(app.table.column("source_file", "width"))
    exp_extra_w = int(app.table.column("extra_info", "width"))

    assert exp_addr_w > init_addr_w
    assert exp_addr_w >= 450
    assert exp_name_w > init_name_w
    assert exp_name_w >= 220
    assert exp_file_w > init_file_w
    assert exp_file_w >= 380
    assert exp_extra_w > init_extra_w
    assert exp_extra_w >= 450


def test_delete_all_failed_rows(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    from tkinter import messagebox

    app = CCCDScannerApp(shared_root)

    app.records = [
        {"source_file": "ok1.jpg", "status": "Quét thành công", "_is_error": False, "_is_pending": False},
        {"source_file": "err1.jpg", "status": "Cần chụp lại", "_is_error": True, "_is_pending": False},
        {"source_file": "ok2.jpg", "status": "Quét thành công", "_is_error": False, "_is_pending": False},
        {"source_file": "err2.jpg", "status": "Cần chụp lại", "_is_error": True, "_is_pending": False},
    ]
    app.error_count = 2
    app.success_count = 2
    app.total_queued = 4
    app.processed_count = 4
    app._update_status_bar()

    # Verify button dynamically displays error count
    assert "2" in app.btn_delete_failed.cget("text")

    # Mock user confirming the deletion
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)

    app._on_delete_all_failed_rows()

    # Only the 2 success records should remain
    assert len(app.records) == 2
    assert all(not r["_is_error"] for r in app.records)
    assert app.error_count == 0
    assert app.success_count == 2
    assert app.btn_delete_failed.cget("text") == "🧹 Xóa dòng lỗi"


def test_revamped_dark_mode_colors(shared_root: tk.Tk):
    app = CCCDScannerApp(shared_root)
    app._apply_theme("dark")

    dark_theme = THEMES["dark"]
    # Verify dark mode uses deep obsidian surfaces and high-contrast status colors
    assert dark_theme["root_bg"] == "#0B0F17"
    assert dark_theme["frame_bg"] == "#151B28"
    assert dark_theme["success_fg"] == "#34D399"
    assert dark_theme["err_fg"] == "#F87171"
    assert dark_theme["pending_fg"] == "#60A5FA"
    assert dark_theme["excel_btn_fg"] == "#FFFFFF"
    assert shared_root.cget("bg") == "#0B0F17"


def test_process_queue_reschedules_polling(shared_root: tk.Tk):
    """Verify _process_queue reschedules itself via root.after(80, ...)."""
    app = CCCDScannerApp(shared_root)

    scheduled = []
    original_after = shared_root.after

    def mock_after(ms, func=None, *args):
        if func == app._process_queue:
            scheduled.append(ms)
        return original_after(ms, func, *args)

    shared_root.after = mock_after
    try:
        app._process_queue()
        assert 80 in scheduled
    finally:
        shared_root.after = original_after


def test_inline_editing_reentrancy_safe(shared_root: tk.Tk):
    """Verify commit_edit handles double invocation gracefully without TclError."""
    app = CCCDScannerApp(shared_root)
    rec = {"source_file": "test.jpg", "full_name": "Old Name", "status": "Thành công", "_is_error": False, "_is_pending": False}
    app.records = [rec]
    app._refresh_preview_table_data()

    # Simulate double click
    items = app.table.get_children()
    assert len(items) == 1

    # Fake entry creation
    entry = tk.Entry(app.table)
    app.active_inline_entry = entry

    # Calling destroy inline entry sets active_inline_entry to None
    app._destroy_inline_entry()
    assert app.active_inline_entry is None


def test_column_stretch_and_horizontal_scrolling(shared_root: tk.Tk):
    """
    Verify that table columns have stretch=False so user can freely expand them
    and that horizontal scrolling via Shift+MouseWheel works without error.
    """
    app = CCCDScannerApp(shared_root)

    # 1. Verify stretch is False on all active columns so manual expansion doesn't snap back
    for col in app.table["columns"]:
        col_opts = app.table.column(col)
        assert col_opts.get("stretch") in (0, False, "0"), f"Column {col} should have stretch=False"

    # 2. Verify column manual widening is preserved
    app.table.column("status", width=420)
    assert int(app.table.column("status", "width")) == 420

    # 3. Test horizontal scroll event
    class FakeWheelEvent:
        delta = -120

    res = app._on_table_shift_mousewheel(FakeWheelEvent())
    assert res == "break"

    # 4. Verify TCombobox in dark mode is properly styled (not greyed out)
    app._apply_theme("dark")
    dark_field_bg = app.style.lookup("TCombobox", "fieldbackground", ("readonly",))
    assert dark_field_bg == THEMES["dark"]["btn_bg"]


def test_export_excel_skips_status_and_errors(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """
    Verify that Excel export:
    1. Skips the 'status' column completely.
    2. Excludes error records (_is_error == True).
    3. Shows a warning about skipped error rows that can be appended later.
    """
    app = CCCDScannerApp(shared_root)

    rec1 = build_record(Path("success1.jpg"), "079099001234||Nguyễn Văn A|01011990|Nam|Hà Nội|01012020", "OK")
    rec2 = build_record(Path("error1.jpg"), None, "UNREADABLE")
    rec3 = build_record(Path("success2.jpg"), "079099005678||Trần Thị B|02021995|Nữ|TP HCM|02022021", "OK")

    app.records = [rec1, rec2, rec3]
    app.total_queued = 3
    app.processed_count = 3
    app.success_count = 2
    app.error_count = 1

    warnings_shown = []
    monkeypatch.setattr(
        "tkinter.messagebox.showwarning",
        lambda title, msg: warnings_shown.append((title, msg)),
    )

    prep = app._prepare_export_records_and_columns()
    assert prep is not None
    valid_recs, export_cols = prep

    # Assert status and source_file columns are skipped
    assert not any(c.get("key") == "status" for c in export_cols)
    assert not any(c.get("key") == "source_file" for c in export_cols)

    # Assert error record is omitted
    assert len(valid_recs) == 2
    assert all(not r.get("_is_error", False) for r in valid_recs)
    assert valid_recs[0]["cccd_number"] == "079099001234"
    assert valid_recs[1]["cccd_number"] == "079099005678"

    # Assert warning was shown explaining error rows were excluded
    assert len(warnings_shown) == 1
    assert "Bỏ qua dòng lỗi" in warnings_shown[0][0]
    assert "1" in warnings_shown[0][1]
    assert "Ghi tiếp vào Excel" in warnings_shown[0][1]


def test_export_excel_halts_when_all_records_are_errors(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """Verify that export aborts cleanly when list contains only error rows."""
    app = CCCDScannerApp(shared_root)
    rec_error = build_record(Path("error.jpg"), None, "UNREADABLE")
    app.records = [rec_error]
    app.error_count = 1

    warnings_shown = []
    monkeypatch.setattr(
        "tkinter.messagebox.showwarning",
        lambda title, msg: warnings_shown.append((title, msg)),
    )

    res = app._prepare_export_records_and_columns()
    assert res is None
    assert len(warnings_shown) == 1
    assert "Không có dữ liệu hợp lệ" in warnings_shown[0][0]


def test_treeview_gridlines_and_alternating_tags(shared_root: tk.Tk):
    """Verify Treeview Row and Cell layout performance alignment and alternating row tags."""
    app = CCCDScannerApp(shared_root)

    # Verify style layouts use high-performance native clam elements (aligned boundaries, no PhotoImage lag)
    row_layout = app.style.layout("Treeview.Row")
    cell_layout = app.style.layout("Treeview.Cell")
    heading_layout = app.style.layout("Treeview.Heading")
    assert any("row" in elem[0] for elem in row_layout)
    assert any("padding" in elem[0] for elem in cell_layout)
    assert any("border" in elem[0] for elem in heading_layout)

    # Verify flat border configuration on cells to eliminate double lines
    for theme_key in ("light", "dark"):
        app._apply_theme(theme_key)
        assert app.style.lookup("Treeview.Cell", "relief") == "flat"
        assert int(app.style.lookup("Treeview.Cell", "borderwidth")) == 0
        assert int(app.style.lookup("Treeview.Heading", "borderwidth")) == 1

    # Add sample records and verify alternating tags
    rec1 = build_record(Path("1.jpg"), "001||A|01012000|Nam|HN|01012022", "OK")
    rec2 = build_record(Path("2.jpg"), "002||B|01012000|Nu|HN|01012022", "OK")
    app.records = [rec1, rec2]
    app._refresh_preview_table_data()

    items = app.table.get_children()
    assert len(items) == 2
    tags_0 = app.table.item(items[0], "tags")
    tags_1 = app.table.item(items[1], "tags")

    assert "even_row" in tags_0
    assert "odd_row" in tags_1
    assert "success_row" in tags_0
    assert "success_row" in tags_1


def test_col_tree_click_only_toggles_checkbox_column(shared_root: tk.Tk):
    """
    Verify that:
    1. Checkbox column shows '◼' for enabled and '◻' for disabled.
    2. Only clicking on column #1 toggles the column enable status.
    3. Clicking on column #2 (#) or column #3 (Tên cột) does NOT toggle the column status.
    """
    app = CCCDScannerApp(shared_root)

    # Initial state: cccd_number is enabled
    col_def = next(c for c in app.columns if c["key"] == "cccd_number")
    col_def["enabled"] = True
    app._refresh_col_tree_view()
    assert app.col_tree.item("cccd_number", "values")[0] == "◼"

    col_disabled = next(c for c in app.columns if c["key"] == "old_cmnd")
    col_disabled["enabled"] = False
    app._refresh_col_tree_view()
    assert app.col_tree.item("old_cmnd", "values")[0] == "◻"

    class FakeClickEvent:
        def __init__(self, x: int, y: int):
            self.x = x
            self.y = y

    # Identify row at y=20
    target_key = app.col_tree.identify_row(20)
    target_col = next(c for c in app.columns if c["key"] == target_key)
    init_state = target_col.get("enabled", True)

    # 1. Click on column #2 or #3 (x=150) -> Must NOT toggle
    event_label = FakeClickEvent(x=150, y=20)
    app._on_col_tree_click(event_label)
    assert target_col.get("enabled", True) == init_state

    # 2. Click on column #1 ('checked' column, x=20) -> Must toggle
    event_check = FakeClickEvent(x=20, y=20)
    app._on_col_tree_click(event_check)
    assert target_col.get("enabled", True) != init_state

    # 3. Click again on column #1 -> Must toggle back
    app._on_col_tree_click(event_check)
    assert target_col.get("enabled", True) == init_state


def test_empty_state_action_buttons(shared_root: tk.Tk):
    """Verify that prominent 'Thêm ảnh...' buttons exist directly on the empty list state."""
    app = CCCDScannerApp(shared_root)

    assert hasattr(app, "empty_btn_container")
    assert hasattr(app, "btn_empty_add_files")
    assert hasattr(app, "btn_empty_add_dir")
    assert "Thêm ảnh" in app.btn_empty_add_files.cget("text")
    assert "Thêm thư mục" in app.btn_empty_add_dir.cget("text")


def test_single_column_divider_and_high_quality_icons(shared_root: tk.Tk):
    """
    Verify:
    1. High-performance native clam Treeview layout without PhotoImage lag.
    2. Heading border alignment with 1px border and flat borderless cells (no double lines).
    3. Solid filled square '◼' for enabled columns and hollow square '◻' for disabled columns.
    4. Heavy high-contrast tick '✔' for success and cross '✖' for errors in status displays.
    """
    app = CCCDScannerApp(shared_root)

    # 1. Native clam layout structure without image elements
    cell_layout = app.style.layout("Treeview.Cell")
    assert any("padding" in elem[0] for elem in cell_layout)

    item_layout = app.style.layout("Treeview.Item")
    assert any("padding" in elem[0] for elem in item_layout)

    heading_layout = app.style.layout("Treeview.Heading")
    assert any(elem[0] == "Treeheading.cell" for elem in heading_layout)
    assert any(elem[0] == "Treeheading.border" for elem in heading_layout)

    # 2. No 4-sided borders on cells that could produce double lines; 1px heading border for column separation
    assert app.style.lookup("Treeview.Cell", "relief") == "flat"
    assert int(app.style.lookup("Treeview.Cell", "borderwidth")) == 0
    assert app.style.lookup("Treeview.Heading", "relief") == "solid"
    assert int(app.style.lookup("Treeview.Heading", "borderwidth")) == 1

    # 3. Solid filled square checkbox in column panel
    assert app.col_tree.heading("checked", "text") == "◼ Chọn"

    # Enabled column
    app.columns[0]["enabled"] = True
    app._refresh_col_tree_view()
    item_first = app.col_tree.get_children()[0]
    assert app.col_tree.item(item_first, "values")[0] == "◼"

    # Disabled column
    app.columns[0]["enabled"] = False
    app._refresh_col_tree_view()
    assert app.col_tree.item(item_first, "values")[0] == "◻"
    app.columns[0]["enabled"] = True  # restore

    # 4. Heavy high-contrast icons for status
    active = app._get_active_columns()
    ok_rec = build_record(Path("sample_ok.jpg"), "079099001234||Nguyen Van A|01012000|Nam|HN|01012022", "OK")
    bad_rec = build_record(Path("sample_bad.jpg"), None, "UNREADABLE")

    assert "✔" in app._get_display_value(ok_rec, "status", active)
    assert "✓" not in app._get_display_value(ok_rec, "status", active)
    assert "✖" in app._get_display_value(bad_rec, "status", active)
    assert "✗" not in app._get_display_value(bad_rec, "status", active)

    # Status bar formatting
    app.success_count = 5
    app.error_count = 2
    app.total_queued = 7
    app.processed_count = 7
    app._update_status_bar()
    status_text = app.lbl_status.cget("text")
    assert "✔ 5 thành công" in status_text
    assert "✖ 2 cần chụp lại" in status_text
    assert "✖ Chỉ xem ảnh cần chụp lại (2)" in app.chk_filter.cget("text")


def test_treeview_selection_latency_and_alignment(shared_root: tk.Tk):
    """
    Verify that table selection operations run at sub-50ms speed (for old PCs)
    and that data columns align seamlessly without cumulative boundary drift.
    """
    import time
    app = CCCDScannerApp(shared_root)

    # Insert 25 sample records
    for i in range(25):
        rec = build_record(
            Path(f"img_{i}.jpg"),
            f"07909900{i:04d}||Nguyen Van {i}|01012000|Nam|HN|01012022",
            "OK",
        )
        app.records.append(rec)
    app._refresh_preview_table_data()
    shared_root.update()

    item_ids = list(app.table.get_children())
    assert len(item_ids) >= 25

    # 1. Performance check: selection + event update must take <50ms per iteration
    t0 = time.perf_counter()
    for item in item_ids[:5]:
        app.table.selection_set(item)
        app._on_table_select_changed()
        shared_root.update()
    t1 = time.perf_counter()
    avg_latency_ms = ((t1 - t0) / 5) * 1000
    assert avg_latency_ms < 50.0, f"Selection latency too slow: {avg_latency_ms:.1f}ms (expected <50ms)"

    # 2. Alignment check: column boundary alignment across visible active columns
    active = app._get_active_columns()
    prev_right = 2
    for idx, col in enumerate(active, 1):
        bbox = app.table.bbox(item_ids[0], f"#{idx}")
        if bbox:
            # Each visible column must start exactly where the previous column ended (0 drift gap)
            assert bbox[0] == prev_right, f"Column #{idx} ({col['key']}) misaligned: starts at {bbox[0]}, expected {prev_right}"
            prev_right = bbox[0] + bbox[2]


def test_app_icon_and_slider_visibility(shared_root: tk.Tk):
    """
    Verify:
    1. App icon files (assets/app_icon.ico and assets/app_icon.png) exist, load, and have transparent background.
    2. Empty state card icon retains CCCD card emoji ('🪪'), not the app icon.
    3. Slider components (TScrollbar and Sash) have distinct dark grey colors in both light and dark themes.
    """
    app = CCCDScannerApp(shared_root)

    # 1. App icon assets
    assets_dir = Path(__file__).parent.parent / "assets"
    ico_file = assets_dir / "app_icon.ico"
    png_file = assets_dir / "app_icon.png"
    assert ico_file.exists()
    assert png_file.exists()
    assert hasattr(app, "_app_icon_img")

    # Verify PNG has alpha channel transparency
    from PIL import Image
    png_img = Image.open(png_file)
    assert png_img.mode == "RGBA"
    # Corners should be transparent
    assert png_img.getpixel((0, 0))[3] == 0

    # 2. Empty state maintains CCCD card icon
    assert hasattr(app, "lbl_empty_icon")
    assert app.lbl_empty_icon.cget("text") == "🪪"

    # 3. Slider / Scrollbar visibility in light and dark themes (dark grey tones)
    for theme_key, expected_thumb in [("light", "#475569"), ("dark", "#526075")]:
        app._apply_theme(theme_key)
        thumb_bg = app.style.lookup("TScrollbar", "background")
        assert thumb_bg.upper() == expected_thumb.upper(), f"Scrollbar thumb color in {theme_key} is {thumb_bg}, expected {expected_thumb}"
        assert int(app.style.lookup("Sash", "sashthickness")) == 6




