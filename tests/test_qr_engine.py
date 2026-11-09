"""Unit tests for CCCDQRScanner engine and image loading."""

from pathlib import Path
import cv2
import numpy as np
from src.qr_engine import CCCDQRScanner


def test_scanner_init():
    scanner = CCCDQRScanner()
    assert scanner.clahe is not None


def test_load_grayscale_invalid():
    scanner = CCCDQRScanner()
    assert scanner._load_grayscale(Path("non_existent_file.jpg")) is None


def test_load_grayscale_valid_synthetic(tmp_path: Path):
    img = np.full((100, 100), 128, dtype=np.uint8)
    img_path = tmp_path / "synthetic.png"
    cv2.imwrite(str(img_path), img)

    scanner = CCCDQRScanner()
    gray = scanner._load_grayscale(img_path)
    assert gray is not None
    assert gray.shape == (100, 100)


def test_load_grayscale_oversized_downscale(tmp_path: Path):
    # Test downscaling if > 1600px
    img = np.full((1800, 2400), 128, dtype=np.uint8)
    img_path = tmp_path / "oversized.png"
    cv2.imwrite(str(img_path), img)

    scanner = CCCDQRScanner()
    gray = scanner._load_grayscale(img_path)
    assert gray is not None
    assert max(gray.shape) == 1600


def test_scanner_pad_quiet_zone():
    scanner = CCCDQRScanner()
    small_block = np.zeros((10, 10), dtype=np.uint8)
    padded = scanner._pad_quiet_zone(small_block, pad=15)
    assert padded.shape == (40, 40)
    assert padded[0, 0] == 255
    assert padded[20, 20] == 0


def test_scan_image_synthetic_cccd_qr(tmp_path: Path):
    import zxingcpp

    scanner = CCCDQRScanner()
    raw_text = "091202004905||LƯU HỮU HẬU|28122002|Nam|Kiên Giang|28122022"
    barcode = zxingcpp.create_barcode(raw_text, zxingcpp.BarcodeFormat.QRCode)
    qr_img = np.array(zxingcpp.write_barcode_to_image(barcode))

    # Place QR in top-right of a simulated card canvas
    canvas = np.full((500, 800), 220, dtype=np.uint8)
    qh, qw = qr_img.shape[:2]
    canvas[50 : 50 + qh, 600 : 600 + qw] = qr_img

    img_path = tmp_path / "test_card.png"
    cv2.imwrite(str(img_path), canvas)

    result_text, status = scanner.scan_image(img_path)
    assert status == "OK"
    assert result_text == raw_text


def test_scan_image_unreadable_performance_budget(tmp_path: Path):
    """Ensure worst-case scan across all 5 rescue passes finishes within strict timing budget (< 300ms)."""
    import time

    scanner = CCCDQRScanner()
    # Create a realistic unreadable card canvas (card background with photo box and text lines, but corrupted/missing QR)
    card = np.full((600, 950, 3), (230, 240, 230), dtype=np.uint8)
    # Add fake portrait box
    card[150:450, 50:300] = 160
    # Add fake text lines
    for y in range(180, 480, 45):
        cv2.line(card, (350, y), (850, y), (60, 60, 60), 4)

    img_path = tmp_path / "unreadable_card.jpg"
    cv2.imwrite(str(img_path), card)

    t0 = time.perf_counter()
    res, status = scanner.scan_image(img_path)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert status == "UNREADABLE"
    assert res is None
    # Must finish well under 300ms (previously took 1500ms - 2500ms before optimization)
    assert elapsed_ms < 300.0, f"Scan took too long: {elapsed_ms:.2f}ms"


def test_load_color_valid(tmp_path: Path):
    scanner = CCCDQRScanner()
    bgr_img = np.zeros((100, 100, 3), dtype=np.uint8)
    bgr_img[:, :, 0] = 255  # Blue channel
    img_path = tmp_path / "blue_test.png"
    cv2.imwrite(str(img_path), bgr_img)

    loaded = scanner._load_color(img_path)
    assert loaded is not None
    assert loaded.shape == (100, 100, 3)
    assert loaded[0, 0, 0] == 255


