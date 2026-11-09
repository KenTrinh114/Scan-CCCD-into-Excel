"""Pre-build script to download WeChat QR Caffe models into assets/wechat_models/."""

import os
import sys
import urllib.request
from pathlib import Path

BASE_URL = "https://raw.githubusercontent.com/WeChatCV/opencv_3rdparty/wechat_qrcode/"
MODEL_FILES = [
    "detect.prototxt",
    "detect.caffemodel",
    "sr.prototxt",
    "sr.caffemodel",
]


def download_models(target_dir: Path | None = None) -> bool:
    if target_dir is None:
        target_dir = Path(__file__).resolve().parent / "assets" / "wechat_models"

    target_dir.mkdir(parents=True, exist_ok=True)
    all_ok = True

    for filename in MODEL_FILES:
        dest_path = target_dir / filename
        if dest_path.exists() and dest_path.stat().st_size > 0:
            print(f"[OK] {filename} already exists ({dest_path.stat().st_size} bytes).")
            continue

        url = BASE_URL + filename
        print(f"Downloading {filename} from {url}...")
        try:
            # Download with a User-Agent to avoid HTTP 403 blocks
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as response, open(dest_path, "wb") as out_file:
                chunk = response.read(8192)
                while chunk:
                    out_file.write(chunk)
                    chunk = response.read(8192)

            if dest_path.exists() and dest_path.stat().st_size > 0:
                print(f"[OK] Downloaded {filename} ({dest_path.stat().st_size} bytes).")
            else:
                print(f"[ERROR] Downloaded {filename} but file is empty!")
                all_ok = False
        except Exception as e:
            print(f"[ERROR] Failed to download {filename}: {e}")
            all_ok = False

    return all_ok


if __name__ == "__main__":
    success = download_models()
    if not success:
        sys.exit(1)
    print("All WeChat QR models are ready.")
