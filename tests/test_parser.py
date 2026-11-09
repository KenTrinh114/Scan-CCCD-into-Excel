"""Unit tests for CCCD parser, date formatting, and expiry calculations."""

from datetime import datetime
from pathlib import Path
import pytest

from src.parser import (
    build_record,
    calculate_age,
    calculate_cccd_expiry,
    parse_vn_date,
)


def test_parse_vn_date_valid():
    dt = parse_vn_date("15081999")
    assert dt is not None
    assert dt.day == 15
    assert dt.month == 8
    assert dt.year == 1999


def test_parse_vn_date_invalid():
    assert parse_vn_date("") is None
    assert parse_vn_date("invalid") is None
    assert parse_vn_date("32012020") is None  # Invalid day
    assert parse_vn_date("29022021") is None  # Not a leap year
    assert parse_vn_date("150899") is None  # Too short


def test_calculate_age():
    dob = datetime(2000, 1, 1)
    target = datetime(2026, 1, 1).date()
    assert calculate_age(dob, target) == "26"


def test_calculate_cccd_expiry():
    # Born 15/08/1999.
    # Milestone 25: 15/08/2024 (2 years before is 15/08/2022).
    # If issued on 20/05/2021 (< 15/08/2022), expires at age 25: 15/08/2024.
    dob = datetime(1999, 8, 15)
    issue_early = datetime(2021, 5, 20)
    assert calculate_cccd_expiry(dob, issue_early) == "15/08/2024"

    # If issued on 01/01/2023 (within 2 years before 25), extends to age 40: 15/08/2039.
    issue_near_25 = datetime(2023, 1, 1)
    assert calculate_cccd_expiry(dob, issue_near_25) == "15/08/2039"

    # If citizen is 59 years old and issued card -> "Không thời hạn"
    dob_senior = datetime(1960, 1, 1)
    issue_senior = datetime(2020, 1, 1)
    assert calculate_cccd_expiry(dob_senior, issue_senior) == "Không thời hạn"


def test_standard_2021_cccd_record():
    file_path = Path("IMG_001.jpg")
    qr_text = "079099001234|025123456|Nguyễn Văn A|15081999|Nam|123 Lê Lợi, Q1, TP.HCM|20052021"
    rec = build_record(file_path, qr_text, "OK")

    assert rec["_is_error"] is False
    assert rec["source_file"] == "IMG_001.jpg"
    assert rec["status"] == "Thành công"
    assert rec["cccd_number"] == "079099001234"
    assert rec["old_cmnd"] == "025123456"
    assert rec["full_name"] == "Nguyễn Văn A"
    assert rec["dob"] == "15/08/1999"
    assert rec["sex"] == "Nam"
    assert rec["birth_province"] == "TP. Hồ Chí Minh"
    assert rec["permanent_address"] == "123 Lê Lợi, Q1, TP.HCM"
    assert rec["issue_date"] == "20/05/2021"
    assert rec["expiry_date"] == "15/08/2024"
    assert rec["extra_info"] == ""


def test_payload_missing_old_cmnd():
    file_path = Path("IMG_002.png")
    qr_text = "079099001234||Nguyễn Văn A|15081999|Nam|123 Lê Lợi|20052021"
    rec = build_record(file_path, qr_text, "OK")

    assert rec["_is_error"] is False
    assert rec["old_cmnd"] == ""
    assert rec["cccd_number"] == "079099001234"
    assert rec["full_name"] == "Nguyễn Văn A"


def test_payload_corrupted_date():
    file_path = Path("IMG_003.jpg")
    qr_text = "079099001234|025123456|Nguyễn Văn A|99999999|Nam|123 Lê Lợi|INVALID_DATE"
    rec = build_record(file_path, qr_text, "OK")

    assert rec["_is_error"] is False
    assert rec["dob"] == ""
    assert rec["age"] == ""
    assert rec["issue_date"] == ""
    assert rec["expiry_date"] == ""
    assert rec["status"] == "Thành công"


def test_extended_2024_card_record():
    file_path = Path("IMG_004.jpg")
    qr_text = "001099001234||Trần Thị B|01012005|Nữ|Hà Nội|10072024|Extra1|Extra2"
    rec = build_record(file_path, qr_text, "OK")

    assert rec["_is_error"] is False
    assert rec["birth_province"] == "Hà Nội"
    assert rec["extra_info"] == "Extra1; Extra2"
    assert rec["status"] == "Thành công"


def test_unscannable_image_record():
    file_path = Path("IMG_FAILED.jpg")
    rec = build_record(file_path, None, "UNREADABLE")

    assert rec["_is_error"] is True
    assert rec["source_file"] == "IMG_FAILED.jpg"
    assert "Không đọc được mã QR" in rec["status"]
    assert rec["cccd_number"] == ""
    assert rec["full_name"] == ""
    assert rec["dob"] == ""


def test_encrypted_vneid_qr_record():
    file_path = Path("VNEID_SCREENSHOT.jpg")
    rec = build_record(file_path, None, "WRONG_QR_TYPE")

    assert rec["_is_error"] is True
    assert rec["source_file"] == "VNEID_SCREENSHOT.jpg"
    assert "VNeID" in rec["status"]
    assert rec["cccd_number"] == ""
    assert rec["full_name"] == ""
