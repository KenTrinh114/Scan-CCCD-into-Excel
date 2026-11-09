"""
Automated script to stamp current build/deploy date & time into application version metadata.
Updates:
1. src/version.py (__version__, BUILD_TIME, APP_VERSION)
2. installer.iss (AppVersion)
"""

from datetime import datetime
from pathlib import Path
import re


def stamp_version() -> str:
    now = datetime.now()
    # Format: YYYY.MM.DD.HHMM (e.g., 2026.11.08.1008)
    version_str = now.strftime("%Y.%m.%d.%H%M")
    build_time_str = now.strftime("%Y-%m-%d %H:%M")

    # 1. Update src/version.py
    version_file = Path(__file__).parent / "src" / "version.py"
    version_content = f'''"""Application version metadata updated automatically on build/deploy."""

__version__ = "{version_str}"
BUILD_TIME = "{build_time_str}"
APP_VERSION = __version__
'''
    version_file.write_text(version_content, encoding="utf-8")
    print(f"[VERSION] Updated src/version.py -> {version_str} ({build_time_str})")

    # 2. Update installer.iss
    iss_file = Path(__file__).parent / "installer.iss"
    if iss_file.exists():
        iss_text = iss_file.read_text(encoding="utf-8")
        new_iss_text = re.sub(r"AppVersion=.*", f"AppVersion={version_str}", iss_text)
        iss_file.write_text(new_iss_text, encoding="utf-8")
        print(f"[VERSION] Updated installer.iss -> AppVersion={version_str}")

    return version_str


if __name__ == "__main__":
    stamp_version()
