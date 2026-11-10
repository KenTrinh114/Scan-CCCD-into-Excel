"""Failed image handling, preview generation, moving, and restore logic."""

from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable
import csv

import cv2
import numpy as np
from PIL import Image, ImageOps, ImageTk
import tkinter as tk
from tkinter import ttk


@dataclass
class BatchMoveResult:
    """Structured result of a batch move operation, backwards-compatible with 3-tuple unpacking."""

    dest_dir: Path
    moved: dict[str, str] = field(default_factory=dict)
    errors: list[tuple[str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    def __iter__(self):
        return iter((self.dest_dir, self.moved, self.errors))

    def __getitem__(self, index):
        return (self.dest_dir, self.moved, self.errors)[index]


def to_long_path(p: str | Path) -> str:
    """
    Convert path to Windows extended-length format (\\?\\) if path length >= 248.
    Prevents WinError 3 / WinError 206 on deeply nested paths on Windows.
    """
    path_str = os.path.abspath(str(p))
    if os.name == "nt" and len(path_str) >= 248 and not path_str.startswith("\\\\?\\"):
        return "\\\\?\\" + path_str
    return path_str


def read_image_unicode(path: str | Path) -> np.ndarray | None:
    """
    Safely load an image array on Windows with Unicode path support and zero persistent file locks.
    Uses numpy fromfile to read bytes directly into memory.
    """
    try:
        p_str = to_long_path(path)
        data = np.fromfile(p_str, dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def open_path(path: str | Path) -> None:
    """Open a file or folder with the OS default application."""
    p_str = str(path)
    if sys.platform.startswith("win"):
        os.startfile(p_str)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p_str])
    else:
        subprocess.Popen(["xdg-open", p_str])


def replace_or_move(src: str | Path, dst: str | Path) -> None:
    """Safely move a file, attempting atomic fast O(1) replace first and falling back to shutil.move."""
    src_str = to_long_path(src)
    dst_str = to_long_path(dst)
    try:
        os.replace(src_str, dst_str)
    except OSError:
        shutil.move(src_str, dst_str)


def load_heif_image(path: str | Path) -> Image.Image | None:
    """Safely decode an Apple HEIC/HEIF image into a PIL Image."""
    try:
        import pillow_heif

        with open(to_long_path(path), "rb") as f:
            raw_data = f.read()
        heif_file = pillow_heif.open_heif(raw_data)
        return Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw",
        )
    except Exception:
        return None


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str | None, max_len: int = 60) -> str:
    """Sanitize text for safe filesystem usage across Windows/Linux/macOS."""
    if not text:
        return ""
    text = _BAD_CHARS.sub("", text).strip().rstrip(".")
    return text[:max_len]


def get_unique_dest_path(
    dest_dir: Path,
    src_path: Path,
    root_scan_dir: Path | str | None = None,
    preferred_stem: str | None = None,
) -> Path:
    """
    Generate a collision-free destination path in dest_dir for src_path.
    Prefixes with relative parent folder parts if src_path is inside a subfolder of root_scan_dir.
    Appends numeric suffixes (_1, _2, ...) if a file with the target name already exists.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = preferred_stem if preferred_stem is not None else src_path.stem
    suffix = src_path.suffix

    if root_scan_dir:
        root_dir = Path(root_scan_dir).resolve()
        try:
            src_parent = src_path.parent.resolve()
            if src_parent != root_dir and root_dir in src_parent.parents:
                rel_parent = src_parent.relative_to(root_dir)
                safe_prefix = "_".join(rel_parent.parts)
                if safe_prefix and not stem.startswith(safe_prefix):
                    stem = f"{safe_prefix}_{stem}"
        except (ValueError, OSError):
            pass

    candidate = dest_dir / f"{stem}{suffix}"
    counter = 1
    while candidate.exists():
        try:
            if candidate.resolve() == src_path.resolve():
                return candidate
        except (OSError, ValueError):
            pass
        candidate = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


@lru_cache(maxsize=32)
def make_preview(path: str | Path, max_side: int = 650) -> Image.Image:
    """
    Fast, low-memory preview generator with Pillow JPEG draft decode and LRU cache.
    Supports JPG, PNG, WEBP, BMP, and Apple HEIC/HEIF.
    Safe against Windows file locks (copies/loads pixels into memory immediately).
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".heic", ".heif"}:
        im = load_heif_image(p)
        if im is not None:
            im = ImageOps.exif_transpose(im)
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            res = im.convert("RGB")
            res.load()
            return res

    with Image.open(to_long_path(p)) as im:
        try:
            im.draft("RGB", (max_side, max_side))
        except Exception:
            pass
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        res = im.convert("RGB")
        res.load()
        return res


def move_failed(
    items: list[tuple[str, str]],
    dest_root: str | Path,
    folder_name: str = "Ảnh lỗi",
    progress: Callable[[int, int], None] | None = None,
    root_scan_dir: str | Path | None = None,
) -> BatchMoveResult:
    """
    Move failed image files into a dedicated retake directory (default 'Ảnh lỗi').

    items: [(path, name), ...] in current Failed-list order.
           name may be empty string if not yet provided by user.
    progress(i, total): optional callback (runs in background worker thread).
    root_scan_dir: optional root directory of scan to preserve subfolder context on collision.

    Returns BatchMoveResult (dest_dir, moved_dict, errors_list, skipped_list).
    Supports 3-tuple unpacking: (dest_dir, moved, errors).
    """
    root_p = Path(dest_root)
    if root_p.name == folder_name:
        dest = root_p
    else:
        dest = root_p / folder_name
    dest.mkdir(parents=True, exist_ok=True)

    moved: dict[str, str] = {}
    errors: list[tuple[str, str]] = []
    skipped: list[str] = []
    total = len(items)

    dest_resolved = dest.resolve()

    for i, (src, name) in enumerate(items, 1):
        src_path = Path(src)

        # Skip if source file is already inside destination directory (prevents recursive nest)
        try:
            if src_path.parent.resolve() == dest_resolved:
                skipped.append(src)
                if progress:
                    progress(i, total)
                continue
        except (OSError, ValueError):
            pass

        if not src_path.exists():
            errors.append((src, "Tệp không tồn tại"))
            if progress:
                progress(i, total)
            continue

        label = safe_name(name) or f"unnamed_{src_path.stem}"
        preferred_stem = f"{i:03d}_{label}"
        target = get_unique_dest_path(
            dest,
            src_path,
            root_scan_dir=root_scan_dir,
            preferred_stem=preferred_stem,
        )

        try:
            replace_or_move(src_path, target)
            moved[src] = str(target)
        except Exception as e:
            errors.append((src, str(e)))

        if progress:
            progress(i, total)

    # Manifest so the move can be audited or undone.
    # utf-8-sig ensures Excel opens Vietnamese names cleanly.
    log_file = dest / "_moved_log.csv"
    try:
        with open(log_file, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["original_path", "new_path"])
            w.writerows(moved.items())
    except Exception:
        pass

    make_preview.cache_clear()
    return BatchMoveResult(dest, moved, errors, skipped)


def restore_moved(
    log_csv: str | Path,
    delete_empty_folder: bool = True,
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Undo a move using its manifest CSV. Returns (restored_dict, errors_list)."""
    restored: dict[str, str] = {}
    errors: list[tuple[str, str]] = []
    log_path = Path(log_csv)
    if not log_path.exists():
        return restored, [("", f"Không tìm thấy file nhật ký: {log_path}")]

    dest_folder = log_path.parent

    with open(log_path, newline="", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
        for row in reader:
            orig = row.get("original_path")
            new_p = row.get("new_path")
            if not orig or not new_p:
                continue
            try:
                os.makedirs(os.path.dirname(orig), exist_ok=True)
                if os.path.exists(new_p):
                    replace_or_move(new_p, orig)
                    restored[new_p] = orig
            except Exception as e:
                errors.append((new_p, str(e)))

    if delete_empty_folder and dest_folder.exists():
        try:
            if log_path.exists():
                log_path.unlink()
            dest_folder.rmdir()
        except Exception:
            pass

    make_preview.cache_clear()
    return restored, errors


class HoverPreview:
    """Fast, lightweight hover preview tooltip for treeview rows."""

    DELAY_MS = 150

    def __init__(self, tree: ttk.Treeview, get_path_func: Callable[[str], str | None]) -> None:
        self.tree = tree
        self.get_path_func = get_path_func
        self.tip: tk.Toplevel | None = None
        self.container: tk.Frame | None = None
        self.lbl_title: tk.Label | None = None
        self.lbl_img: tk.Label | None = None
        self.photo: ImageTk.PhotoImage | None = None
        self._job: str | None = None
        self._row: str | None = None

        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", self._hide, add="+")
        tree.bind("<ButtonPress>", self._hide, add="+")
        tree.bind("<MouseWheel>", self._hide, add="+")

    def _on_motion(self, e: tk.Event) -> None:
        row = self.tree.identify_row(e.y)
        if row == self._row:
            return
        if self._job:
            try:
                self.tree.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        self._row = row
        if row:
            self._job = self.tree.after(self.DELAY_MS, self._show, row)
        else:
            self._hide()

    def _show(self, row_id: str, *args: Any) -> None:
        path = self.get_path_func(row_id)
        if not path or not os.path.isfile(path):
            self._hide()
            return

        try:
            preview_img = make_preview(path)
            self.photo = ImageTk.PhotoImage(preview_img)
        except Exception:
            self._hide()
            return

        try:
            filename = Path(path).name
            if self.tip and self.tip.winfo_exists() and self.lbl_title and self.lbl_img:
                self.lbl_title.config(text=f"📷 {filename} (Nhấp đúp dòng để mở ảnh)")
                self.lbl_img.config(image=self.photo)
            else:
                if self.tip:
                    try:
                        self.tip.destroy()
                    except Exception:
                        pass
                self.tip = tk.Toplevel(self.tree)
                self.tip.wm_overrideredirect(True)
                self.tip.attributes("-topmost", True)

                self.container = tk.Frame(self.tip, bd=1, relief="solid", bg="#0F172A")
                self.container.pack()

                self.lbl_title = tk.Label(
                    self.container,
                    text=f"📷 {filename} (Nhấp đúp dòng để mở ảnh)",
                    font=("Segoe UI", 8),
                    bg="#1E293B",
                    fg="#F8FAFC",
                    padx=6,
                    pady=2,
                )
                self.lbl_title.pack(fill=tk.X)

                self.lbl_img = tk.Label(self.container, image=self.photo, bd=0, bg="#000000")
                self.lbl_img.pack()

            self.tip.update_idletasks()
            w, h = self.tip.winfo_width(), self.tip.winfo_height()

            # Fixed center position: center relative to the main window or screen,
            # completely independent of the mouse cursor position.
            top = self.tree.winfo_toplevel()
            top.update_idletasks()
            top_x = top.winfo_rootx()
            top_y = top.winfo_rooty()
            top_w = top.winfo_width()
            top_h = top.winfo_height()

            if top_w > 100 and top_h > 100:
                px = max(10, top_x + (top_w - w) // 2)
                py = max(10, top_y + (top_h - h) // 2)
            else:
                sw, sh = self.tip.winfo_screenwidth(), self.tip.winfo_screenheight()
                px = max(10, (sw - w) // 2)
                py = max(10, (sh - h) // 2)

            self.tip.geometry(f"+{px}+{py}")
        except Exception:
            self._hide()

    def _hide(self, _e: Any = None) -> None:
        if self._job:
            try:
                self.tree.after_cancel(self._job)
            except Exception:
                pass
            self._job = None
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None
        self.container = None
        self.lbl_title = None
        self.lbl_img = None
        self.photo = None
        self._row = None
