"""Tests for short version tracking and clean display."""

import re
import tkinter as tk
from pathlib import Path

from src.version import APP_VERSION, __version__
from src.gui import CCCDScannerApp
import update_version


def test_version_format():
    """Verify version adheres to short semantic version format."""
    assert __version__ == APP_VERSION
    assert re.match(r"^\d+\.\d+(\.\d+)?$", APP_VERSION), f"Invalid version format: {APP_VERSION}"


def test_update_version_script(tmp_path: Path):
    """Verify stamp_version syncs short version to installer.iss."""
    v = update_version.stamp_version()
    assert re.match(r"^\d+\.\d+(\.\d+)?$", v)

    iss_text = Path("installer.iss").read_text(encoding="utf-8")
    assert f"AppVersion={v}" in iss_text


def test_app_title_and_clean_version_display(shared_root: tk.Tk):
    """Verify GUI window title displays short version and empty state does not display update time."""
    app = CCCDScannerApp(shared_root)
    title = shared_root.title()
    assert APP_VERSION in title
    assert "App quét CCCD cho Nger" in title

    # Ensure update time is removed from display
    empty_version_text = app.lbl_empty_version.cget("text")
    assert f"Phiên bản: v{APP_VERSION}" in empty_version_text
    assert "Cập nhật:" not in empty_version_text
