import sys
import tempfile
import time
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import cv2
import numpy as np
from src.qr_engine import CCCDQRScanner

scanner = CCCDQRScanner()

if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
    img_path = Path(sys.argv[1])
    temp_file = None
else:
    # Generate a realistic synthetic card canvas for benchmarking
    temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img_path = Path(temp_file.name)
    card = np.full((600, 950, 3), (230, 240, 230), dtype=np.uint8)
    card[150:450, 50:300] = 160
    for y in range(180, 480, 45):
        cv2.line(card, (350, y), (850, y), (60, 60, 60), 4)
    cv2.imwrite(str(img_path), card)

try:
    t0 = time.perf_counter()
    res, status = scanner.scan_image(img_path)
    t1 = time.perf_counter()
    print(f"Total scan_image duration: {(t1 - t0)*1000:.2f} ms | Status: {status}")
finally:
    if temp_file is not None and img_path.exists():
        try:
            img_path.unlink()
        except Exception:
            pass
