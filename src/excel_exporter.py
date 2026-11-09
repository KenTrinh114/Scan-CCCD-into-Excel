"""Openpyxl-based generator for exporting CCCD records to new or existing Excel files."""

import shutil
from typing import Any
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def _get_styling_objects():
    thin_border_side = Side(border_style="thin", color="B0BEC5")
    cell_border = Border(
        left=thin_border_side,
        right=thin_border_side,
        top=thin_border_side,
        bottom=thin_border_side,
    )
    header_font = Font(name="Arial", size=11, bold=True, color="1A237E")
    header_fill = PatternFill(
        start_color="D9E1F2", end_color="D9E1F2", fill_type="solid"
    )
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    error_fill = PatternFill(
        start_color="FFEBEE", end_color="FFEBEE", fill_type="solid"
    )
    error_font = Font(name="Arial", size=10, color="B71C1C")
    error_bold_font = Font(name="Arial", size=10, bold=True, color="B71C1C")

    regular_font = Font(name="Arial", size=10, color="212121")
    align_left = Alignment(horizontal="left", vertical="center")
    align_center = Alignment(horizontal="center", vertical="center")

    return {
        "border": cell_border,
        "header_font": header_font,
        "header_fill": header_fill,
        "header_align": header_align,
        "error_fill": error_fill,
        "error_font": error_font,
        "error_bold_font": error_bold_font,
        "regular_font": regular_font,
        "align_left": align_left,
        "align_center": align_center,
    }


def export_records_to_excel(
    records: list[dict[str, Any]],
    active_columns: list[dict[str, Any]],
    output_path: str,
) -> None:
    """
    Export records to a brand new Excel (.xlsx) file.
    Respects custom column order, preserves leading zeros for CCCD/CMND numbers,
    highlights error rows in red, and auto-adjusts column widths.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Danh sách CCCD"

    st = _get_styling_objects()

    # Write Header Row (Row 1)
    for col_idx, col in enumerate(active_columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col["label"])
        cell.font = st["header_font"]
        cell.fill = st["header_fill"]
        cell.alignment = st["header_align"]
        cell.border = st["border"]
    ws.row_dimensions[1].height = 28

    # Write Data Rows (Row 2..N)
    has_source_col = any(c["key"] == "source_file" for c in active_columns)
    for row_idx, rec in enumerate(records, start=2):
        is_error = rec.get("_is_error", False)
        ws.row_dimensions[row_idx].height = 22

        for col_idx, col in enumerate(active_columns, start=1):
            key = col["key"]
            raw_val = rec.get(key, "")
            if key == "status" and is_error and not has_source_col:
                val_str = f"[{rec.get('source_file', '')}] {raw_val}"
            else:
                val_str = str(raw_val) if raw_val is not None else ""

            if key not in ("cccd_number", "old_cmnd") and val_str.startswith(("=", "+", "-", "@")):
                val_str = f"'{val_str}"

            cell = ws.cell(row=row_idx, column=col_idx, value=val_str)
            cell.border = st["border"]

            # Explicit text format to preserve leading zeros
            if key in ("cccd_number", "old_cmnd"):
                cell.number_format = "@"

            # Error vs Normal formatting
            if is_error:
                cell.fill = st["error_fill"]
                if key == "status":
                    cell.font = st["error_bold_font"]
                else:
                    cell.font = st["error_font"]
            else:
                cell.font = st["regular_font"]

            # Alignment based on data type
            if key in ("dob", "issue_date", "expiry_date", "sex", "age", "status"):
                cell.alignment = st["align_center"]
            else:
                cell.alignment = st["align_left"]

    # Auto-Fit Column Widths
    for col_idx, col in enumerate(active_columns, start=1):
        col_letter = get_column_letter(col_idx)
        max_len = len(str(col.get("label", "")))
        for row in range(2, len(records) + 2):
            cell_val = str(ws.cell(row=row, column=col_idx).value or "")
            if len(cell_val) > max_len:
                max_len = len(cell_val)
        fitted_width = max(12, min(50, max_len + 4))
        ws.column_dimensions[col_letter].width = fitted_width

    # Freeze header row
    ws.freeze_panes = "A2"

    wb.save(output_path)


def append_records_to_excel(
    records: list[dict[str, Any]],
    active_columns: list[dict[str, Any]],
    target_path: str,
) -> int:
    """
    Append records to an existing Excel (.xlsx) file.
    Validates that the existing sheet has the EXACT SAME number of columns as active_columns.
    If the column count does NOT match, raises ValueError and halts appending.
    Preserves leading zeros and error row formatting.
    Returns the number of appended records.
    """
    wb = openpyxl.load_workbook(target_path)
    ws = wb.active

    # Determine number of non-empty columns and header labels in row 1
    existing_col_count = 0
    existing_headers: list[str] = []
    for col_idx in range(1, ws.max_column + 1):
        val = ws.cell(row=1, column=col_idx).value
        if val is not None and str(val).strip() != "":
            existing_col_count = col_idx
            existing_headers.append(str(val).strip())
        else:
            break

    required_col_count = len(active_columns)
    if existing_col_count != required_col_count:
        raise ValueError(
            f"Số lượng cột không khớp!\n"
            f"File Excel hiện tại có {existing_col_count} cột, nhưng bạn đang chọn {required_col_count} cột để xuất.\n"
            f"Vui lòng điều chỉnh lại danh sách cột hoặc chọn file Excel phù hợp."
        )

    # Validate header names match
    required_headers = [str(col.get("label", "")).strip() for col in active_columns]
    mismatched = []
    for idx, (ex_h, req_h) in enumerate(zip(existing_headers, required_headers), start=1):
        if ex_h != req_h:
            mismatched.append(f"  • Cột {idx}: file có '{ex_h}', cấu hình xuất là '{req_h}'")
    if mismatched:
        details = "\n".join(mismatched)
        raise ValueError(
            f"Tiêu đề các cột không khớp với file Excel hiện tại!\n\n"
            f"{details}\n\n"
            f"Vui lòng sắp xếp lại thứ tự hoặc đổi tên cột cho khớp trước khi ghi tiếp."
        )

    st = _get_styling_objects()
    start_row = ws.max_row + 1
    has_source_col = any(c["key"] == "source_file" for c in active_columns)

    for row_offset, rec in enumerate(records):
        current_row = start_row + row_offset
        is_error = rec.get("_is_error", False)
        ws.row_dimensions[current_row].height = 22

        for col_idx, col in enumerate(active_columns, start=1):
            key = col["key"]
            raw_val = rec.get(key, "")
            if key == "status" and is_error and not has_source_col:
                val_str = f"[{rec.get('source_file', '')}] {raw_val}"
            else:
                val_str = str(raw_val) if raw_val is not None else ""

            if key not in ("cccd_number", "old_cmnd") and val_str.startswith(("=", "+", "-", "@")):
                val_str = f"'{val_str}"

            cell = ws.cell(row=current_row, column=col_idx, value=val_str)
            cell.border = st["border"]

            if key in ("cccd_number", "old_cmnd"):
                cell.number_format = "@"

            if is_error:
                cell.fill = st["error_fill"]
                if key == "status":
                    cell.font = st["error_bold_font"]
                else:
                    cell.font = st["error_font"]
            else:
                cell.font = st["regular_font"]

            if key in ("dob", "issue_date", "expiry_date", "sex", "age", "status"):
                cell.alignment = st["align_center"]
            else:
                cell.alignment = st["align_left"]

    # Auto-adjust column widths if newly added rows contain wider values
    for col_idx, col in enumerate(active_columns, start=1):
        col_letter = get_column_letter(col_idx)
        current_w = ws.column_dimensions[col_letter].width or 12
        max_len = int(current_w)
        for row in range(start_row, start_row + len(records)):
            cell_val = str(ws.cell(row=row, column=col_idx).value or "")
            if len(cell_val) > max_len:
                max_len = len(cell_val)
        ws.column_dimensions[col_letter].width = max(12, min(50, max_len + 4))

    # Create automated .bak backup safety copy before overwriting
    try:
        shutil.copy2(target_path, f"{target_path}.bak")
    except Exception:
        pass

    wb.save(target_path)
    return len(records)
