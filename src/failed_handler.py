"""Failed image handling, preview generation, moving, and restore logic."""

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

from PIL import Image, ImageOps, ImageTk
import tkinter as tk
from tkinter import ttk


def open_path(path: str | Path) -> None:
    """Open a file or folder with the OS default application."""
    p_str = str(path)
    if sys.platform.startswith("win"):
        os.startfile(p_str)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", p_str])
    else:
        subprocess.Popen(["xdg-open", p_str])


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(text: str, max_len: int = 60) -> str:
    """Sanitize text for safe filesystem usage across Windows/Linux/macOS."""
    if not text:
        return ""
    text = _BAD_CHARS.sub("", text).strip().rstrip(".")
    return text[:max_len]


@lru_cache(maxsize=32)
def make_preview(path: str | Path, max_side: int = 650) -> Image.Image:
    """
    Fast, low-memory preview generator with Pillow JPEG draft decode and LRU cache.
    Supports JPG, PNG, WEBP, BMP, and Apple HEIC/HEIF.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix in {".heic", ".heif"}:
        try:
            import pillow_heif

            heif_file = pillow_heif.open_heif(str(p))
            im = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
            )
            im = ImageOps.exif_transpose(im)
            im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            return im.convert("RGB")
        except Exception:
            pass

    with Image.open(str(p)) as im:
        try:
            im.draft("RGB", (max_side, max_side))
        except Exception:
            pass
        im = ImageOps.exif_transpose(im)
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        return im.convert("RGB")


def move_failed(
    items: list[tuple[str, str]],
    dest_root: str | Path,
    folder_name: str = "Ảnh lỗi",
    progress: Callable[[int, int], None] | None = None,
) -> tuple[Path, dict[str, str], list[tuple[str, str]]]:
    """
    Move failed image files into a dedicated retake directory (default 'Ảnh lỗi').

    items: [(path, name), ...] in current Failed-list order.
           name may be empty string if not yet provided by user.
    progress(i, total): optional callback (runs in background worker thread).
    Returns (dest_dir, moved_dict, errors_list)
        moved_dict:  {old_path: new_path}
        errors_list: [(path, message), ...]
    """
    root_p = Path(dest_root)
    if root_p.name == folder_name:
        dest = root_p
    else:
        dest = root_p / folder_name
    dest.mkdir(parents=True, exist_ok=True)

    moved: dict[str, str] = {}
    errors: list[tuple[str, str]] = []
    total = len(items)

    for i, (src, name) in enumerate(items, 1):
        src_path = Path(src)
        ext = src_path.suffix
        label = safe_name(name) or f"unnamed_{src_path.stem}"
        target = dest / f"{i:03d}_{label}{ext}"
        try:
            shutil.move(src, str(target))
            moved[src] = str(target)
        except OSError as e:
            errors.append((src, str(e)))
        if progress:
            progress(i, total)

    # Manifest so the move can be audited or undone.
    # utf-8-sig ensures Excel opens Vietnamese names cleanly.
    log_file = dest / "_moved_log.csv"
    with open(log_file, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["original_path", "new_path"])
        w.writerows(moved.items())

    make_preview.cache_clear()
    return dest, moved, errors


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
                    shutil.move(new_p, orig)
                    restored[new_p] = orig
            except OSError as e:
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
        self._hide()
        self._row = row
        if row:
            self._job = self.tree.after(
                self.DELAY_MS, self._show, row, e.x_root, e.y_root
            )

    def _show(self, row_id: str, x: int, y: int) -> None:
        path = self.get_path_func(row_id)
        if not path or not os.path.isfile(path):
            return

        try:
            preview_img = make_preview(path)
            self.photo = ImageTk.PhotoImage(preview_img)
        except Exception:
            return

        try:
            if self.tip:
                self.tip.destroy()
            self.tip = tk.Toplevel(self.tree)
            self.tip.wm_overrideredirect(True)
            self.tip.attributes("-topmost", True)

            container = tk.Frame(self.tip, bd=1, relief="solid", bg="#0F172A")
            container.pack()

            filename = Path(path).name
            lbl_title = tk.Label(
                container,
                text=f"📷 {filename} (Nhấp đúp dòng để mở ảnh)",
                font=("Segoe UI", 8),
                bg="#1E293B",
                fg="#F8FAFC",
                padx=6,
                pady=2,
            )
            lbl_title.pack(fill=tk.X)

            lbl_img = tk.Label(container, image=self.photo, bd=0, bg="#000000")
            lbl_img.pack()

            self.tip.update_idletasks()
            w, h = self.tip.winfo_width(), self.tip.winfo_height()
            sw, sh = self.tip.winfo_screenwidth(), self.tip.winfo_screenheight()
            px = min(x + 20, sw - w - 10)
            py = min(y + 10, sh - h - 10)
            self.tip.geometry(f"+{max(px, 10)}+{max(py, 10)}")
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
        self._row = None
