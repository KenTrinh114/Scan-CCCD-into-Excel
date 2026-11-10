"""Fault-tolerant Vietnamese CCCD QR payload parser, date formatter, and expiry calculator."""

from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.config import DEFAULT_COLUMNS, PROVINCE_CODES

_EMPTY_RECORD_TEMPLATE: dict[str, Any] = {col["key"]: "" for col in DEFAULT_COLUMNS}


def parse_vn_date(raw_ddmmyyyy: str) -> datetime | None:
    """
    Parse an 8-digit Vietnamese date string (DDMMYYYY) into a datetime object.
    Returns None if format or date values are invalid.
    """
    if not raw_ddmmyyyy:
        return None
    s = raw_ddmmyyyy.strip()
    if len(s) != 8 or not s.isdigit():
        return None
    try:
        return datetime.strptime(s, "%d%m%Y")
    except ValueError:
        return None


def calculate_age(dob: datetime, target_date: date | None = None) -> str:
    """
    Calculate age in whole years from date of birth.
    Defaults to calculating relative to today.
    """
    if target_date is None:
        target_date = date.today()
    dob_date = dob.date() if isinstance(dob, datetime) else dob
    age = target_date.year - dob_date.year - (
        (target_date.month, target_date.day) < (dob_date.month, dob_date.day)
    )
    return str(max(0, age))


def _add_years(d: date, years: int) -> date:
    """Add years to a date, falling back to Feb 28 if target year is not a leap year."""
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(year=d.year + years, day=28)


def calculate_cccd_expiry(dob: datetime, issue_date: datetime) -> str:
    """
    Calculate statutory CCCD card expiry under Article 21 of the Law on Citizen Identification.
    Milestones are at ages 25, 40, and 60.
    If the card is issued within 2 years prior to reaching a milestone age,
    its validity extends to the subsequent milestone age.
    If issued at or after age 58 (within 2 years of 60, or after 60), it is valid indefinitely ('Không thời hạn').
    """
    dob_d = dob.date() if isinstance(dob, datetime) else dob
    issue_d = issue_date.date() if isinstance(issue_date, datetime) else issue_date

    for age_limit in (25, 40, 60):
        milestone_date = _add_years(dob_d, age_limit)
        two_years_before = _add_years(milestone_date, -2)
        if issue_d < two_years_before:
            return milestone_date.strftime("%d/%m/%Y")

    return "Không thời hạn"


def build_record(file_path: Path, qr_text: str | None, scan_note: str) -> dict[str, Any]:
    """
    Build a standardized record dictionary for a scanned image file.
    Always includes all 13 schema keys initialized to empty string,
    plus internal keys '_is_error' and '_full_path'.
    """
    record: dict[str, Any] = dict(_EMPTY_RECORD_TEMPLATE)
    record["_is_error"] = False
    record["_full_path"] = str(file_path)
    record["source_file"] = file_path.name

    # Case 1: Unscannable or wrong QR type
    if qr_text is None:
        record["_is_error"] = True
        if scan_note == "WRONG_QR_TYPE":
            record["status"] = "Cần chụp lại: Mã QR VNeID điện tử (vui lòng chụp thẻ CCCD vật lý)"
        else:
            record["status"] = "Cần chụp lại: Không đọc được mã QR (ảnh mờ hoặc bị lóa sáng)"
        return record

    # Case 2: QR text decoded successfully
    parts = [p.strip() for p in qr_text.strip().split("|")]

    def get_part(idx: int) -> str:
        return parts[idx] if idx < len(parts) else ""

    cccd = get_part(0)
    record["cccd_number"] = cccd
    record["old_cmnd"] = get_part(1)
    record["full_name"] = get_part(2)

    dob_dt = parse_vn_date(get_part(3))
    if dob_dt:
        record["dob"] = dob_dt.strftime("%d/%m/%Y")
        record["age"] = calculate_age(dob_dt)

    record["sex"] = get_part(4)

    if len(cccd) >= 3:
        record["birth_province"] = PROVINCE_CODES.get(cccd[:3], "")

    record["permanent_address"] = get_part(5)

    issue_dt = parse_vn_date(get_part(6))
    if issue_dt:
        record["issue_date"] = issue_dt.strftime("%d/%m/%Y")

    if dob_dt and issue_dt:
        record["expiry_date"] = calculate_cccd_expiry(dob_dt, issue_dt)

    if len(parts) > 7:
        extra = [p for p in parts[7:] if p]
        record["extra_info"] = "; ".join(extra)

    record["status"] = "Thành công"
    return record
