"""Tests for bulk upload with two-stage priority processing (passed images handled first)."""

from pathlib import Path
import queue
import threading
import time
import cv2
import numpy as np
import zxingcpp

from src.qr_engine import CCCDQRScanner
from src.parser import build_record
from src.gui import CCCDScannerApp


def test_bulk_upload_handles_passed_images_first(tmp_path: Path):
    """
    Test bulk upload scenario:
    10 scannable CCCD cards mixed with 10 unscannable images.
    Verifies that all 10 scannable cards finish FIRST before unscannable images finish rescue.
    """
    scanner = CCCDQRScanner()

    # 1. Create 10 scannable card images
    raw_text = "091202004905||LƯU HỮU HẬU|28122002|Nam|Kiên Giang|28122022"
    barcode = zxingcpp.create_barcode(raw_text, zxingcpp.BarcodeFormat.QRCode)
    qr_img = np.array(zxingcpp.write_barcode_to_image(barcode))
    qh, qw = qr_img.shape[:2]

    scannable_paths = []
    for i in range(10):
        canvas = np.full((500, 800), 220, dtype=np.uint8)
        canvas[50 : 50 + qh, 600 : 600 + qw] = qr_img
        p = tmp_path / f"scannable_{i:02d}.png"
        cv2.imwrite(str(p), canvas)
        scannable_paths.append(p)

    # 2. Create 10 unscannable card images (blank/corrupted)
    unscannable_paths = []
    for i in range(10):
        canvas = np.full((500, 800), 200, dtype=np.uint8)
        # Add some text lines but no QR
        cv2.line(canvas, (100, 100), (500, 100), 50, 3)
        p = tmp_path / f"unscannable_{i:02d}.png"
        cv2.imwrite(str(p), canvas)
        unscannable_paths.append(p)

    # 3. Interleave them so unscannable files are at the very front of the queue
    # [unscannable_0, scannable_0, unscannable_1, scannable_1, ...]
    interleaved_paths = []
    for u, s in zip(unscannable_paths, scannable_paths):
        interleaved_paths.append(u)
        interleaved_paths.append(s)

    # 4. Run through two-stage priority queue with 4 worker threads
    task_queue = queue.PriorityQueue()
    result_queue = queue.Queue()
    task_counter = 0
    lock = threading.Lock()

    # Enqueue all as Stage 1 FAST (Priority 1)
    for p in interleaved_paths:
        task_counter += 1
        task_queue.put((1, task_counter, p, "FAST"))

    completion_order = []

    def worker():
        nonlocal task_counter
        w_scanner = CCCDQRScanner()
        while True:
            try:
                prio, tid, fpath, stage = task_queue.get(timeout=0.2)
            except queue.Empty:
                if task_queue.empty():
                    break
                continue

            if stage == "FAST":
                qr, note = w_scanner.scan_fast(fpath)
                if qr:
                    rec = build_record(fpath, qr, note or "OK")
                    rec["_is_pending"] = False
                    result_queue.put((str(fpath), rec))
                    completion_order.append(("SCANNABLE", fpath.name))
                else:
                    with lock:
                        task_counter += 1
                        new_tid = task_counter
                    task_queue.put((2, new_tid, fpath, "RESCUE"))
            else:
                qr, note = w_scanner.scan_rescue(fpath)
                rec = build_record(fpath, qr, note)
                rec["_is_pending"] = False
                result_queue.put((str(fpath), rec))
                completion_order.append(("UNSCANNABLE", fpath.name))

            task_queue.task_done()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(completion_order) == 20

    # The first 10 completed items MUST be the 10 scannable images!
    first_10_types = [item[0] for item in completion_order[:10]]
    last_10_types = [item[0] for item in completion_order[10:]]

    assert first_10_types == ["SCANNABLE"] * 10, f"Expected scannable first, got: {first_10_types}"
    assert last_10_types == ["UNSCANNABLE"] * 10, f"Expected unscannable last, got: {last_10_types}"


def test_table_sorting_by_status(shared_root):
    """Verify that clicking the 'status' header sorts passed images to the top."""
    app = CCCDScannerApp(shared_root)

    # Add 2 error records and 2 success records
    app.records = [
        {"source_file": "err1.jpg", "status": "Cần chụp lại", "_is_error": True, "_is_pending": False},
        {"source_file": "ok1.jpg", "status": "Quét thành công", "_is_error": False, "_is_pending": False, "cccd_number": "123"},
        {"source_file": "err2.jpg", "status": "Cần chụp lại", "_is_error": True, "_is_pending": False},
        {"source_file": "ok2.jpg", "status": "Quét thành công", "_is_error": False, "_is_pending": False, "cccd_number": "456"},
    ]

    # Sort by status
    app._on_sort_column("status")

    # Success records must be at index 0 and 1
    assert app.records[0]["_is_error"] is False
    assert app.records[1]["_is_error"] is False
    assert app.records[2]["_is_error"] is True
    assert app.records[3]["_is_error"] is True


def test_app_scanning_pipeline_completes_all_records(tmp_path: Path, shared_root):
    """
    Test full end-to-end scanning pipeline within CCCDScannerApp.
    Ensures that all images (both scannable and unscannable) complete processing,
    no rows remain stuck in '_is_pending = True', and the worker queue cleans up cleanly.
    """
    app = CCCDScannerApp(shared_root)

    # Create 3 scannable and 3 unscannable images
    paths = []
    for i in range(3):
        raw_text = f"09120200490{i}||NGUYEN VAN {i}|28122000|Nam|Ha Noi|28122020"
        barcode = zxingcpp.create_barcode(raw_text, zxingcpp.BarcodeFormat.QRCode)
        qr_img = np.array(zxingcpp.write_barcode_to_image(barcode))
        qh, qw = qr_img.shape[:2]
        canvas = np.full((400, 600), 220, dtype=np.uint8)
        canvas[40 : 40 + qh, 400 : 400 + qw] = qr_img
        p = tmp_path / f"app_ok_{i}.png"
        cv2.imwrite(str(p), canvas)
        paths.append(p)

        # Unscannable
        p_err = tmp_path / f"app_err_{i}.png"
        canvas_err = np.full((400, 600), 180, dtype=np.uint8)
        cv2.imwrite(str(p_err), canvas_err)
        paths.append(p_err)

    app._start_scanning(paths)

    # Pump GUI events until processing finishes (timeout 8.0s)
    start_time = time.time()
    while time.time() - start_time < 8.0:
        shared_root.update()
        time.sleep(0.05)
        pending = sum(1 for r in app.records if r.get("_is_pending", False))
        if pending == 0 and not app.is_scanning:
            break

    # Verification:
    # 1. Total records must be 6
    assert len(app.records) == 6
    # 2. No records are still pending
    assert sum(1 for r in app.records if r.get("_is_pending", False)) == 0
    # 3. Exactly 3 successes and 3 errors
    assert app.success_count == 3
    assert app.error_count == 3
    # 4. Scanner is no longer in scanning state
    assert app.is_scanning is False
