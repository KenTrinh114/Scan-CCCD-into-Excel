"""Unit tests for Excel exporter and appender."""

from pathlib import Path
import openpyxl
import pytest
from src.excel_exporter import append_records_to_excel, export_records_to_excel
from src.parser import build_record


def test_export_records_to_excel(tmp_path: Path):
    rec_success = build_record(
        Path("test1.jpg"),
        "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021",
        "OK",
    )
    rec_error = build_record(
        Path("test2.jpg"),
        None,
        "UNREADABLE",
    )

    records = [rec_success, rec_error]
    active_columns = [
        {"key": "source_file", "label": "Tên file ảnh", "enabled": True},
        {"key": "status", "label": "Trạng thái", "enabled": True},
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
    ]

    out_file = tmp_path / "test_out.xlsx"
    export_records_to_excel(records, active_columns, str(out_file))

    assert out_file.exists()

    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    assert ws.title == "Danh sách CCCD"

    # Header assertions
    assert ws.cell(row=1, column=1).value == "Tên file ảnh"
    assert ws.cell(row=1, column=2).value == "Trạng thái"
    assert ws.cell(row=1, column=3).value == "Số định danh / CCCD"
    assert ws.cell(row=1, column=4).value == "Họ và tên"

    # Success row assertions
    assert ws.cell(row=2, column=1).value == "test1.jpg"
    assert ws.cell(row=2, column=2).value == "Thành công"
    assert ws.cell(row=2, column=3).value == "079099001234"
    assert ws.cell(row=2, column=4).value == "Nguyễn Văn A"

    # Error row assertions
    assert ws.cell(row=3, column=1).value == "test2.jpg"
    assert "Không đọc được mã QR" in ws.cell(row=3, column=2).value
    assert ws.cell(row=3, column=3).value in ("", None)
    assert ws.cell(row=3, column=4).value in ("", None)

    # Check error row fill color
    fill = ws.cell(row=3, column=1).fill
    assert fill.start_color.rgb in ("00FFEBEE", "FFEBEE")


def test_export_error_row_includes_filename_when_source_file_hidden(tmp_path: Path):
    rec_error = build_record(
        Path("cmnd_bi_mo_01.jpg"),
        None,
        "UNREADABLE",
    )
    # source_file is omitted (disabled by default)
    active_columns = [
        {"key": "status", "label": "Trạng thái", "enabled": True},
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
    ]

    out_file = tmp_path / "test_hidden_source.xlsx"
    export_records_to_excel([rec_error], active_columns, str(out_file))

    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    status_val = ws.cell(row=2, column=1).value
    assert "[cmnd_bi_mo_01.jpg]" in status_val
    assert "Không đọc được mã QR" in status_val


def test_append_records_to_excel_success(tmp_path: Path):
    rec1 = build_record(
        Path("test1.jpg"),
        "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021",
        "OK",
    )
    rec2 = build_record(
        Path("test2.jpg"),
        "001099005678||Trần Thị B|01012000|Nữ|Hà Nội|20052022",
        "OK",
    )

    active_columns = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
        {"key": "dob", "label": "Ngày sinh", "enabled": True},
    ]

    out_file = tmp_path / "test_append.xlsx"
    export_records_to_excel([rec1], active_columns, str(out_file))

    # Append second record
    appended = append_records_to_excel([rec2], active_columns, str(out_file))
    assert appended == 1

    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    assert ws.max_row == 3  # Header (1) + Record 1 (2) + Record 2 (3)

    assert ws.cell(row=2, column=1).value == "079099001234"
    assert ws.cell(row=2, column=2).value == "Nguyễn Văn A"

    assert ws.cell(row=3, column=1).value == "001099005678"
    assert ws.cell(row=3, column=2).value == "Trần Thị B"


def test_append_records_mismatched_columns(tmp_path: Path):
    rec1 = build_record(
        Path("test1.jpg"),
        "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021",
        "OK",
    )
    rec2 = build_record(
        Path("test2.jpg"),
        "001099005678||Trần Thị B|01012000|Nữ|Hà Nội|20052022",
        "OK",
    )

    # Initial file has 3 columns
    cols_initial = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
        {"key": "dob", "label": "Ngày sinh", "enabled": True},
    ]

    # Attempting to append with 4 columns
    cols_mismatch = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
        {"key": "dob", "label": "Ngày sinh", "enabled": True},
        {"key": "sex", "label": "Giới tính", "enabled": True},
    ]

    out_file = tmp_path / "test_mismatch.xlsx"
    export_records_to_excel([rec1], cols_initial, str(out_file))

    with pytest.raises(ValueError, match="Số lượng cột không khớp"):
        append_records_to_excel([rec2], cols_mismatch, str(out_file))

    # File should remain with 1 data row
    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    assert ws.max_row == 2


def test_append_records_creates_backup_bak(tmp_path: Path):
    rec1 = build_record(
        Path("test1.jpg"),
        "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021",
        "OK",
    )
    rec2 = build_record(
        Path("test2.jpg"),
        "001099005678||Trần Thị B|01012000|Nữ|Hà Nội|20052022",
        "OK",
    )
    active_columns = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
    ]

    out_file = tmp_path / "test_backup.xlsx"
    export_records_to_excel([rec1], active_columns, str(out_file))

    bak_file = tmp_path / "test_backup.xlsx.bak"
    assert not bak_file.exists()

    append_records_to_excel([rec2], active_columns, str(out_file))
    assert bak_file.exists()
    assert bak_file.stat().st_size > 0


def test_append_records_mismatched_header_labels(tmp_path: Path):
    rec1 = build_record(
        Path("test1.jpg"),
        "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021",
        "OK",
    )
    rec2 = build_record(
        Path("test2.jpg"),
        "001099005678||Trần Thị B|01012000|Nữ|Hà Nội|20052022",
        "OK",
    )

    cols_initial = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
    ]
    # Same column count (2), but different headers
    cols_different = [
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
        {"key": "dob", "label": "Ngày sinh", "enabled": True},
    ]

    out_file = tmp_path / "test_header_mismatch.xlsx"
    export_records_to_excel([rec1], cols_initial, str(out_file))

    with pytest.raises(ValueError, match="Tiêu đề các cột không khớp"):
        append_records_to_excel([rec2], cols_different, str(out_file))


def test_export_records_formula_injection_sanitization(tmp_path: Path):
    rec_inject = {
        "source_file": "evil.jpg",
        "status": "Thành công",
        "cccd_number": "079099001234",
        "full_name": "=cmd|' /C calc'!A0",
        "permanent_address": "+123456789",
        "_is_error": False,
    }
    active_columns = [
        {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True},
        {"key": "full_name", "label": "Họ và tên", "enabled": True},
        {"key": "permanent_address", "label": "Nơi thường trú", "enabled": True},
    ]

    out_file = tmp_path / "test_formula.xlsx"
    export_records_to_excel([rec_inject], active_columns, str(out_file))

    wb = openpyxl.load_workbook(str(out_file))
    ws = wb.active
    # Formula character must be prefixed with single quote
    assert ws.cell(row=2, column=2).value == "'=cmd|' /C calc'!A0"
    assert ws.cell(row=2, column=3).value == "'+123456789"
