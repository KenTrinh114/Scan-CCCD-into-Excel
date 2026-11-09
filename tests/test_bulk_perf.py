"""Unit tests for high-throughput bulk import performance and UI smoothness."""

import time
import tkinter as tk
from unittest.mock import MagicMock
import pytest

from src.gui import CCCDScannerApp, DEFAULT_COLUMNS


def test_bulk_column_width_heuristic_performance(shared_root: tk.Tk):
    """
    Verify that _adjust_all_column_widths handles 1,000 records almost instantaneously (<50ms)
    thanks to the string-length pre-filtering heuristic, avoiding font.measure overhead.
    """
    app = CCCDScannerApp(shared_root)

    # Generate 1,000 mock records with varied lengths
    mock_records = []
    for i in range(1000):
        mock_records.append({
            "source_file": f"card_scan_batch_{i:04d}.jpg",
            "status": "Quét thành công",
            "cccd_number": f"0123456{i:05d}",
            "full_name": f"NGUYEN VAN {i}",
            "dob": "01/01/1990",
            "gender": "Nam",
            "permanent_address": f"So {i} Duong Le Loi, Phuong Ben Nghe, Quan 1, TP. Ho Chi Minh",
            "date_of_issue": "01/01/2021",
            "date_of_expiry": "01/01/2030",
            "_is_pending": False,
            "_is_error": False,
        })
    app.records = mock_records

    # Benchmark _adjust_all_column_widths
    t0 = time.perf_counter()
    app._adjust_all_column_widths()
    elapsed = time.perf_counter() - t0

    # Must complete well within 100ms (typically <15ms)
    assert elapsed < 0.1, f"Expected < 100ms for 1,000 records, took {elapsed * 1000:.2f}ms"

    # Verify permanent_address expanded to accommodate long string
    addr_w = int(app.table.column("permanent_address", "width"))
    assert addr_w > 200, f"Expected permanent_address column to expand, got width {addr_w}"
    assert addr_w <= 850, f"Expected column width to respect 850px max cap, got {addr_w}"


def test_bulk_spinner_animation_throttles_updates(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """
    Verify that _animate_spinner only updates visible rows when large bulk queue is pending,
    preventing event loop starvation and UI freezes.
    """
    app = CCCDScannerApp(shared_root)
    app.is_scanning = True

    # Pre-populate 500 pending records
    for i in range(500):
        item_id = app.table.insert("", tk.END, values=[f"file_{i}.jpg", "Đang xử lý..."])
        rec = {
            "source_file": f"file_{i}.jpg",
            "status": "Đang xử lý...",
            "_is_pending": True,
            "_is_error": False,
            "_task_id": i + 1,
            "_rec_idx": i,
        }
        app.records.append(rec)
        app.item_to_rec_idx[item_id] = i
        app.task_id_to_item_id[i + 1] = item_id
        app.task_id_to_rec[i + 1] = rec

    # Mock table.set to count how many times cells are modified
    set_calls = []
    orig_set = app.table.set
    def mock_set(item, column=None, value=None):
        set_calls.append(item)
        return orig_set(item, column, value)

    monkeypatch.setattr(app.table, "set", mock_set)

    # Mock yview to simulate top of viewport showing first 25 rows
    monkeypatch.setattr(app.table, "yview", lambda: (0.0, 0.05))

    # Trigger spinner frame animation
    app._animate_spinner()

    # With 500 pending items, table.set must NOT be called 500 times.
    # It should only animate the ~25-30 visible rows in viewport.
    assert len(set_calls) < 40, f"Expected <40 row updates for viewport, got {len(set_calls)}"
    assert len(set_calls) > 0, "Expected visible rows to be animated"


def test_bulk_process_queue_no_jitter_and_adaptive_consumption(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """
    Verify that:
    1. During bulk imports (total_queued > 5), table.see(item_id) is NOT called on every result,
       preventing erratic scroll jumping and viewport jitter.
    2. Large bursts in result_queue (>50 items) scale the consumption batch limit up to 100
       so the GUI drains worker outputs immediately without falling behind.
    """
    app = CCCDScannerApp(shared_root)
    app.total_queued = 80  # Bulk queue

    # Populate 60 items directly into result_queue to simulate fast worker output
    for i in range(60):
        item_id = app.table.insert("", tk.END, values=[f"img_{i}.jpg", "Đang xử lý..."])
        rec = {
            "source_file": f"img_{i}.jpg",
            "status": "Đang xử lý...",
            "_is_pending": True,
            "_is_error": False,
            "_task_id": i + 1,
            "_rec_idx": i,
        }
        app.records.append(rec)
        app.item_to_rec_idx[item_id] = i
        app.task_id_to_item_id[i + 1] = item_id
        app.task_id_to_rec[i + 1] = rec

        finished = {
            "source_file": f"img_{i}.jpg",
            "status": "Quét thành công",
            "cccd_number": f"012345{i:06d}",
            "_is_pending": False,
            "_is_error": False,
            "_task_id": i + 1,
        }
        app.result_queue.put((i + 1, finished))

    see_calls = []
    monkeypatch.setattr(app.table, "see", lambda item: see_calls.append(item))

    # Call _process_queue
    app._process_queue()

    # 1. table.see must NOT have been called (no jitter)
    assert len(see_calls) == 0, f"table.see should be bypassed for bulk queues, but was called {len(see_calls)} times"

    # 2. Since 60 items were in queue, dynamic batch limit scaled up and processed all 60 items in one tick
    assert app.processed_count == 60, f"Expected 60 processed items, got {app.processed_count}"
    assert app.result_queue.empty()


def test_single_import_calls_see_for_visibility(shared_root: tk.Tk, monkeypatch: pytest.MonkeyPatch):
    """
    Verify that when importing a single file (total_queued <= 5), table.see IS called
    so the user immediately sees the newly inserted row.
    """
    app = CCCDScannerApp(shared_root)
    app.total_queued = 1  # Single file import

    item_id = app.table.insert("", tk.END, values=["single.jpg", "Đang xử lý..."])
    rec = {
        "source_file": "single.jpg",
        "status": "Đang xử lý...",
        "_is_pending": True,
        "_is_error": False,
        "_task_id": 1,
        "_rec_idx": 0,
    }
    app.records.append(rec)
    app.item_to_rec_idx[item_id] = 0
    app.task_id_to_item_id[1] = item_id
    app.task_id_to_rec[1] = rec

    app.result_queue.put((1, {
        "source_file": "single.jpg",
        "status": "Quét thành công",
        "_is_pending": False,
        "_is_error": False,
        "_task_id": 1,
    }))

    see_calls = []
    monkeypatch.setattr(app.table, "see", lambda item: see_calls.append(item))

    app._process_queue()

    assert len(see_calls) == 1, "Single import should scroll to row via table.see"


def test_clear_list_resets_task_mappings(shared_root: tk.Tk):
    """Verify _on_clear_list completely clears task_id_to_rec and task_id_to_item_id."""
    app = CCCDScannerApp(shared_root)
    app.is_scanning = False

    app.task_id_to_rec[1] = {"_task_id": 1}
    app.task_id_to_item_id[1] = "I001"
    app.records = [{"_task_id": 1}]

    app._on_clear_list()

    assert len(app.task_id_to_rec) == 0
    assert len(app.task_id_to_item_id) == 0
    assert len(app.records) == 0
