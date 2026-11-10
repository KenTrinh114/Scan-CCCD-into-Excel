"""Master column registry, 63 province codes, and JSON configuration persistence."""

import json
import os
from pathlib import Path
from typing import Any

# Default columns with order, Vietnamese headers, widths, and initial visibility
DEFAULT_COLUMNS: list[dict[str, Any]] = [
    {"key": "source_file", "label": "Tên file ảnh", "enabled": False, "width": 160},
    {"key": "status", "label": "Trạng thái", "enabled": True, "width": 240},
    {"key": "cccd_number", "label": "Số định danh / CCCD", "enabled": True, "width": 130},
    {"key": "old_cmnd", "label": "Số CMND cũ", "enabled": False, "width": 110},
    {"key": "full_name", "label": "Họ và tên", "enabled": True, "width": 180},
    {"key": "dob", "label": "Ngày sinh", "enabled": True, "width": 100},
    {"key": "age", "label": "Tuổi", "enabled": False, "width": 60},
    {"key": "sex", "label": "Giới tính", "enabled": True, "width": 80},
    {"key": "birth_province", "label": "Nơi đăng ký khai sinh", "enabled": False, "width": 160},
    {"key": "permanent_address", "label": "Nơi thường trú", "enabled": True, "width": 280},
    {"key": "issue_date", "label": "Ngày cấp", "enabled": True, "width": 100},
    {"key": "expiry_date", "label": "Có giá trị đến", "enabled": True, "width": 120},
    {"key": "extra_info", "label": "Thông tin mở rộng (Thẻ 2024)", "enabled": False, "width": 180},
]

# Official 63-province codes mapping from the first 3 digits of CCCD
PROVINCE_CODES: dict[str, str] = {
    "001": "Hà Nội", "002": "Hà Giang", "004": "Cao Bằng", "006": "Bắc Kạn",
    "008": "Tuyên Quang", "010": "Lào Cai", "011": "Điện Biên", "012": "Lai Châu",
    "014": "Sơn La", "015": "Yên Bái", "017": "Hòa Bình", "019": "Thái Nguyên",
    "020": "Lạng Sơn", "022": "Quảng Ninh", "024": "Bắc Giang", "025": "Phú Thọ",
    "026": "Vĩnh Phúc", "027": "Bắc Ninh", "030": "Hải Dương", "031": "Hải Phòng",
    "033": "Hưng Yên", "034": "Thái Bình", "035": "Hà Nam", "036": "Nam Định",
    "037": "Ninh Bình", "038": "Thanh Hóa", "040": "Nghệ An", "042": "Hà Tĩnh",
    "044": "Quảng Bình", "045": "Quảng Trị", "046": "Thừa Thiên Huế", "048": "Đà Nẵng",
    "049": "Quảng Nam", "051": "Quảng Ngãi", "052": "Bình Định", "054": "Phú Yên",
    "056": "Khánh Hòa", "058": "Ninh Thuận", "060": "Bình Thuận", "062": "Kon Tum",
    "064": "Gia Lai", "066": "Đắk Lắk", "067": "Đắk Nông", "068": "Lâm Đồng",
    "070": "Bình Phước", "072": "Tây Ninh", "074": "Bình Dương", "075": "Đồng Nai",
    "077": "Bà Rịa - Vũng Tàu", "079": "TP. Hồ Chí Minh", "080": "Long An",
    "082": "Tiền Giang", "083": "Bến Tre", "084": "Trà Vinh", "086": "Vĩnh Long",
    "087": "Đồng Tháp", "089": "An Giang", "091": "Kiên Giang", "092": "Cần Thơ",
    "093": "Hậu Giang", "094": "Sóc Trăng", "095": "Bạc Liêu", "096": "Cà Mau"
}


def get_app_config_dir() -> Path:
    """Return the base config directory in %LOCALAPPDATA%\\CCCDScanner, creating it if needed."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")
    config_dir = Path(local_app_data) / "CCCDScanner"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file_path() -> Path:
    """Return the path to column_config.json in %LOCALAPPDATA%\\CCCDScanner."""
    return get_app_config_dir() / "column_config.json"


def get_theme_file_path() -> Path:
    """Return the path to theme_config.json in %LOCALAPPDATA%\\CCCDScanner."""
    return get_app_config_dir() / "theme_config.json"


def load_theme_config() -> str:
    """Load user's chosen UI theme ('light' or 'dark'). Default is 'light'."""
    theme_file = get_theme_file_path()
    if not theme_file.exists():
        return "light"
    try:
        with open(theme_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                theme = data.get("theme")
                if theme in ("light", "dark"):
                    return theme
                if theme == "grey":
                    return "light"
    except Exception:
        pass
    return "light"


def save_theme_config(theme: str) -> None:
    """Persist user's chosen UI theme to theme_config.json."""
    if theme not in ("light", "dark"):
        theme = "light"
    theme_file = get_theme_file_path()
    try:
        with open(theme_file, "w", encoding="utf-8") as f:
            json.dump({"theme": theme}, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save theme config: {e}")


def reset_to_default_columns() -> list[dict[str, Any]]:
    """Return a deep copy of DEFAULT_COLUMNS."""
    return [dict(col) for col in DEFAULT_COLUMNS]


def load_column_config() -> list[dict[str, Any]]:
    """
    Load column preferences from JSON file.
    Merge saved order/state with DEFAULT_COLUMNS so newly added schema keys
    never break older config files.
    """
    config_file = get_config_file_path()
    if not config_file.exists():
        return reset_to_default_columns()

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            saved_list = json.load(f)

        if not isinstance(saved_list, list):
            return reset_to_default_columns()

        # Build mapping of default column definitions
        defaults_by_key = {col["key"]: col for col in DEFAULT_COLUMNS}
        loaded_keys = set()
        result: list[dict[str, Any]] = []

        # First add saved columns that exist in defaults, preserving saved order and enabled flag
        for item in saved_list:
            if isinstance(item, dict) and "key" in item:
                k = item["key"]
                if k in defaults_by_key and k not in loaded_keys:
                    col_def = dict(defaults_by_key[k])
                    if "enabled" in item:
                        col_def["enabled"] = bool(item["enabled"])
                    result.append(col_def)
                    loaded_keys.add(k)

        # Append any default columns that were not present in saved config
        for col in DEFAULT_COLUMNS:
            if col["key"] not in loaded_keys:
                result.append(dict(col))

        return result
    except Exception:
        return reset_to_default_columns()


def save_column_config(columns: list[dict[str, Any]]) -> None:
    """Save the ordered list of columns and their enabled states to JSON."""
    config_file = get_config_file_path()
    data = [{"key": col["key"], "enabled": bool(col.get("enabled", True))} for col in columns]
    try:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save column config: {e}")
