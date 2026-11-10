"""
Script to synchronize application version metadata between src/version.py and installer.iss.
"""

from pathlib import Path
import re


import sys

def stamp_version(new_version: str | None = None) -> str:
    version_file = Path(__file__).parent / "src" / "version.py"
    iss_file = Path(__file__).parent / "installer.iss"

    if new_version:
        version_str = new_version
    else:
        content = version_file.read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        version_str = m.group(1) if m else "2.1.0"

    version_content = f'''"""Application version metadata."""

__version__ = "{version_str}"
BUILD_TIME = ""
APP_VERSION = __version__
'''
    version_file.write_text(version_content, encoding="utf-8")
    print(f"[VERSION] Synced src/version.py -> {version_str}")

    if iss_file.exists():
        iss_text = iss_file.read_text(encoding="utf-8")
        new_iss_text = re.sub(r"AppVersion=.*", f"AppVersion={version_str}", iss_text)
        iss_file.write_text(new_iss_text, encoding="utf-8")
        print(f"[VERSION] Synced installer.iss -> AppVersion={version_str}")

    return version_str


if __name__ == "__main__":
    cli_ver = sys.argv[1] if len(sys.argv) > 1 else None
    stamp_version(cli_ver)
