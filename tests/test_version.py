"""Tests for automated deploy version tracking (date & time stamping)."""

import re
import tkinter as tk
from pathlib import Path

from src.version import APP_VERSION, BUILD_TIME, __version__
from src.gui import CCCDScannerApp
import update_version


def test_version_format():
    """Verify version adheres to YYYY.MM.DD.HHMM format for date & time tracking."""
    assert __version__ == APP_VERSION
    assert re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$", APP_VERSION), f"Invalid version format: {APP_VERSION}"
    assert re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$", BUILD_TIME), f"Invalid build time format: {BUILD_TIME}"


def test_update_version_script(tmp_path: Path):
    """Verify stamp_version generates a valid timestamped version and updates files."""
    v = update_version.stamp_version()
    assert re.match(r"^\d{4}\.\d{2}\.\d{2}\.\d{4}$", v)

    iss_text = Path("installer.iss").read_text(encoding="utf-8")
    assert f"AppVersion={v}" in iss_text


def test_app_title_displays_version(shared_root: tk.Tk):
    """Verify that the GUI window title displays the deploy version number."""
    app = CCCDScannerApp(shared_root)
    title = shared_root.title()
    assert APP_VERSION in title
    assert "App quét CCCD cho Nger" in title
