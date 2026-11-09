"""Tkinter-based Desktop GUI for CCCD QR Extractor to Excel with Impeccable UX."""

from datetime import datetime
import gc
import os
from pathlib import Path
import queue
import shutil
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
from typing import Any
from PIL import Image, ImageDraw, ImageTk

from src.config import (
    DEFAULT_COLUMNS,
    load_column_config,
    load_theme_config,
    reset_to_default_columns,
    save_column_config,
    save_theme_config,
)
from src.excel_exporter import append_records_to_excel, export_records_to_excel
from src.parser import build_record
from src.qr_engine import CCCDQRScanner
from src.version import APP_VERSION, BUILD_TIME
from src.failed_handler import (
    HoverPreview,
    make_preview,
    move_failed,
    open_path,
    restore_moved,
    safe_name,
)

# Extended supported image extensions including Apple iPhone/iPad HEIC/HEIF
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic", ".heif"}

# Number of parallel worker threads for image processing
# Each worker gets its own CCCDQRScanner instance (WeChatQRCode is not thread-safe)
WORKER_COUNT = min(4, os.cpu_count() or 2)

# Professional themes with high-contrast status recognition and modern functional colors
THEMES: dict[str, dict[str, Any]] = {
    "light": {
        "name": "☀️ Sáng",
        "root_bg": "#E2E8F0",
        "frame_bg": "#F1F5F9",
        "border_col": "#CBD5E1",
        "border_dark": "#94A3B8",
        "heading_bg": "#CBD5E1",
        "heading_fg": "#0F172A",
        "tree_bg": "#F8FAFC",
        "tree_fg": "#0F172A",
        "tree_even": "#FFFFFF",
        "tree_odd": "#E2E8F0",
        "tree_grid": "#CBD5E1",        # Subtle divider lines between rows and columns
        "tree_select_bg": "#BFDBFE",
        "tree_select_fg": "#1E3A8A",
        # Status recognition colors (Light theme)
        "success_bg": "#ECFDF5",       # Soft emerald tint
        "success_fg": "#16A34A",       # Vibrant emerald green text
        "err_bg": "#FEF2F2",           # Soft rose tint
        "err_fg": "#DC2626",           # Vibrant deep crimson text
        "pending_bg": "#EFF6FF",       # Soft sky tint
        "pending_fg": "#1D4ED8",       # Vibrant blue text
        "border_rail": "#CBD5E1",      # Crisp divider rail between functional clusters
        # Functional button colors
        "primary_btn_bg": "#2563EB",   # Vibrant Blue for Add Files/Folder
        "primary_btn_fg": "#FFFFFF",
        "primary_btn_active": "#1D4ED8",
        "excel_btn_bg": "#059669",     # Excel Emerald Green
        "excel_btn_fg": "#FFFFFF",
        "excel_btn_active": "#047857",
        "append_btn_bg": "#0D9488",    # Teal for Append Excel
        "append_btn_fg": "#FFFFFF",
        "append_btn_active": "#0F766E",
        "danger_btn_bg": "#FEE2E2",    # Rose tint for Clear List
        "danger_btn_fg": "#991B1B",
        "danger_btn_active": "#FECACA",
        "danger_btn_border": "#FCA5A5",
        "btn_bg": "#FFFFFF",
        "btn_fg": "#0F172A",
        "btn_active": "#CBD5E1",
        "accent_bg": "#059669",
        "accent_fg": "#FFFFFF",
        "accent_active": "#047857",
        "text_main": "#0F172A",
        "text_muted": "#475569",
        "badge_bg": "#E2E8F0",
        "badge_fg": "#334155",
        "entry_bg": "#FFFFFF",
        "entry_fg": "#0F172A",
        "entry_caret": "#0F172A",
        # High visibility slider & scrollbar colors (Light theme - distinct dark grey)
        "scrollbar_thumb": "#475569",          # Slate-600 dark grey slider thumb
        "scrollbar_thumb_active": "#1E293B",   # Slate-800 deep dark grey active/drag state
        "scrollbar_trough": "#E2E8F0",         # Clear track
        "scrollbar_border": "#334155",         # Slate-700 crisp border
        "scrollbar_arrow": "#1E293B",
    },
    "dark": {
        "name": "🌙 Tối",
        # Deep Obsidian & Charcoal Navy surfaces (modern, comfortable, no glare)
        "root_bg": "#0B0F17",          # Deep obsidian backdrop
        "frame_bg": "#151B28",         # Elevated card/toolbar surface
        "border_col": "#232D3F",       # Refined 1px panel border
        "border_dark": "#334155",      # Crisp focus/hover border
        "border_rail": "#3E4C5E",      # Distinct vertical divider rail between clusters
        "heading_bg": "#1C2436",       # Distinct table header surface
        "heading_fg": "#F1F5F9",       # Slate-100 crisp bold header text
        "tree_bg": "#0D121D",          # Table canvas background
        "tree_fg": "#F1F5F9",          # Crisp white-slate row text
        "tree_even": "#121824",        # Seamless dark row alternation
        "tree_odd": "#0D121D",         # Seamless dark row alternation
        "tree_grid": "#2A364F",        # Subtle divider lines between rows and columns
        "tree_select_bg": "#1D4ED8",   # Vibrant royal blue selection
        "tree_select_fg": "#FFFFFF",   # High-contrast white text on selection
        # Status recognition colors (High contrast, vibrant, non-muddy)
        "success_bg": "#063D27",       # Luminous dark emerald tint
        "success_fg": "#34D399",       # Vibrant mint emerald text
        "err_bg": "#3B1317",           # Deep dark crimson velvet
        "err_fg": "#F87171",           # Vibrant warm coral red text
        "pending_bg": "#0F2744",       # Deep midnight sapphire
        "pending_fg": "#60A5FA",       # Vivid electric sky blue (7.1:1 contrast ratio)
        # Functional button colors (Crisp contrast and modern saturation)
        "primary_btn_bg": "#2563EB",   # Vibrant Blue for Add Files/Folder
        "primary_btn_fg": "#FFFFFF",
        "primary_btn_active": "#1D4ED8",
        "excel_btn_bg": "#059669",     # Emerald Green for New Excel Export
        "excel_btn_fg": "#FFFFFF",
        "excel_btn_active": "#047857",
        "append_btn_bg": "#0284C7",    # Azure Blue for Append Excel
        "append_btn_fg": "#FFFFFF",
        "append_btn_active": "#0369A1",
        "danger_btn_bg": "#7F1D1D",    # Deep crimson red, clearly red and not muddy black
        "danger_btn_fg": "#FFFFFF",    # High contrast crisp white
        "danger_btn_active": "#991B1B",
        "danger_btn_border": "#B91C1C",# Refined crimson border
        "btn_bg": "#232D3F",           # Elevated modern dark button surface (not pitch black)
        "btn_fg": "#F1F5F9",           # Crisp slate-100 text
        "btn_active": "#334155",
        "accent_bg": "#10B981",
        "accent_fg": "#FFFFFF",
        "accent_active": "#059669",
        "text_main": "#F8FAFC",        # High readability white-slate
        "text_muted": "#94A3B8",       # Slate-400 secondary text
        "badge_bg": "#1C2436",
        "badge_fg": "#CBD5E1",
        "entry_bg": "#1C2436",
        "entry_fg": "#F8FAFC",
        "entry_caret": "#60A5FA",      # Electric sky blue cursor
        # High visibility slider & scrollbar colors (Dark theme - distinct dark slate grey)
        "scrollbar_thumb": "#526075",          # Elevated medium-dark slate grey thumb
        "scrollbar_thumb_active": "#94A3B8",   # Slate-400 light slate active/drag state
        "scrollbar_trough": "#0B0F17",         # Deep obsidian backdrop track
        "scrollbar_border": "#1E293B",         # Crisp dark border
        "scrollbar_arrow": "#94A3B8",
    },
}


class CCCDScannerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"App quét CCCD cho Nger ❤️ - v{APP_VERSION}")
        self.root.geometry("1200x700")
        self.root.minsize(920, 520)

        # Set application icon from bundled assets
        self._setup_window_icon()

        # Load user's chosen UI theme ('grey' is default off-white to eliminate glare)
        self.current_theme = load_theme_config()
        self.root.configure(bg=THEMES[self.current_theme]["root_bg"])

        # Visual styling
        self._setup_styles()

        # Engine & Data states
        self.columns: list[dict[str, Any]] = load_column_config()
        self.records: list[dict[str, Any]] = []
        self.item_to_rec_idx: dict[str, int] = {}
        self.active_inline_entry: tk.Entry | None = None

        # Threading & Background Worker Queue (Two-Stage Priority Queue: Fast Pass -> Deep Rescue)
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.result_queue: queue.Queue = queue.Queue()
        self._task_counter: int = 0
        self._sort_col: str | None = None
        self._sort_reverse: bool = False
        self.is_scanning = False
        self._worker_lock = threading.Lock()
        self._active_workers = 0
        self.total_queued = 0
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0

        # Spinner animation & Pending items tracking
        self.pending_item_ids: dict[str, str] = {}
        self.task_id_to_item_id: dict[int, str] = {}
        self.task_id_to_rec: dict[int, dict[str, Any]] = {}
        self.spinner_running: bool = False
        self.spinner_frame_idx: int = 0
        self.SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]

        # Split mode & failed image handling states
        self.is_split_mode: bool = False
        self.has_moved_failed_images: bool = False
        self.last_failed_move_dest: Path | None = None
        self.last_failed_move_items: dict[str, str] = {}
        self.last_failed_move_names: dict[str, str] = {}
        self.passed_item_to_rec_idx: dict[str, int] = {}
        self.failed_item_to_rec_idx: dict[str, int] = {}
        self.last_input_dir: str | None = None
        self.last_moved_log_path: str | None = None

        # Build UI layout
        self._build_top_toolbar()
        self._build_main_panes()
        self._build_status_bar()

        # Apply active theme colors to all widgets
        self._apply_theme(self.current_theme)

        # Update empty state visibility
        self._check_empty_state()

        # Start periodic queue polling (every 80ms)
        self.root.after(80, self._process_queue)

    def _setup_window_icon(self) -> None:
        """Set application window and taskbar icon from bundled assets."""
        import sys
        icon_ico = Path(__file__).parent.parent / "assets" / "app_icon.ico"
        icon_png = Path(__file__).parent.parent / "assets" / "app_icon.png"
        if not icon_ico.exists():
            base_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
            icon_ico = base_dir / "assets" / "app_icon.ico"
            icon_png = base_dir / "assets" / "app_icon.png"

        try:
            if icon_ico.exists():
                self.root.iconbitmap(default=str(icon_ico))
        except Exception:
            pass

        try:
            if icon_png.exists():
                icon_img = ImageTk.PhotoImage(Image.open(icon_png))
                self.root.iconphoto(True, icon_img)
                self._app_icon_img = icon_img
        except Exception:
            pass

    def _setup_styles(self) -> None:
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # High-performance native clam Treeview layouts (100% aligned column boundaries, zero GDI paint lag)
        self.style.layout(
            "Treeview.Row",
            [
                ("Treeitem.row", {"sticky": "nswe"}),
            ],
        )
        self.style.layout(
            "Treeview.Cell",
            [
                (
                    "Treedata.padding",
                    {"sticky": "nswe", "children": [("Treeitem.text", {"sticky": "nswe"})]},
                ),
            ],
        )
        self.style.layout(
            "Treeview.Item",
            [
                (
                    "Treeitem.padding",
                    {
                        "sticky": "nswe",
                        "children": [
                            ("Treeitem.indicator", {"side": "left", "sticky": ""}),
                            ("Treeitem.image", {"side": "left", "sticky": ""}),
                            ("Treeitem.text", {"sticky": "nswe"}),
                        ],
                    },
                ),
            ],
        )
        self.style.layout(
            "Treeview.Heading",
            [
                ("Treeheading.cell", {"sticky": "nswe"}),
                (
                    "Treeheading.border",
                    {
                        "sticky": "nswe",
                        "children": [
                            (
                                "Treeheading.padding",
                                {
                                    "sticky": "nswe",
                                    "children": [
                                        ("Treeheading.image", {"side": "right", "sticky": ""}),
                                        ("Treeheading.text", {"sticky": "we"}),
                                    ],
                                },
                            ),
                        ],
                    },
                ),
            ],
        )

        self._configure_ttk_styles(THEMES[self.current_theme])

    def _configure_ttk_styles(self, t: dict[str, Any]) -> None:
        # Frame & LabelFrame styling
        self.style.configure("TFrame", background=t["frame_bg"])
        self.style.configure(
            "TLabelframe",
            background=t["frame_bg"],
            relief="solid",
            borderwidth=1,
            bordercolor=t["border_col"],
        )
        self.style.configure(
            "TLabelframe.Label",
            background=t["frame_bg"],
            foreground=t["text_main"],
            font=("Segoe UI", 10, "bold"),
        )

        # ---------------------------------------------------------------------
        # Native, Clean, Flat Button Styles (No box outlines, no focus borders)
        # ---------------------------------------------------------------------
        # Primary Ingestion (Add Files, Add Folder)
        self.style.configure(
            "Primary.TButton",
            background=t["primary_btn_bg"],
            foreground=t["primary_btn_fg"],
            bordercolor=t["primary_btn_bg"],
            lightcolor=t["primary_btn_bg"],
            darkcolor=t["primary_btn_bg"],
            relief="flat",
            borderwidth=0,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 4),
        )
        self.style.map(
            "Primary.TButton",
            background=[("active", t["primary_btn_active"]), ("disabled", t["frame_bg"])],
            foreground=[("disabled", t["text_muted"])],
            bordercolor=[("active", t["primary_btn_active"]), ("disabled", t["frame_bg"])],
        )

        # Excel Export (New .xlsx)
        self.style.configure(
            "Excel.TButton",
            background=t["excel_btn_bg"],
            foreground=t["excel_btn_fg"],
            bordercolor=t["excel_btn_bg"],
            lightcolor=t["excel_btn_bg"],
            darkcolor=t["excel_btn_bg"],
            relief="flat",
            borderwidth=0,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 4),
        )
        self.style.map(
            "Excel.TButton",
            background=[("active", t["excel_btn_active"]), ("disabled", t["frame_bg"])],
            foreground=[("disabled", t["text_muted"])],
            bordercolor=[("active", t["excel_btn_active"]), ("disabled", t["frame_bg"])],
        )

        # Excel Append (Append to existing)
        self.style.configure(
            "Append.TButton",
            background=t["append_btn_bg"],
            foreground=t["append_btn_fg"],
            bordercolor=t["append_btn_bg"],
            lightcolor=t["append_btn_bg"],
            darkcolor=t["append_btn_bg"],
            relief="flat",
            borderwidth=0,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 9, "bold"),
            padding=(10, 4),
        )
        self.style.map(
            "Append.TButton",
            background=[("active", t["append_btn_active"]), ("disabled", t["frame_bg"])],
            foreground=[("disabled", t["text_muted"])],
            bordercolor=[("active", t["append_btn_active"]), ("disabled", t["frame_bg"])],
        )

        # Danger List Action (Clear List)
        self.style.configure(
            "Danger.TButton",
            background=t["danger_btn_bg"],
            foreground=t["danger_btn_fg"],
            bordercolor=t["danger_btn_border"],
            lightcolor=t["danger_btn_border"],
            darkcolor=t["danger_btn_border"],
            relief="flat",
            borderwidth=1,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 9),
            padding=(8, 4),
        )
        self.style.map(
            "Danger.TButton",
            background=[("active", t["danger_btn_active"]), ("disabled", t["frame_bg"])],
            foreground=[("disabled", t["text_muted"])],
            bordercolor=[("disabled", t["border_col"])],
        )

        # Small Danger (Row deletion in status bar)
        self.style.configure(
            "SmallDanger.TButton",
            background=t["danger_btn_bg"],
            foreground=t["danger_btn_fg"],
            bordercolor=t["danger_btn_border"],
            lightcolor=t["danger_btn_border"],
            darkcolor=t["danger_btn_border"],
            relief="flat",
            borderwidth=1,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 8),
            padding=(6, 2),
        )
        self.style.map(
            "SmallDanger.TButton",
            background=[("active", t["danger_btn_active"]), ("disabled", t["frame_bg"])],
            foreground=[("disabled", t["text_muted"])],
            bordercolor=[("disabled", t["border_col"])],
        )

        # Small Standard (Column reordering: Up, Down, Reset, Select All)
        self.style.configure(
            "Small.TButton",
            background=t["btn_bg"],
            foreground=t["btn_fg"],
            bordercolor=t["border_dark"],
            lightcolor=t["border_dark"],
            darkcolor=t["border_dark"],
            relief="flat",
            borderwidth=1,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 8),
            padding=(6, 2),
        )
        self.style.map(
            "Small.TButton",
            background=[("active", t["btn_active"])],
            bordercolor=[("active", t["text_muted"])],
        )

        # Default TButton
        self.style.configure(
            "TButton",
            background=t["btn_bg"],
            foreground=t["btn_fg"],
            bordercolor=t["border_dark"],
            lightcolor=t["border_dark"],
            darkcolor=t["border_dark"],
            relief="flat",
            borderwidth=1,
            focusthickness=0,
            focuscolor="",
            font=("Segoe UI", 9),
            padding=(8, 4),
        )
        self.style.map(
            "TButton",
            background=[("active", t["btn_active"])],
            bordercolor=[("active", t["text_muted"])],
        )

        # Checkbutton
        self.style.configure(
            "TCheckbutton",
            background=t["frame_bg"],
            foreground=t["text_main"],
            font=("Segoe UI", 9),
        )
        self.style.map(
            "TCheckbutton",
            background=[("active", t["frame_bg"])],
            foreground=[("active", t["text_main"])],
        )

        # Combobox - styled for both normal and readonly state to eliminate greyed-out appearance
        self.style.configure(
            "TCombobox",
            fieldbackground=t["btn_bg"],
            background=t["btn_bg"],
            foreground=t["btn_fg"],
            arrowcolor=t["btn_fg"],
            bordercolor=t["border_dark"],
            lightcolor=t["btn_bg"],
            darkcolor=t["btn_bg"],
        )
        self.style.map(
            "TCombobox",
            fieldbackground=[("readonly", t["btn_bg"]), ("disabled", t["frame_bg"])],
            background=[("readonly", t["btn_bg"]), ("active", t["btn_active"])],
            foreground=[("readonly", t["btn_fg"]), ("disabled", t["text_muted"])],
            arrowcolor=[("readonly", t["btn_fg"]), ("active", t["text_main"])],
            selectbackground=[("readonly", t["btn_bg"])],
            selectforeground=[("readonly", t["btn_fg"])],
        )

        # Dropdown popup listbox options for combobox
        self.root.option_add("*TCombobox*Listbox.background", t["btn_bg"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["btn_fg"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["tree_select_bg"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", t["tree_select_fg"])

        # PanedWindow & Sash (Distinct, easy-to-grab panel resizer slider)
        self.style.configure("TPanedwindow", background=t["root_bg"])
        self.style.configure("Panedwindow", background=t["root_bg"])
        self.style.configure(
            "Sash",
            sashthickness=6,
            background=t["border_rail"],
            bordercolor=t["border_dark"],
            relief="flat",
        )

        # Scrollbars (Smooth, high-contrast modern sliders with prominent blue thumb)
        self.style.configure(
            "TScrollbar",
            background=t["scrollbar_thumb"],
            troughcolor=t["scrollbar_trough"],
            bordercolor=t["scrollbar_border"],
            arrowcolor=t["scrollbar_arrow"],
            relief="flat",
            borderwidth=1,
            width=14,
            arrowsize=12,
        )
        self.style.map(
            "TScrollbar",
            background=[("active", t["scrollbar_thumb_active"]), ("disabled", t["frame_bg"])],
            arrowcolor=[("active", t["scrollbar_thumb_active"])],
        )

        # Treeview Headings - clean native border aligning 100% with column boundaries
        self.style.configure(
            "Treeview.Heading",
            background=t["heading_bg"],
            foreground=t["heading_fg"],
            font=("Segoe UI", 9, "bold"),
            padding=(6, 6),
            relief="solid",
            borderwidth=1,
            bordercolor=t["tree_grid"],
            lightcolor=t["tree_grid"],
            darkcolor=t["tree_grid"],
        )
        self.style.map(
            "Treeview.Heading",
            background=[("active", t["border_dark"])],
        )

        # Treeview Field & Cell/Row styles - flat relief with 0 borderwidth so borders don't duplicate
        for target in ("Treeview", "Treeview.Cell", "Treeview.Row", "Treeview.Item"):
            self.style.configure(
                target,
                background=t["tree_bg"],
                foreground=t["tree_fg"],
                fieldbackground=t["tree_bg"],
                relief="flat",
                borderwidth=0,
            )
        self.style.configure(
            "Treeview",
            font=("Segoe UI", 9),
            rowheight=28,  # Generous height prevents clipping of Vietnamese diacritics
        )
        self.style.map(
            "Treeview",
            background=[("selected", t["tree_select_bg"])],
            foreground=[("selected", t["tree_select_fg"])],
        )

        # Progressbar
        self.style.configure(
            "TProgressbar",
            troughcolor=t["frame_bg"],
            background=t["accent_bg"],
            thickness=14,
        )

    def _apply_theme(self, theme_key: str) -> None:
        """Dynamically apply theme palette to all widgets without requiring app restart."""
        if theme_key not in THEMES:
            theme_key = "light"
        self.current_theme = theme_key
        t = THEMES[theme_key]

        # 1. Update Root Window
        self.root.configure(bg=t["root_bg"])

        # 2. Update TTK Styles
        self._configure_ttk_styles(t)

        # 3. Update Standard TK Widgets
        if hasattr(self, "top_toolbar"):
            self.top_toolbar.configure(
                bg=t["frame_bg"],
                highlightbackground=t["border_col"],
                highlightthickness=1,
            )
        if hasattr(self, "theme_container"):
            self.theme_container.configure(bg=t["frame_bg"])
        if hasattr(self, "lbl_theme"):
            self.lbl_theme.configure(bg=t["frame_bg"], fg=t["text_main"])
        if hasattr(self, "lbl_hint"):
            self.lbl_hint.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "lbl_right_hint"):
            self.lbl_right_hint.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "div_toolbar_1"):
            self.div_toolbar_1.configure(bg=t["border_rail"])
        if hasattr(self, "div_toolbar_2"):
            self.div_toolbar_2.configure(bg=t["border_rail"])
        if hasattr(self, "status_frame"):
            self.status_frame.configure(
                bg=t["frame_bg"],
                highlightbackground=t["border_col"],
                highlightthickness=1,
            )
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(bg=t["frame_bg"], fg=t["text_main"])
        if hasattr(self, "lbl_select_hint"):
            self.lbl_select_hint.configure(bg=t["frame_bg"], fg=t["text_muted"])

        # Empty state widgets
        if hasattr(self, "empty_frame"):
            self.empty_frame.configure(bg=t["frame_bg"])
        if hasattr(self, "empty_btn_container"):
            self.empty_btn_container.configure(bg=t["frame_bg"])
        if hasattr(self, "lbl_empty_icon"):
            self.lbl_empty_icon.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "lbl_empty_title"):
            self.lbl_empty_title.configure(bg=t["frame_bg"], fg=t["text_main"])
        if hasattr(self, "lbl_empty_sub"):
            self.lbl_empty_sub.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "lbl_empty_formats"):
            self.lbl_empty_formats.configure(
                bg=t["badge_bg"],
                fg=t["badge_fg"],
                highlightbackground=t["border_col"],
                highlightthickness=1,
            )
        if hasattr(self, "lbl_empty_version"):
            self.lbl_empty_version.configure(bg=t["frame_bg"], fg=t["text_muted"])

        # Table Row Tags: Green text for success, red text for error, alternating row backgrounds
        if hasattr(self, "table"):
            self.table.tag_configure("success_row", foreground=t["success_fg"])
            self.table.tag_configure("error_row", foreground=t["err_fg"])
            self.table.tag_configure("pending_row", foreground=t["pending_fg"])
            self.table.tag_configure("even_row", background=t["tree_even"], foreground=t["tree_fg"])
            self.table.tag_configure("odd_row", background=t["tree_odd"], foreground=t["tree_fg"])

        if hasattr(self, "col_tree"):
            self.col_tree.tag_configure("even_row", background=t["tree_even"], foreground=t["tree_fg"])
            self.col_tree.tag_configure("odd_row", background=t["tree_odd"], foreground=t["tree_fg"])

        # Split view widgets
        if hasattr(self, "right_header_bar"):
            self.right_header_bar.configure(bg=t["frame_bg"])
        if hasattr(self, "hdr_passed"):
            self.hdr_passed.configure(bg=t["frame_bg"])
        if hasattr(self, "lbl_passed_title"):
            self.lbl_passed_title.configure(bg=t["frame_bg"], fg=t["success_fg"])
        if hasattr(self, "lbl_passed_hint"):
            self.lbl_passed_hint.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "hdr_failed"):
            self.hdr_failed.configure(bg=t["frame_bg"])
        if hasattr(self, "lbl_failed_title"):
            self.lbl_failed_title.configure(bg=t["frame_bg"], fg=t["err_fg"])
        if hasattr(self, "lbl_failed_hint"):
            self.lbl_failed_hint.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "failed_toolbar"):
            self.failed_toolbar.configure(bg=t["frame_bg"])
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.configure(bg=t["frame_bg"], fg=t["text_muted"])
        if hasattr(self, "lbl_failed_empty"):
            self.lbl_failed_empty.configure(
                bg=t["badge_bg"],
                fg=t["text_main"],
                highlightbackground=t["border_col"],
                highlightthickness=1,
            )

        if hasattr(self, "tree_passed"):
            self.tree_passed.tag_configure("success_row", foreground=t["success_fg"])
            self.tree_passed.tag_configure("even_row", background=t["tree_even"], foreground=t["tree_fg"])
            self.tree_passed.tag_configure("odd_row", background=t["tree_odd"], foreground=t["tree_fg"])

        if hasattr(self, "tree_failed"):
            self.tree_failed.tag_configure("error_row", foreground=t["err_fg"])
            self.tree_failed.tag_configure("even_row", background=t["tree_even"], foreground=t["tree_fg"])
            self.tree_failed.tag_configure("odd_row", background=t["tree_odd"], foreground=t["tree_fg"])

    # =========================================================================
    # UI Layout Construction
    # =========================================================================
    def _build_top_toolbar(self) -> None:
        t = THEMES[self.current_theme]
        self.top_toolbar = tk.Frame(self.root, padx=10, pady=6, relief="solid", bd=1)
        self.top_toolbar.pack(side=tk.TOP, fill=tk.X, padx=8, pady=(8, 4))

        # Cluster 1: Ingestion Actions (Add Files / Add Folder)
        btn_files = ttk.Button(
            self.top_toolbar,
            text="➕ Thêm ảnh...",
            style="Primary.TButton",
            command=self._on_add_files,
        )
        btn_files.pack(side=tk.LEFT, padx=(0, 4))

        btn_dir = ttk.Button(
            self.top_toolbar,
            text="📂 Thêm thư mục ảnh...",
            style="Primary.TButton",
            command=self._on_add_directory,
        )
        btn_dir.pack(side=tk.LEFT, padx=(0, 8))

        # Divider Rail 1: Between Ingestion and Export
        self.div_toolbar_1 = tk.Frame(self.top_toolbar, width=2, bg=t["border_rail"])
        self.div_toolbar_1.pack(side=tk.LEFT, padx=(0, 8), fill=tk.Y, pady=2)

        # Cluster 2: Export Actions (Export New / Append to existing)
        btn_export = ttk.Button(
            self.top_toolbar,
            text="📊 Xuất File Excel Mới (.xlsx)",
            style="Excel.TButton",
            command=self._on_export_excel,
        )
        btn_export.pack(side=tk.LEFT, padx=(0, 4))

        btn_append = ttk.Button(
            self.top_toolbar,
            text="📑 Ghi tiếp vào Excel...",
            style="Append.TButton",
            command=self._on_append_excel,
        )
        btn_append.pack(side=tk.LEFT, padx=(0, 8))

        # Divider Rail 2: Between Export and List Maintenance
        self.div_toolbar_2 = tk.Frame(self.top_toolbar, width=2, bg=t["border_rail"])
        self.div_toolbar_2.pack(side=tk.LEFT, padx=(0, 8), fill=tk.Y, pady=2)

        # Cluster 3: List Operations & Filters
        btn_clear = ttk.Button(
            self.top_toolbar,
            text="🗑 Xóa danh sách",
            style="Danger.TButton",
            command=self._on_clear_list,
        )
        btn_clear.pack(side=tk.LEFT, padx=(0, 8))

        # Retained for internal backwards-compatibility with existing tests, but omitted from UI
        self.filter_error_var = tk.BooleanVar(value=False)
        self.chk_filter = ttk.Checkbutton(
            self.top_toolbar,
            text="Chỉ xem ảnh cần chụp lại (0)",
            variable=self.filter_error_var,
            command=self._refresh_preview_table_data,
        )

        self.btn_split_toggle = ttk.Button(
            self.top_toolbar,
            text="⚡ Tách danh sách lỗi",
            style="Small.TButton",
            command=self._on_toggle_split_view,
        )
        self.btn_split_toggle.pack(side=tk.LEFT, padx=(0, 8))

        # Cluster 4 (Far Right): Theme Selection
        self.theme_container = tk.Frame(self.top_toolbar)
        self.theme_container.pack(side=tk.RIGHT)

        self.lbl_theme = tk.Label(
            self.theme_container,
            text="Giao diện:",
            font=("Segoe UI", 9),
        )
        self.lbl_theme.pack(side=tk.LEFT, padx=(0, 4))

        theme_display_names = {
            "light": "☀️ Sáng",
            "dark": "🌙 Tối",
        }
        self.theme_var = tk.StringVar(value=theme_display_names.get(self.current_theme, "☀️ Sáng"))
        self.theme_combo = ttk.Combobox(
            self.theme_container,
            textvariable=self.theme_var,
            values=["☀️ Sáng", "🌙 Tối"],
            state="readonly",
            width=10,
            font=("Segoe UI", 9),
        )
        self.theme_combo.pack(side=tk.LEFT)
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme_selected)

    def _on_theme_selected(self, event: Any = None) -> None:
        chosen_display = self.theme_var.get()
        theme_keys = {"☀️ Sáng": "light", "🌙 Tối": "dark"}
        chosen_key = theme_keys.get(chosen_display, "light")
        self._apply_theme(chosen_key)
        save_theme_config(chosen_key)

    def _build_main_panes(self) -> None:
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=8, pady=(4, 6))

        # ---------------------------------------------------------------------
        # Left Panel: Column Management
        # ---------------------------------------------------------------------
        left_frame = ttk.LabelFrame(paned, text="Cột dữ liệu xuất Excel", padding=8)
        paned.add(left_frame, weight=1)

        # Helper description (concise UX copy)
        self.lbl_hint = tk.Label(
            left_frame,
            text="Tích chọn cột cần lấy. Dùng nút Lên/Xuống để đổi thứ tự xuất.",
            font=("Segoe UI", 8),
            wraplength=230,
            justify=tk.LEFT,
        )
        self.lbl_hint.pack(anchor="w", pady=(0, 6))

        # Order Toolbar
        left_toolbar = ttk.Frame(left_frame)
        left_toolbar.pack(fill=tk.X, pady=(0, 6))

        btn_up = ttk.Button(
            left_toolbar, text="▲ Lên", style="Small.TButton", command=self._on_move_col_up
        )
        btn_up.pack(side=tk.LEFT, padx=(0, 4))

        btn_down = ttk.Button(
            left_toolbar, text="▼ Xuống", style="Small.TButton", command=self._on_move_col_down
        )
        btn_down.pack(side=tk.LEFT, padx=(0, 4))

        btn_reset = ttk.Button(
            left_toolbar, text="Mặc định", style="Small.TButton", command=self._on_reset_columns
        )
        btn_reset.pack(side=tk.RIGHT)

        # Left Column Treeview
        col_tree_frame = ttk.Frame(left_frame)
        col_tree_frame.pack(fill=tk.BOTH, expand=True)

        self.col_tree = ttk.Treeview(
            col_tree_frame,
            columns=("checked", "order", "label"),
            show="headings",
            selectmode="browse",
            height=13,
        )
        self.col_tree.heading("checked", text="◼ Chọn")
        self.col_tree.column("checked", width=54, anchor="center")
        self.col_tree.heading("order", text="#")
        self.col_tree.column("order", width=36, anchor="center")
        self.col_tree.heading("label", text="Tên cột")
        self.col_tree.column("label", width=170, anchor="w")

        col_tree_scroll = ttk.Scrollbar(col_tree_frame, orient=tk.VERTICAL, command=self.col_tree.yview)
        self.col_tree.configure(yscrollcommand=col_tree_scroll.set)
        self.col_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        col_tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Only clicking directly on the 'Chọn' checkbox column toggles export selection
        self.col_tree.bind("<Button-1>", self._on_col_tree_click)
        self.col_tree.bind("<Motion>", self._on_col_tree_motion)
        self.col_tree.bind("<space>", self._on_col_tree_space)

        # Select all / Deselect all
        left_bottom = ttk.Frame(left_frame)
        left_bottom.pack(fill=tk.X, pady=(6, 0))
        btn_select_all = ttk.Button(
            left_bottom, text="Chọn tất cả", style="Small.TButton", command=self._on_select_all_cols
        )
        btn_select_all.pack(side=tk.LEFT, padx=(0, 4))
        btn_deselect_all = ttk.Button(
            left_bottom, text="Bỏ chọn", style="Small.TButton", command=self._on_deselect_all_cols
        )
        btn_deselect_all.pack(side=tk.LEFT)

        # ---------------------------------------------------------------------
        # Right Panel: Results Preview Table
        # ---------------------------------------------------------------------
        self.right_frame = ttk.LabelFrame(
            paned,
            text="Danh sách kết quả quét",
            padding=8,
        )
        paned.add(self.right_frame, weight=4)

        # Subtitle header bar with hint & split toggle button
        self.right_header_bar = tk.Frame(self.right_frame)
        self.right_header_bar.pack(fill=tk.X, pady=(0, 4))

        self.lbl_right_hint = tk.Label(
            self.right_header_bar,
            text="Nhấp đúp chuột vào ô bất kỳ để chỉnh sửa trực tiếp thông tin trước khi xuất Excel.",
            font=("Segoe UI", 8),
        )
        self.lbl_right_hint.pack(side=tk.LEFT)

        self.btn_split_sub = ttk.Button(
            self.right_header_bar,
            text="⚡ Tách danh sách lỗi",
            style="Small.TButton",
            command=self._on_toggle_split_view,
        )
        self.btn_split_sub.pack(side=tk.RIGHT)

        # Main Table Container
        self.table_container = ttk.Frame(self.right_frame)
        self.table_container.pack(fill=tk.BOTH, expand=True)

        self.table = ttk.Treeview(self.table_container, selectmode="extended", show="headings")
        self.table_scroll_y = ttk.Scrollbar(self.table_container, orient=tk.VERTICAL, command=self.table.yview)
        self.table_scroll_x = ttk.Scrollbar(self.table_container, orient=tk.HORIZONTAL, command=self.table.xview)
        self.table.configure(yscrollcommand=self.table_scroll_y.set, xscrollcommand=self.table_scroll_x.set)

        self.table.grid(row=0, column=0, sticky="nsew")
        self.table_scroll_y.grid(row=0, column=1, sticky="ns")
        self.table_scroll_x.grid(row=1, column=0, sticky="ew")
        self.table_container.grid_rowconfigure(0, weight=1)
        self.table_container.grid_columnconfigure(0, weight=1)

        # Inline Editing on Double-Click
        self.table.bind("<Double-Button-1>", self._on_table_double_click)

        # Keyboard Shortcuts for Row Deletion & Selection
        self.table.bind("<Delete>", lambda e: self._on_delete_selected_rows())
        self.table.bind("<BackSpace>", lambda e: self._on_delete_selected_rows())
        self.table.bind("<Control-a>", self._on_select_all_rows)
        self.table.bind("<Control-A>", self._on_select_all_rows)

        # Horizontal scrolling with Shift + MouseWheel (standard on Windows)
        self.table.bind("<Shift-MouseWheel>", self._on_table_shift_mousewheel)

        # Update button states on selection changes
        self.table.bind("<<TreeviewSelect>>", self._on_table_select_changed)

        # ---------------------------------------------------------------------
        # Split View Container (Passed / Failed split lists)
        # ---------------------------------------------------------------------
        self.split_container = ttk.Frame(self.right_frame)

        self.split_paned = ttk.PanedWindow(self.split_container, orient=tk.VERTICAL)
        self.split_paned.pack(fill=tk.BOTH, expand=True)

        # Top Section: Passed List
        self.frame_passed = ttk.Frame(self.split_paned)
        self.split_paned.add(self.frame_passed, weight=1)

        self.hdr_passed = tk.Frame(self.frame_passed)
        self.hdr_passed.pack(fill=tk.X, pady=(0, 3))

        self.lbl_passed_title = tk.Label(
            self.hdr_passed,
            text="✅ Danh sách Đạt (0)",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_passed_title.pack(side=tk.LEFT)

        self.lbl_passed_hint = tk.Label(
            self.hdr_passed,
            text="— Thẻ CCCD quét thành công, sẵn sàng xuất Excel",
            font=("Segoe UI", 8),
        )
        self.lbl_passed_hint.pack(side=tk.LEFT, padx=(4, 0))

        tree_passed_container = ttk.Frame(self.frame_passed)
        tree_passed_container.pack(fill=tk.BOTH, expand=True)

        self.tree_passed = ttk.Treeview(
            tree_passed_container,
            columns=("n", "file", "name", "cccd", "dob", "status"),
            show="headings",
            selectmode="extended",
        )
        self.tree_passed.heading("n", text="#")
        self.tree_passed.column("n", width=40, anchor="center")
        self.tree_passed.heading("file", text="Tên file ảnh")
        self.tree_passed.column("file", width=160, anchor="w")
        self.tree_passed.heading("name", text="Họ và tên")
        self.tree_passed.column("name", width=180, anchor="w")
        self.tree_passed.heading("cccd", text="Số định danh / CCCD")
        self.tree_passed.column("cccd", width=130, anchor="center")
        self.tree_passed.heading("dob", text="Ngày sinh")
        self.tree_passed.column("dob", width=90, anchor="center")
        self.tree_passed.heading("status", text="Trạng thái")
        self.tree_passed.column("status", width=120, anchor="w")

        self.tree_passed_scroll_y = ttk.Scrollbar(tree_passed_container, orient=tk.VERTICAL, command=self.tree_passed.yview)
        self.tree_passed_scroll_x = ttk.Scrollbar(tree_passed_container, orient=tk.HORIZONTAL, command=self.tree_passed.xview)
        self.tree_passed.configure(yscrollcommand=self.tree_passed_scroll_y.set, xscrollcommand=self.tree_passed_scroll_x.set)

        self.tree_passed.grid(row=0, column=0, sticky="nsew")
        self.tree_passed_scroll_y.grid(row=0, column=1, sticky="ns")
        self.tree_passed_scroll_x.grid(row=1, column=0, sticky="ew")
        tree_passed_container.grid_rowconfigure(0, weight=1)
        tree_passed_container.grid_columnconfigure(0, weight=1)

        self.tree_passed.bind("<Double-Button-1>", self._on_split_passed_double_click)
        self.tree_passed.bind("<Delete>", self._on_split_passed_delete)
        self.tree_passed.bind("<BackSpace>", self._on_split_passed_delete)

        # Bottom Section: Failed List
        self.frame_failed = ttk.Frame(self.split_paned)
        self.split_paned.add(self.frame_failed, weight=1)

        self.hdr_failed = tk.Frame(self.frame_failed)
        self.hdr_failed.pack(fill=tk.X, pady=(5, 3))

        self.lbl_failed_title = tk.Label(
            self.hdr_failed,
            text="❌ Danh sách Cần chụp lại (0)",
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_failed_title.pack(side=tk.LEFT)

        self.lbl_failed_hint = tk.Label(
            self.hdr_failed,
            text="— 💡 Rê chuột để xem ảnh • Nhấp đúp ô Tên để sửa • Nhấp đúp dòng để mở ảnh",
            font=("Segoe UI", 8),
        )
        self.lbl_failed_hint.pack(side=tk.LEFT, padx=(4, 0))

        tree_failed_container = ttk.Frame(self.frame_failed)
        tree_failed_container.pack(fill=tk.BOTH, expand=True)

        self.tree_failed = ttk.Treeview(
            tree_failed_container,
            columns=("n", "file", "name", "status"),
            show="headings",
            selectmode="extended",
        )
        self.tree_failed.heading("n", text="#")
        self.tree_failed.column("n", width=45, anchor="center")
        self.tree_failed.heading("file", text="Tên file ảnh")
        self.tree_failed.column("file", width=180, anchor="w")
        self.tree_failed.heading("name", text="Họ và tên (chủ thẻ)")
        self.tree_failed.column("name", width=220, anchor="w")
        self.tree_failed.heading("status", text="Trạng thái lỗi (cần chụp lại)")
        self.tree_failed.column("status", width=360, anchor="w")

        self.tree_failed_scroll_y = ttk.Scrollbar(tree_failed_container, orient=tk.VERTICAL, command=self.tree_failed.yview)
        self.tree_failed_scroll_x = ttk.Scrollbar(tree_failed_container, orient=tk.HORIZONTAL, command=self.tree_failed.xview)
        self.tree_failed.configure(yscrollcommand=self.tree_failed_scroll_y.set, xscrollcommand=self.tree_failed_scroll_x.set)

        self.tree_failed.grid(row=0, column=0, sticky="nsew")
        self.tree_failed_scroll_y.grid(row=0, column=1, sticky="ns")
        self.tree_failed_scroll_x.grid(row=1, column=0, sticky="ew")
        tree_failed_container.grid_rowconfigure(0, weight=1)
        tree_failed_container.grid_columnconfigure(0, weight=1)

        # Empty state overlay when failed images are moved
        self.lbl_failed_empty = tk.Label(
            tree_failed_container,
            text="📂 Các ảnh lỗi đã được gom lại, bạn có thể hoàn tác để chúng hiện lại ở đây",
            font=("Segoe UI", 9, "bold"),
            padx=16,
            pady=10,
            relief="solid",
            bd=1,
        )

        # Attach HoverPreview ONLY to the Failed treeview!
        self.failed_hover_preview = HoverPreview(
            self.tree_failed,
            lambda row_id: self.records[self.failed_item_to_rec_idx[row_id]].get("_full_path")
            if row_id in self.failed_item_to_rec_idx and self.failed_item_to_rec_idx[row_id] < len(self.records)
            else None,
        )

        self.tree_failed.bind("<Double-Button-1>", self._on_split_failed_double_click)
        self.tree_failed.bind("<Delete>", self._on_split_failed_delete)
        self.tree_failed.bind("<BackSpace>", self._on_split_failed_delete)

        # Action Toolbar below Failed table
        self.failed_toolbar = tk.Frame(self.frame_failed, pady=4)
        self.failed_toolbar.pack(fill=tk.X, pady=(4, 0))

        # Merged Move/Undo button (2 states)
        self.btn_move_toggle = ttk.Button(
            self.failed_toolbar,
            text="📁 Gom ảnh lỗi vào 1 thư mục",
            style="Primary.TButton",
            command=self._on_handle_failed_images_action,
        )
        self.btn_move_toggle.pack(side=tk.LEFT, padx=(0, 8))

        # Aliases for backwards compatibility with test suites
        self.btn_move_failed = self.btn_move_toggle
        self.btn_restore_failed = self.btn_move_toggle

        self.lbl_move_status = tk.Label(
            self.failed_toolbar,
            text="",
            font=("Segoe UI", 8),
        )
        self.lbl_move_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.btn_merge_back = ttk.Button(
            self.failed_toolbar,
            text="📋 Gộp lại danh sách chính",
            style="Small.TButton",
            command=self._on_toggle_split_view,
        )
        self.btn_merge_back.pack(side=tk.RIGHT)

        # Friendly Empty State Overlay
        self._build_empty_state_overlay()

        # Initial render of column list and preview headers
        self._refresh_col_tree_view()
        self._rebuild_preview_columns()

    def _build_empty_state_overlay(self) -> None:
        """Create a clean, welcoming empty state when no files are loaded."""
        self.empty_frame = tk.Frame(self.table_container)

        self.lbl_empty_icon = tk.Label(
            self.empty_frame,
            text="🪪",
            font=("Segoe UI", 42),
        )
        self.lbl_empty_icon.pack(pady=(35, 6))

        self.lbl_empty_title = tk.Label(
            self.empty_frame,
            text="Sẵn sàng quét thẻ CCCD",
            font=("Segoe UI", 13, "bold"),
        )
        self.lbl_empty_title.pack(pady=(0, 6))

        self.lbl_empty_sub = tk.Label(
            self.empty_frame,
            text="Chọn các file ảnh thẻ Căn cước công dân hoặc chọn cả thư mục ảnh để trích xuất tự động vào Excel.",
            font=("Segoe UI", 9),
        )
        self.lbl_empty_sub.pack(pady=(0, 14))

        # Prominent Call-To-Action buttons directly in empty state for new users
        self.empty_btn_container = tk.Frame(self.empty_frame)
        self.empty_btn_container.pack(pady=(0, 14))

        self.btn_empty_add_files = ttk.Button(
            self.empty_btn_container,
            text="➕ Thêm ảnh...",
            style="Primary.TButton",
            command=self._on_add_files,
        )
        self.btn_empty_add_files.pack(side=tk.LEFT, padx=4)

        self.btn_empty_add_dir = ttk.Button(
            self.empty_btn_container,
            text="📂 Thêm thư mục ảnh...",
            style="Primary.TButton",
            command=self._on_add_directory,
        )
        self.btn_empty_add_dir.pack(side=tk.LEFT, padx=4)

        self.lbl_empty_formats = tk.Label(
            self.empty_frame,
            text="📷 Định dạng hỗ trợ: JPG • PNG • WEBP • BMP • HEIC / HEIF (iPhone)",
            font=("Segoe UI", 8),
            padx=14,
            pady=5,
            relief="solid",
            bd=1,
        )
        self.lbl_empty_formats.pack()

        self.lbl_empty_version = tk.Label(
            self.empty_frame,
            text=f"Phiên bản: v{APP_VERSION} (Cập nhật: {BUILD_TIME})",
            font=("Segoe UI", 8),
        )
        self.lbl_empty_version.pack(pady=(8, 0))

    def _check_empty_state(self) -> None:
        """Show or hide the empty state overlay depending on records count."""
        if self.is_split_mode:
            self.empty_frame.place_forget()
            return
        if not self.records:
            self.empty_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        else:
            self.empty_frame.place_forget()

    def _build_status_bar(self) -> None:
        t = THEMES[self.current_theme]
        self.status_frame = tk.Frame(self.root, padx=10, pady=5, relief="solid", bd=1)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=8, pady=(0, 8))

        # Quick Delete All Failed/Error Rows button
        self.btn_delete_failed = ttk.Button(
            self.status_frame,
            text="🧹 Xóa dòng lỗi",
            style="SmallDanger.TButton",
            command=self._on_delete_all_failed_rows,
        )
        self.btn_delete_failed.pack(side=tk.RIGHT, padx=(4, 0))

        # Merged Delete Selected Rows button (with selection count indicator)
        self.btn_delete_selected = ttk.Button(
            self.status_frame,
            text="🗑 Xóa dòng (0)",
            style="SmallDanger.TButton",
            command=self._on_delete_selected_rows,
        )
        self.btn_delete_selected.pack(side=tk.RIGHT, padx=(6, 0))
        # Backwards-compatible aliases for test suites and scripts
        self.btn_delete_single = self.btn_delete_selected
        self.btn_delete_multi = self.btn_delete_selected

        # Instruction hint on the same line explaining Ctrl / Shift multi-select
        self.lbl_select_hint = tk.Label(
            self.status_frame,
            text="💡 Giữ Ctrl hoặc Shift để chọn nhiều dòng",
            font=("Segoe UI", 8),
            bg=t["frame_bg"],
            fg=t["text_muted"],
        )
        self.lbl_select_hint.pack(side=tk.RIGHT, padx=(8, 4))

        # Status text label on the left
        self.lbl_status = tk.Label(
            self.status_frame,
            text="Sẵn sàng. Hãy chọn ảnh hoặc thư mục để bắt đầu quét.",
            font=("Segoe UI", 9),
            bg=t["frame_bg"],
            fg=t["text_main"],
        )
        self.lbl_status.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # =========================================================================
    # Column Management & Persistence
    # =========================================================================
    def _refresh_col_tree_view(self) -> None:
        selected_key = None
        current_sel = self.col_tree.selection()
        if current_sel:
            selected_key = current_sel[0]

        for item in self.col_tree.get_children():
            self.col_tree.delete(item)

        for idx, col in enumerate(self.columns, start=1):
            check_mark = "◼" if col.get("enabled", True) else "◻"
            item_id = col["key"]
            tag = "even_row" if idx % 2 == 1 else "odd_row"
            self.col_tree.insert(
                "",
                tk.END,
                iid=item_id,
                values=(check_mark, idx, col["label"]),
                tags=(tag,),
            )

        if selected_key and self.col_tree.exists(selected_key):
            self.col_tree.selection_set(selected_key)
            self.col_tree.see(selected_key)

    def _on_col_tree_click(self, event: tk.Event) -> None:
        item_id = self.col_tree.identify_row(event.y)
        col_id = self.col_tree.identify_column(event.x)
        # ONLY clicking directly on column #1 ("checked" / "Chọn") toggles selection
        if item_id and col_id == "#1":
            self._toggle_col_enabled(item_id)

    def _on_col_tree_motion(self, event: tk.Event) -> None:
        col_id = self.col_tree.identify_column(event.x)
        row_id = self.col_tree.identify_row(event.y)
        if row_id and col_id == "#1":
            self.col_tree.configure(cursor="hand2")
        else:
            self.col_tree.configure(cursor="")

    def _on_col_tree_space(self, event: tk.Event) -> None:
        sel = self.col_tree.selection()
        if sel:
            self._toggle_col_enabled(sel[0])

    def _toggle_col_enabled(self, key: str) -> None:
        for col in self.columns:
            if col["key"] == key:
                col["enabled"] = not col.get("enabled", True)
                break
        save_column_config(self.columns)
        self._refresh_col_tree_view()
        self._rebuild_preview_columns()
        self._refresh_preview_table_data()

    def _on_move_col_up(self) -> None:
        sel = self.col_tree.selection()
        if not sel:
            return
        key = sel[0]
        idx = next((i for i, c in enumerate(self.columns) if c["key"] == key), -1)
        if idx > 0:
            self.columns[idx - 1], self.columns[idx] = self.columns[idx], self.columns[idx - 1]
            save_column_config(self.columns)
            self._refresh_col_tree_view()
            self._rebuild_preview_columns()
            self._refresh_preview_table_data()
            self.col_tree.selection_set(key)

    def _on_move_col_down(self) -> None:
        sel = self.col_tree.selection()
        if not sel:
            return
        key = sel[0]
        idx = next((i for i, c in enumerate(self.columns) if c["key"] == key), -1)
        if 0 <= idx < len(self.columns) - 1:
            self.columns[idx], self.columns[idx + 1] = self.columns[idx + 1], self.columns[idx]
            save_column_config(self.columns)
            self._refresh_col_tree_view()
            self._rebuild_preview_columns()
            self._refresh_preview_table_data()
            self.col_tree.selection_set(key)

    def _on_select_all_cols(self) -> None:
        for col in self.columns:
            col["enabled"] = True
        save_column_config(self.columns)
        self._refresh_col_tree_view()
        self._rebuild_preview_columns()
        self._refresh_preview_table_data()

    def _on_deselect_all_cols(self) -> None:
        for col in self.columns:
            col["enabled"] = False
        save_column_config(self.columns)
        self._refresh_col_tree_view()
        self._rebuild_preview_columns()
        self._refresh_preview_table_data()

    def _on_reset_columns(self) -> None:
        self.columns = reset_to_default_columns()
        save_column_config(self.columns)
        self._refresh_col_tree_view()
        self._rebuild_preview_columns()
        self._refresh_preview_table_data()

    def _get_active_columns(self) -> list[dict[str, Any]]:
        return [c for c in self.columns if c.get("enabled", True)]

    # =========================================================================
    # Error Message Formatting & Column Auto-Resizing
    # =========================================================================
    def _get_display_value(
        self,
        rec: dict[str, Any],
        col_key: str,
        active_cols: list[dict[str, Any]],
        spinner_frame: str | None = None,
    ) -> str:
        """
        Return the formatted cell string for a given record and column.
        - Pending rows: display loading circle animation in the status column; other columns empty.
        - Success rows: display '🟢 Thành công' in green badge.
        - Error rows: display '🔴 [filename] Cần chụp lại: ...' in red badge.
        """
        if spinner_frame is None:
            spinner_frame = self.SPINNER_FRAMES[self.spinner_frame_idx]

        is_pending = rec.get("_is_pending", False)
        is_err = rec.get("_is_error", False)
        has_source_col = any(c["key"] == "source_file" for c in active_cols)
        filename = rec.get("source_file", "")

        if is_pending:
            if col_key == "status":
                if not has_source_col and filename:
                    return f"[{filename}] {spinner_frame} Đang xử lý..."
                return f"{spinner_frame} Đang xử lý..."
            elif col_key == "source_file":
                return str(filename)
            else:
                # Put a loading circle instead of all the columns
                return ""

        raw_val = rec.get(col_key, "")
        val_str = str(raw_val) if raw_val is not None else ""

        if col_key == "status":
            if is_err:
                # Failed upload: heavy high-contrast X icon (colored red via error_row tag)
                if not has_source_col and filename:
                    return f"✖ [{filename}] {val_str}"
                return f"✖ {val_str}"
            else:
                # Success upload: heavy high-contrast Tick icon (colored green via success_row tag)
                return f"✔ {val_str}"

        return val_str

    def _adjust_all_column_widths(self, record_candidates: list[dict[str, Any]] | None = None) -> None:
        """
        Dynamically auto-fit table column widths based on cell contents and headers.
        Applies to ALL column types (source_file, status, full_name, permanent_address, etc.)
        to ensure no text is truncated or clipped.
        Optimized with fast length heuristics to avoid font.measure overhead during bulk imports.
        """
        active = self._get_active_columns()
        if not active:
            return

        font = tkfont.Font(font=("Segoe UI", 9))
        records_to_check = record_candidates if record_candidates is not None else self.records
        # Sampling up to 100 records is statistically representative and keeps execution under 10ms
        sample_recs = records_to_check[:100] if len(records_to_check) > 100 else records_to_check

        for col in active:
            key = col["key"]
            header_text = col.get("label", "")
            base_w = col.get("width", 120)
            header_w = font.measure(header_text) + 30

            try:
                curr_w = int(self.table.column(key, "width"))
            except Exception:
                curr_w = base_w

            needed_w = max(curr_w, base_w, header_w)
            if needed_w >= 850:
                continue

            pad = 42 if key == "status" else 26

            # Measure width across checked records with fast length pre-filter
            for rec in sample_recs:
                if key == "status":
                    val = self._get_display_value(rec, key, active)
                else:
                    raw_val = rec.get(key, "")
                    val = str(raw_val) if raw_val is not None else ""

                if val:
                    # At 9pt Segoe UI, max char width is ~11px. If len(val)*11 + pad <= needed_w,
                    # it mathematically cannot expand the column, so bypass font.measure.
                    if len(val) * 11 + pad <= needed_w:
                        continue
                    cell_w = font.measure(val) + pad
                    if cell_w > needed_w:
                        needed_w = min(cell_w, 850)
                        if needed_w >= 850:
                            break

            if needed_w > curr_w:
                try:
                    self.table.column(key, width=needed_w, minwidth=max(60, base_w), stretch=False)
                except Exception:
                    pass

    def _adjust_status_column_width(self) -> None:
        """Backward-compatible helper that delegates to full-table dynamic column auto-fitting."""
        self._adjust_all_column_widths()

    # =========================================================================
    # Preview Table Operations
    # =========================================================================
    def _rebuild_preview_columns(self) -> None:
        active = self._get_active_columns()
        col_keys = [c["key"] for c in active]
        self.table["columns"] = col_keys

        for col in active:
            key = col["key"]
            self.table.heading(
                key,
                text=col["label"],
                command=lambda k=key: self._on_sort_column(k),
            )
            width = col.get("width", 120)
            anchor = (
                "center"
                if key in ("dob", "issue_date", "expiry_date", "sex", "age", "cccd_number", "old_cmnd")
                else "w"
            )
            self.table.column(key, width=width, minwidth=60, anchor=anchor, stretch=False)

        self._adjust_all_column_widths()

    def _on_sort_column(self, col_key: str) -> None:
        """
        Sort table rows when clicking a column header.
        Sorting by 'status' groups all passed (successful) rows at the top first,
        or reverses on alternate clicks.
        """
        if self._sort_col == col_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col_key
            self._sort_reverse = False

        def get_sort_key(rec: dict[str, Any]):
            if col_key == "status":
                # Success = 0, Pending = 1, Error = 2
                if rec.get("_is_pending", False):
                    prio = 1
                elif rec.get("_is_error", False):
                    prio = 2
                else:
                    prio = 0
                return (prio, str(rec.get("source_file", "")))
            val = rec.get(col_key, "")
            return str(val) if val is not None else ""

        self.records.sort(key=get_sort_key, reverse=self._sort_reverse)
        self._refresh_preview_table_data()

    def _refresh_preview_table_data(self) -> None:
        self._destroy_inline_entry()
        for item in self.table.get_children():
            self.table.delete(item)
        self.item_to_rec_idx.clear()
        self.pending_item_ids.clear()
        self.task_id_to_item_id.clear()
        self.task_id_to_rec.clear()

        active = self._get_active_columns()
        filter_error_only = self.filter_error_var.get()

        displayed_count = 0
        frame = self.SPINNER_FRAMES[self.spinner_frame_idx]
        for rec_idx, rec in enumerate(self.records):
            rec["_rec_idx"] = rec_idx
            is_err = rec.get("_is_error", False)
            is_pending = rec.get("_is_pending", False)
            if filter_error_only and not is_err:
                continue

            values = [self._get_display_value(rec, c["key"], active, spinner_frame=frame) for c in active]
            if is_pending:
                row_tag = "pending_row"
            elif is_err:
                row_tag = "error_row"
            else:
                row_tag = "success_row"
            parity_tag = "even_row" if displayed_count % 2 == 0 else "odd_row"
            item_id = self.table.insert("", tk.END, values=values, tags=(row_tag, parity_tag))
            self.item_to_rec_idx[item_id] = rec_idx
            task_id = rec.get("_task_id")
            if task_id is not None:
                self.task_id_to_item_id[task_id] = item_id
                if is_pending:
                    self.task_id_to_rec[task_id] = rec
            if is_pending:
                self.pending_item_ids[rec.get("_full_path", "")] = item_id
            displayed_count += 1

        self._adjust_all_column_widths()
        self._check_empty_state()

    # =========================================================================
    # Inline Cell Editing
    # =========================================================================
    def _destroy_inline_entry(self) -> None:
        if self.active_inline_entry is not None:
            entry = self.active_inline_entry
            self.active_inline_entry = None
            try:
                entry.destroy()
            except Exception:
                pass

    def _on_table_double_click(self, event: tk.Event) -> None:
        self._destroy_inline_entry()

        region = self.table.identify("region", event.x, event.y)
        if region != "cell":
            return

        item_id = self.table.identify_row(event.y)
        col_id = self.table.identify_column(event.x)
        if not item_id or not col_id:
            return

        col_index = int(col_id.replace("#", "")) - 1
        active_cols = self._get_active_columns()
        if col_index < 0 or col_index >= len(active_cols):
            return

        col_info = active_cols[col_index]
        key = col_info["key"]
        rec_idx = self.item_to_rec_idx.get(item_id)
        if rec_idx is None or rec_idx >= len(self.records):
            return

        # Do not allow inline editing while row is still pending/processing
        if self.records[rec_idx].get("_is_pending", False):
            return

        bbox = self.table.bbox(item_id, col_id)
        if not bbox:
            return

        x, y, width, height = bbox
        current_val = self._get_display_value(self.records[rec_idx], key, active_cols)

        t = THEMES[self.current_theme]
        entry = tk.Entry(
            self.table,
            font=("Segoe UI", 10),
            bg=t["entry_bg"],
            fg=t["entry_fg"],
            insertbackground=t["entry_caret"],
            relief="solid",
            bd=1,
            highlightcolor=t["accent_bg"],
            highlightthickness=1,
        )
        align = (
            "center"
            if key in ("dob", "issue_date", "expiry_date", "sex", "age", "cccd_number", "old_cmnd")
            else "left"
        )
        entry.configure(justify=align)
        entry.insert(0, current_val)
        entry.select_range(0, tk.END)
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        self.active_inline_entry = entry

        def commit_edit(e: Any = None) -> None:
            if self.active_inline_entry is None:
                return
            new_val = entry.get()
            self._destroy_inline_entry()
            self.records[rec_idx][key] = new_val
            current_vals = list(self.table.item(item_id, "values"))
            current_vals[col_index] = new_val
            self.table.item(item_id, values=current_vals)
            self._adjust_all_column_widths([self.records[rec_idx]])

        def cancel_edit(e: Any = None) -> None:
            self._destroy_inline_entry()

        entry.bind("<Return>", commit_edit)
        entry.bind("<FocusOut>", commit_edit)
        entry.bind("<Escape>", cancel_edit)

    # =========================================================================
    # Scanning & Background Worker
    # =========================================================================
    def _on_add_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="Chọn các file ảnh CCCD",
            filetypes=[
                (
                    "Tất cả ảnh CCCD (*.jpg, *.png, *.heic, *.webp)",
                    "*.jpg *.jpeg *.png *.bmp *.webp *.heic *.heif",
                ),
                ("Ảnh iPhone / iPad (*.heic, *.heif)", "*.heic *.heif"),
                ("Ảnh JPG / PNG (*.jpg, *.png)", "*.jpg *.jpeg *.png *.bmp"),
                ("Tất cả tập tin (*.*)", "*.*"),
            ],
        )
        if files:
            paths = [Path(f) for f in files if Path(f).suffix.lower() in SUPPORTED_EXTENSIONS]
            if paths:
                self.last_input_dir = str(paths[0].parent)
            self._start_scanning(paths)

    def _on_add_directory(self) -> None:
        folder = filedialog.askdirectory(title="Chọn thư mục chứa ảnh CCCD")
        if folder:
            self.last_input_dir = str(folder)
            dir_path = Path(folder)
            paths = [
                p
                for p in dir_path.rglob("*")
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            if not paths:
                messagebox.showinfo(
                    "Thông báo",
                    "Không tìm thấy file ảnh phù hợp trong thư mục đã chọn.\n"
                    "Phần mềm hỗ trợ các định dạng: JPG, PNG, WEBP, BMP, HEIC/HEIF.",
                )
                return
            self._start_scanning(paths)

    def _has_pending_records(self) -> bool:
        """Check if any records in the application are still awaiting scan completion."""
        return bool(self.task_id_to_rec)

    def _start_scanning(self, paths: list[Path]) -> None:
        if not paths:
            return

        active = self._get_active_columns()
        self.total_queued += len(paths)

        with self._worker_lock:
            start_task_id = self._task_counter
            self._task_counter += len(paths)

        new_pending_recs: list[dict[str, Any]] = []
        # Immediately list out each file as a pending row with loading circle
        for idx, p in enumerate(paths):
            task_id = start_task_id + 1 + idx
            full_path_str = str(p)
            pending_rec: dict[str, Any] = {col["key"]: "" for col in DEFAULT_COLUMNS}
            pending_rec["_is_pending"] = True
            pending_rec["_is_error"] = False
            pending_rec["_full_path"] = full_path_str
            pending_rec["_task_id"] = task_id
            pending_rec["source_file"] = p.name
            pending_rec["status"] = "Đang xử lý..."

            rec_idx = len(self.records)
            pending_rec["_rec_idx"] = rec_idx
            self.records.append(pending_rec)
            new_pending_recs.append(pending_rec)

            values = [self._get_display_value(pending_rec, c["key"], active) for c in active]
            tag = "pending_row"
            parity_tag = "even_row" if rec_idx % 2 == 0 else "odd_row"
            item_id = self.table.insert("", tk.END, values=values, tags=(tag, parity_tag))
            self.item_to_rec_idx[item_id] = rec_idx
            self.task_id_to_item_id[task_id] = item_id
            self.task_id_to_rec[task_id] = pending_rec
            self.pending_item_ids[full_path_str] = item_id

            # Priority 1: Fast Stage 1 scan (~2ms). All fast scans run before any rescue scans!
            self.task_queue.put((1, task_id, p, "FAST"))

        self._adjust_all_column_widths(new_pending_recs)
        self.has_moved_failed_images = False
        self.last_failed_move_dest = None
        self.last_failed_move_items.clear()
        self.last_failed_move_names.clear()
        if hasattr(self, "lbl_failed_empty"):
            self.lbl_failed_empty.place_forget()
        if hasattr(self, "btn_move_toggle"):
            self.btn_move_toggle.config(
                text="📁 Gom ảnh lỗi vào 1 thư mục",
                style="Primary.TButton",
            )
            self.btn_move_toggle.state(["disabled"])
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(text="")

        if self.is_split_mode:
            self._refresh_split_views()
        self._check_empty_state()
        self._update_status_bar()
        self._start_spinner()

        self._ensure_workers_running()

    def _ensure_workers_running(self) -> None:
        """Spawn worker threads up to WORKER_COUNT if below target."""
        with self._worker_lock:
            self.is_scanning = True
            needed = max(0, WORKER_COUNT - self._active_workers)
            for _ in range(needed):
                self._active_workers += 1
                threading.Thread(target=self._worker_thread, daemon=True).start()

    def _worker_thread(self) -> None:
        try:
            # Each worker creates its own scanner (WeChatQRCode C++ state is not thread-safe)
            scanner = CCCDQRScanner()
            counter = 0
            while True:
                try:
                    priority, task_id, file_path, stage = self.task_queue.get(timeout=2.0)
                except queue.Empty:
                    with self._worker_lock:
                        # Only exit if queue is empty AND no pending records remain in the application
                        if self.task_queue.empty() and not self._has_pending_records():
                            break
                    continue

                try:
                    if stage == "FAST":
                        qr_text, scan_note = scanner.scan_fast(file_path)
                        if qr_text:
                            # Fast pass succeeded! Immediate success result
                            record = build_record(file_path, qr_text, scan_note or "OK")
                            record["_task_id"] = task_id
                            record["_is_pending"] = False
                            self.result_queue.put((task_id, record))
                        else:
                            # Fast pass did not find valid QR or file unreadable.
                            # Re-enqueue to Stage 2 Rescue with Priority 2 with same task_id
                            self.task_queue.put((2, task_id, file_path, "RESCUE"))
                            self._ensure_workers_running()
                    else:
                        # Stage == "RESCUE": Runs deep rescue passes (WeChat, CLAHE, Compression, Color)
                        qr_text, scan_note = scanner.scan_rescue(file_path)
                        record = build_record(file_path, qr_text, scan_note)
                        record["_task_id"] = task_id
                        record["_is_pending"] = False
                        self.result_queue.put((task_id, record))
                except Exception:
                    record = build_record(file_path, None, "UNREADABLE")
                    record["_task_id"] = task_id
                    record["status"] = "Cần kiểm tra: Không thể mở file ảnh (file hỏng hoặc bị khóa)"
                    record["_is_pending"] = False
                    self.result_queue.put((task_id, record))
                finally:
                    self.task_queue.task_done()
                    counter += 1
                    if counter % 50 == 0:
                        gc.collect()
        finally:
            # Safely decrement active worker count
            with self._worker_lock:
                self._active_workers -= 1
                if self._active_workers <= 0:
                    self._active_workers = 0
                    self.is_scanning = False

    def _process_queue(self) -> None:
        """Scheduled tick running every 80ms to process completed scan items."""
        try:
            # Dynamically scale batch limit: consume faster when worker results are backlogged
            qsize = self.result_queue.qsize()
            batch_limit = min(100, max(25, qsize))
            active = self._get_active_columns()
            filter_error_only = self.filter_error_var.get()
            inserted = 0
            batch_records: list[dict[str, Any]] = []

            while inserted < batch_limit:
                try:
                    item_data = self.result_queue.get_nowait()
                except queue.Empty:
                    break

                if isinstance(item_data, tuple):
                    task_id_or_path, finished_record = item_data
                else:
                    finished_record = item_data
                    task_id_or_path = finished_record.get("_task_id")

                target_rec: dict[str, Any] | None = None
                item_id: str | None = None

                if isinstance(task_id_or_path, int):
                    target_rec = self.task_id_to_rec.pop(task_id_or_path, None)
                    item_id = self.task_id_to_item_id.pop(task_id_or_path, None)
                else:
                    file_path_str = str(task_id_or_path or finished_record.get("_full_path", ""))
                    item_id = self.pending_item_ids.pop(file_path_str, None)
                    if item_id in self.item_to_rec_idx:
                        idx = self.item_to_rec_idx[item_id]
                        if 0 <= idx < len(self.records):
                            target_rec = self.records[idx]

                if target_rec is not None:
                    target_rec.update(finished_record)
                    target_rec["_is_pending"] = False
                    current_record = target_rec
                else:
                    finished_record["_is_pending"] = False
                    finished_record["_rec_idx"] = len(self.records)
                    self.records.append(finished_record)
                    current_record = finished_record

                self.processed_count += 1
                is_err = current_record.get("_is_error", False)
                row_tag = "error_row" if is_err else "success_row"
                if is_err:
                    self.error_count += 1
                else:
                    self.success_count += 1

                if item_id is not None and self.table.exists(item_id):
                    if filter_error_only and not is_err:
                        try:
                            self.table.delete(item_id)
                            if item_id in self.item_to_rec_idx:
                                del self.item_to_rec_idx[item_id]
                        except Exception:
                            pass
                    else:
                        values = [self._get_display_value(current_record, c["key"], active) for c in active]
                        rec_idx = current_record.get("_rec_idx", 0)
                        parity_tag = "even_row" if rec_idx % 2 == 0 else "odd_row"
                        self.table.item(item_id, values=values, tags=(row_tag, parity_tag))
                        # Only auto-scroll for single/tiny imports. During bulk imports, keep table
                        # viewport stable so the user can freely scroll and inspect rows without jitter.
                        if self.total_queued <= 5:
                            self.table.see(item_id)
                else:
                    if not (filter_error_only and not is_err):
                        values = [self._get_display_value(current_record, c["key"], active) for c in active]
                        rec_idx = current_record.get("_rec_idx", len(self.records) - 1)
                        parity_tag = "even_row" if rec_idx % 2 == 0 else "odd_row"
                        new_item_id = self.table.insert("", tk.END, values=values, tags=(row_tag, parity_tag))
                        self.item_to_rec_idx[new_item_id] = rec_idx

                batch_records.append(current_record)
                inserted += 1

            if batch_records:
                # Dynamically auto-fit column widths across all column types once per batch tick
                self._adjust_all_column_widths(batch_records)
                if self.is_split_mode:
                    self._refresh_split_views()

            self._check_empty_state()
            self._update_status_bar()
        except Exception:
            pass
        finally:
            # Reschedule next polling tick - guaranteed to always run
            self.root.after(80, self._process_queue)

    def _on_select_all_rows(self, event: Any = None) -> str:
        """Select all visible rows in the table (triggered by Ctrl+A)."""
        all_items = self.table.get_children()
        if all_items:
            self.table.selection_set(all_items)
        return "break"

    def _on_table_shift_mousewheel(self, event: tk.Event) -> str:
        """Scroll table horizontally when user holds Shift and spins mouse wheel."""
        if event.delta:
            delta = -1 if event.delta > 0 else 1
            self.table.xview_scroll(delta * 2, "units")
            return "break"
        return ""

    def _delete_records_by_indices(self, indices_to_remove: set[int]) -> None:
        """Remove records by their indices in self.records and update all table data & counters."""
        if not indices_to_remove:
            return

        self._destroy_inline_entry()

        # Build new records list omitting removed indices
        new_records = [rec for i, rec in enumerate(self.records) if i not in indices_to_remove]
        self.records = new_records

        # Recalculate summary counters
        self.total_queued = len(self.records)
        self.processed_count = sum(1 for r in self.records if not r.get("_is_pending", False))
        self.success_count = sum(
            1 for r in self.records if not r.get("_is_error", False) and not r.get("_is_pending", False)
        )
        self.error_count = sum(1 for r in self.records if r.get("_is_error", False))

        # Re-render preview table & status bar
        self._refresh_preview_table_data()
        if self.is_split_mode:
            self._refresh_split_views()
        self._update_status_bar()
        self._check_empty_state()

    def _on_delete_selected_rows(self) -> None:
        """Delete all selected rows from the list."""
        if self.is_scanning:
            messagebox.showwarning(
                "Đang quét ảnh",
                "Phần mềm đang xử lý danh sách ảnh. Vui lòng chờ quét xong trước khi xóa dòng.",
            )
            return

        selected_items = self.table.selection()
        sel_count = len(selected_items)
        if sel_count == 0:
            messagebox.showinfo(
                "Thông báo",
                "Vui lòng chọn dòng cần xóa trong danh sách.\n\n"
                "Mẹo: Bạn có thể giữ phím Ctrl hoặc Shift để chọn nhiều dòng cùng lúc.",
            )
            return

        if sel_count == 1:
            msg = "Bạn có chắc chắn muốn xóa dòng đã chọn khỏi danh sách?"
        else:
            msg = f"Bạn có chắc chắn muốn xóa {sel_count} dòng đã chọn khỏi danh sách?"

        if not messagebox.askyesno("Xác nhận xóa", msg):
            return

        indices = {
            self.item_to_rec_idx[item_id]
            for item_id in selected_items
            if item_id in self.item_to_rec_idx and self.item_to_rec_idx[item_id] < len(self.records)
        }
        self._delete_records_by_indices(indices)

    def _on_delete_single_row(self) -> None:
        """Alias for backwards compatibility."""
        self._on_delete_selected_rows()

    def _on_delete_multiple_rows(self) -> None:
        """Alias for backwards compatibility."""
        self._on_delete_selected_rows()

    def _on_delete_all_failed_rows(self) -> None:
        """Quickly remove all failed upload rows (status is error or needs retake)."""
        if self.is_scanning:
            messagebox.showwarning(
                "Đang quét ảnh",
                "Phần mềm đang xử lý danh sách ảnh. Vui lòng chờ quét xong trước khi xóa các dòng lỗi.",
            )
            return

        err_indices = {i for i, r in enumerate(self.records) if r.get("_is_error", False)}
        if not err_indices:
            messagebox.showinfo(
                "Thông báo",
                "Không có dòng nào bị lỗi trong danh sách. Tất cả các ảnh đã được quét thành công!",
            )
            return

        count = len(err_indices)
        if not messagebox.askyesno(
            "Xác nhận xóa dòng lỗi",
            f"Bạn có chắc chắn muốn xóa nhanh tất cả {count} dòng bị lỗi (cần chụp lại) khỏi danh sách không?",
        ):
            return

        self._delete_records_by_indices(err_indices)

    def _start_spinner(self) -> None:
        """Ensure loading circle animation loop is actively running while files are pending."""
        if not self.spinner_running:
            self.spinner_running = True
            self._animate_spinner()

    def _animate_spinner(self) -> None:
        """Cycle the rotating circle animation on pending items."""
        if not self.task_id_to_rec and not self.is_scanning:
            self.spinner_running = False
            return

        self.spinner_frame_idx = (self.spinner_frame_idx + 1) % len(self.SPINNER_FRAMES)
        current_frame = self.SPINNER_FRAMES[self.spinner_frame_idx]
        active = self._get_active_columns()

        if "status" in [c["key"] for c in active]:
            # In bulk imports, thousands of items may be pending. Updating thousands of table rows
            # 8 times per second starves the Tkinter event loop and freezes the UI.
            # We animate only visible pending rows or up to 40 pending items to keep UI buttery smooth.
            if len(self.task_id_to_item_id) <= 40:
                target_items = list(self.task_id_to_item_id.values())
            else:
                total_records = len(self.records)
                try:
                    y0, y1 = self.table.yview()
                    start_idx = max(0, int(y0 * total_records) - 2)
                    end_idx = min(total_records, int(y1 * total_records) + 4)
                except Exception:
                    start_idx, end_idx = 0, 40

                target_items = []
                for idx in range(start_idx, end_idx):
                    if idx < len(self.records):
                        rec = self.records[idx]
                        if rec.get("_is_pending", False):
                            tid = rec.get("_task_id")
                            if tid in self.task_id_to_item_id:
                                target_items.append(self.task_id_to_item_id[tid])

            for item_id in target_items:
                try:
                    rec_idx = self.item_to_rec_idx.get(item_id)
                    if rec_idx is not None and rec_idx < len(self.records):
                        rec = self.records[rec_idx]
                        if rec.get("_is_pending", False):
                            disp = self._get_display_value(rec, "status", active, spinner_frame=current_frame)
                            self.table.set(item_id, "status", disp)
                except Exception:
                    pass

        self.root.after(120, self._animate_spinner)

    def _on_table_select_changed(self, event: Any = None) -> None:
        """Update context-sensitive action button states when row selection changes."""
        self._update_action_button_states()

    def _update_action_button_states(self) -> None:
        """Dynamically enable or disable contextual deletion buttons based on current selection."""
        sel_items = self.table.selection() if hasattr(self, "table") else ()
        sel_count = len(sel_items)

        if hasattr(self, "btn_delete_selected"):
            if sel_count == 0:
                self.btn_delete_selected.config(text="🗑 Xóa dòng (0)")
                self.btn_delete_selected.state(["disabled"])
            elif sel_count == 1:
                self.btn_delete_selected.config(text="🗑 Xóa 1 dòng")
                self.btn_delete_selected.state(["!disabled"])
            else:
                self.btn_delete_selected.config(text=f"🗑 Xóa {sel_count} dòng")
                self.btn_delete_selected.state(["!disabled"])

        if hasattr(self, "btn_delete_failed"):
            if self.error_count > 0:
                self.btn_delete_failed.state(["!disabled"])
            else:
                self.btn_delete_failed.state(["disabled"])

    def _update_status_bar(self) -> None:
        t = THEMES[self.current_theme]
        # Update filter checkbox label with current error count
        if self.error_count > 0:
            self.chk_filter.config(text=f"✖ Chỉ xem ảnh cần chụp lại ({self.error_count})")
        else:
            self.chk_filter.config(text="Chỉ xem ảnh cần chụp lại (0)")

        # Update delete-failed-rows button label with current error count
        if hasattr(self, "btn_delete_failed"):
            if self.error_count > 0:
                self.btn_delete_failed.config(text=f"🧹 Xóa {self.error_count} dòng lỗi")
            else:
                self.btn_delete_failed.config(text="🧹 Xóa dòng lỗi")

        pending_count = len(self.task_id_to_rec)

        if self.total_queued == 0:
            self.lbl_status.config(
                text="Sẵn sàng. Hãy chọn ảnh hoặc thư mục để bắt đầu quét.",
                fg=t["text_main"],
            )
            if hasattr(self, "lbl_processing_badge"):
                self.lbl_processing_badge.config(text="")
        elif pending_count > 0 or self.processed_count < self.total_queued:
            pct = int((self.processed_count / max(1, self.total_queued)) * 100)
            self.lbl_status.config(
                text=f"🔄 Đang xử lý: {pending_count} file ảnh còn lại ({self.processed_count}/{self.total_queued} hoàn tất - {pct}%) • "
                f"✔ Thành công: {self.success_count} • ✖ Cần chụp lại: {self.error_count}",
                fg=t["primary_btn_bg"],
            )
            if hasattr(self, "lbl_processing_badge"):
                self.lbl_processing_badge.config(
                    text=f"🔄 Đang xử lý {pending_count} file ảnh...",
                )
        else:
            status_text = (
                f"Hoàn tất {self.total_queued} ảnh • "
                f"✔ {self.success_count} thành công • ✖ {self.error_count} cần chụp lại"
            )
            status_color = t["success_fg"] if self.error_count == 0 else t["err_fg"]
            self.lbl_status.config(text=status_text, fg=status_color)
            if hasattr(self, "lbl_processing_badge"):
                self.lbl_processing_badge.config(text="")

        self._update_action_button_states()

    def _on_clear_list(self) -> None:
        if self.is_scanning:
            messagebox.showwarning(
                "Đang quét ảnh",
                "Phần mềm đang xử lý danh sách ảnh hiện tại. Vui lòng chờ quét xong.",
            )
            return

        self._destroy_inline_entry()
        for item in self.table.get_children():
            self.table.delete(item)
        self.records.clear()
        self.item_to_rec_idx.clear()
        self.pending_item_ids.clear()
        self.task_id_to_rec.clear()
        self.task_id_to_item_id.clear()
        self.spinner_running = False
        self.total_queued = 0
        self.processed_count = 0
        self.success_count = 0
        self.error_count = 0
        for col in self._get_active_columns():
            key = col["key"]
            base_w = col.get("width", 120)
            try:
                self.table.column(key, width=base_w, minwidth=60, stretch=False)
            except Exception:
                pass
        self.has_moved_failed_images = False
        self.last_failed_move_dest = None
        self.last_failed_move_items.clear()
        self.last_failed_move_names.clear()
        if hasattr(self, "lbl_failed_empty"):
            self.lbl_failed_empty.place_forget()
        if hasattr(self, "btn_move_toggle"):
            self.btn_move_toggle.config(
                text="📁 Gom ảnh lỗi vào 1 thư mục",
                style="Primary.TButton",
            )
            self.btn_move_toggle.state(["disabled"])
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(text="")

        if self.is_split_mode:
            self._refresh_split_views()
        self._check_empty_state()
        self._update_status_bar()

    # =========================================================================
    # Always-New Excel Export Action & Excel Appending
    # =========================================================================
    def _prepare_export_records_and_columns(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
        """
        Validate and prepare records and columns for Excel export:
        - Excludes any pending records.
        - Excludes error records (_is_error == True), warning the user that they can append them later.
        - Excludes the 'status' column from exported columns.
        Returns (valid_records, export_columns) or None if export should abort.
        """
        if self.is_scanning:
            messagebox.showwarning(
                "Đang quét ảnh",
                "Phần mềm đang xử lý danh sách ảnh. Vui lòng chờ quá trình quét hoàn tất trước khi xuất file.",
            )
            return None

        finished_records = [r for r in self.records if not r.get("_is_pending", False)]
        if not finished_records:
            messagebox.showwarning(
                "Chưa có dữ liệu",
                "Danh sách đang trống hoặc các ảnh chưa xử lý xong. Vui lòng chờ quét xong trước khi xuất file.",
            )
            return None

        valid_records = [r for r in finished_records if not r.get("_is_error", False)]
        error_records = [r for r in finished_records if r.get("_is_error", False)]

        if not valid_records:
            messagebox.showwarning(
                "Không có dữ liệu hợp lệ",
                f"Tất cả {len(error_records)} ảnh hiện tại đều bị lỗi (cần chụp lại).\n\n"
                f"Không có dòng dữ liệu hợp lệ nào để xuất file. Vui lòng chụp lại ảnh rõ nét hơn rồi quét lại.",
            )
            return None

        active = self._get_active_columns()
        # Skip internal status column and file name column (source_file) from Excel export
        export_columns = [c for c in active if c.get("key") not in ("status", "source_file")]
        if not export_columns:
            messagebox.showwarning(
                "Chưa chọn cột",
                "Bạn chưa tích chọn cột dữ liệu CCCD nào để xuất (cột Tên file ảnh và Trạng thái tự động bỏ qua). Vui lòng chọn ít nhất một cột ở bảng bên trái.",
            )
            return None

        # Show a quick warning if error items are skipped so the user knows they can append them later
        if error_records:
            messagebox.showwarning(
                "Lưu ý: Bỏ qua dòng lỗi",
                f"Có {len(error_records)} dòng ảnh bị lỗi (cần chụp lại) sẽ KHÔNG được đưa vào file Excel.\n\n"
                f"Sau khi chụp lại ảnh rõ nét hơn, bạn có thể quét và bấm nút 'Ghi tiếp vào Excel...' để bổ sung vào file này sau.",
            )

        return valid_records, export_columns

    def _on_export_excel(self) -> None:
        prep = self._prepare_export_records_and_columns()
        if prep is None:
            return
        valid_records, export_columns = prep

        default_filename = f"Danh_sach_CCCD_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.xlsx"
        save_path = filedialog.asksaveasfilename(
            title="Lưu file Excel kết quả",
            initialfile=default_filename,
            defaultextension=".xlsx",
            filetypes=[("File Excel (*.xlsx)", "*.xlsx")],
        )

        if not save_path:
            return

        # Resolve junctions / symlinks transparently across C: and secondary drives
        try:
            resolved_path = str(Path(save_path).resolve())
        except Exception:
            resolved_path = save_path

        try:
            export_records_to_excel(valid_records, export_columns, resolved_path)
            open_now = messagebox.askyesno(
                "Xuất file thành công",
                f"Đã lưu thành công {len(valid_records)} dòng dữ liệu vào file:\n{resolved_path}\n\n"
                "Bạn có muốn mở file Excel vừa tạo ngay bây giờ không?",
            )
            if open_now:
                os.startfile(resolved_path)
        except Exception as e:
            messagebox.showerror(
                "Lỗi khi lưu file",
                f"Không thể lưu file Excel do sự cố:\n{e}\n\n"
                "Gợi ý: Kiểm tra xem file có đang bị mở trong phần mềm khác hay không.",
            )

    def _on_append_excel(self) -> None:
        """Append scanned records to an existing Excel workbook if column counts match."""
        prep = self._prepare_export_records_and_columns()
        if prep is None:
            return
        valid_records, export_columns = prep

        file_path = filedialog.askopenfilename(
            title="Chọn file Excel hiện có để ghi tiếp dữ liệu",
            filetypes=[("File Excel (*.xlsx)", "*.xlsx")],
        )

        if not file_path:
            return

        # Resolve junctions / symlinks transparently
        try:
            resolved_path = str(Path(file_path).resolve())
        except Exception:
            resolved_path = file_path

        try:
            appended_count = append_records_to_excel(valid_records, export_columns, resolved_path)
            open_now = messagebox.askyesno(
                "Ghi tiếp thành công",
                f"Đã ghi thêm thành công {appended_count} dòng dữ liệu vào file:\n{resolved_path}\n\n"
                "Bạn có muốn mở file Excel vừa cập nhật ngay bây giờ không?",
            )
            if open_now:
                os.startfile(resolved_path)
        except ValueError as ve:
            # Column count mismatch - halts appending and explains why
            messagebox.showerror("Không thể ghi tiếp", str(ve))
        except Exception as e:
            messagebox.showerror(
                "Lỗi khi ghi file",
                f"Không thể ghi tiếp vào file Excel do sự cố:\n{e}\n\n"
                "Gợi ý: Kiểm tra xem file có đang bị mở trong phần mềm khác hay không.",
            )

    # =========================================================================
    # Split View (Passed / Failed) & Failed Image Handling
    # =========================================================================
    def _on_toggle_split_view(self) -> None:
        """Toggle between the standard single preview table and the split Passed/Failed views."""
        self.is_split_mode = not self.is_split_mode
        if self.is_split_mode:
            self.table_container.pack_forget()
            self.split_container.pack(fill=tk.BOTH, expand=True)
            self.btn_split_toggle.config(text="📋 Gộp lại danh sách chính")
            if hasattr(self, "btn_split_sub"):
                self.btn_split_sub.config(text="📋 Gộp lại danh sách chính")
            self._refresh_split_views()
        else:
            self.split_container.pack_forget()
            self.table_container.pack(fill=tk.BOTH, expand=True)
            self.btn_split_toggle.config(text="⚡ Tách danh sách lỗi")
            if hasattr(self, "btn_split_sub"):
                self.btn_split_sub.config(text="⚡ Tách danh sách lỗi")
            self._refresh_preview_table_data()
        self._check_empty_state()

    def _refresh_split_views(self) -> None:
        """Populate both Passed and Failed tables from self.records."""
        if not hasattr(self, "tree_passed") or not hasattr(self, "tree_failed"):
            return

        self._destroy_inline_entry()
        for item in self.tree_passed.get_children():
            self.tree_passed.delete(item)
        for item in self.tree_failed.get_children():
            self.tree_failed.delete(item)

        self.passed_item_to_rec_idx.clear()
        self.failed_item_to_rec_idx.clear()

        pn = 0
        fn = 0
        for rec_idx, rec in enumerate(self.records):
            is_err = rec.get("_is_error", False)
            is_pending = rec.get("_is_pending", False)

            if is_err:
                if rec.get("_is_moved_to_error_folder", False):
                    continue
                fn += 1
                num_str = f"{fn:03d}"
                fname = rec.get("source_file", "")
                name_val = rec.get("full_name", "") or "(chưa nhập tên)"
                status_val = rec.get("status", "")

                parity_tag = "even_row" if fn % 2 == 0 else "odd_row"
                item_id = self.tree_failed.insert(
                    "",
                    tk.END,
                    values=(num_str, fname, name_val, status_val),
                    tags=("error_row", parity_tag),
                )
                self.failed_item_to_rec_idx[item_id] = rec_idx
            elif not is_pending:
                pn += 1
                num_str = f"{pn:03d}"
                fname = rec.get("source_file", "")
                name_val = rec.get("full_name", "")
                cccd_val = rec.get("cccd_number", "")
                dob_val = rec.get("dob", "")
                status_val = rec.get("status", "")

                parity_tag = "even_row" if pn % 2 == 0 else "odd_row"
                item_id = self.tree_passed.insert(
                    "",
                    tk.END,
                    values=(num_str, fname, name_val, cccd_val, dob_val, status_val),
                    tags=("success_row", parity_tag),
                )
                self.passed_item_to_rec_idx[item_id] = rec_idx

        if hasattr(self, "lbl_failed_empty"):
            if self.has_moved_failed_images and fn == 0:
                self.lbl_failed_empty.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
            else:
                self.lbl_failed_empty.place_forget()

        if hasattr(self, "lbl_passed_title"):
            self.lbl_passed_title.config(text=f"✅ Danh sách Đạt ({pn} thẻ thành công)")
        if hasattr(self, "lbl_failed_title"):
            if self.has_moved_failed_images and fn == 0:
                self.lbl_failed_title.config(text="❌ Danh sách Cần chụp lại (Đã gom vào thư mục 'Ảnh lỗi')")
            else:
                self.lbl_failed_title.config(text=f"❌ Danh sách Cần chụp lại ({fn} ảnh lỗi)")

        if hasattr(self, "btn_move_toggle"):
            if self.has_moved_failed_images:
                self.btn_move_toggle.config(
                    text="↩ Hoàn tác gom ảnh",
                    style="SmallDanger.TButton",
                )
                self.btn_move_toggle.state(["!disabled"])
            else:
                self.btn_move_toggle.config(
                    text="📁 Gom ảnh lỗi vào 1 thư mục",
                    style="Primary.TButton",
                )
                if fn > 0:
                    self.btn_move_toggle.state(["!disabled"])
                else:
                    self.btn_move_toggle.state(["disabled"])

    def _on_split_failed_double_click(self, event: tk.Event) -> None:
        """Handle double clicks on the Failed list: column #3 edits Name, other columns open the full image."""
        self._destroy_inline_entry()

        item_id = self.tree_failed.identify_row(event.y)
        col_id = self.tree_failed.identify_column(event.x)
        if not item_id or not col_id:
            return

        rec_idx = self.failed_item_to_rec_idx.get(item_id)
        if rec_idx is None or rec_idx >= len(self.records):
            return

        rec = self.records[rec_idx]

        # Column "#3" is "full_name" (Họ và tên)
        if col_id == "#3":
            bbox = self.tree_failed.bbox(item_id, col_id)
            if not bbox:
                return
            x, y, width, height = bbox
            current_val = rec.get("full_name", "")

            t = THEMES[self.current_theme]
            entry = tk.Entry(
                self.tree_failed,
                font=("Segoe UI", 10),
                bg=t["entry_bg"],
                fg=t["entry_fg"],
                insertbackground=t["entry_caret"],
                relief="solid",
                bd=1,
                highlightcolor=t["accent_bg"],
                highlightthickness=1,
            )
            entry.insert(0, current_val)
            entry.select_range(0, tk.END)
            entry.place(x=x, y=y, width=width, height=height)
            entry.focus_set()
            self.active_inline_entry = entry

            def commit_edit(e: Any = None) -> None:
                if self.active_inline_entry is None:
                    return
                new_val = entry.get().strip()
                self._destroy_inline_entry()
                rec["full_name"] = new_val
                current_vals = list(self.tree_failed.item(item_id, "values"))
                current_vals[2] = new_val if new_val else "(chưa nhập tên)"
                self.tree_failed.item(item_id, values=current_vals)

            def cancel_edit(e: Any = None) -> None:
                self._destroy_inline_entry()

            entry.bind("<Return>", commit_edit)
            entry.bind("<FocusOut>", commit_edit)
            entry.bind("<Escape>", cancel_edit)
        else:
            # Double-click any other column opens the full image file
            path = rec.get("_full_path", "")
            if path and os.path.exists(path):
                try:
                    open_path(path)
                except Exception as e:
                    messagebox.showerror("Lỗi mở ảnh", f"Không mở được tệp ảnh:\n{e}")
            else:
                messagebox.showwarning("Thông báo", f"Không tìm thấy file ảnh gốc:\n{path}")

    def _on_split_passed_double_click(self, event: tk.Event) -> None:
        """Handle double clicks on the Passed list: edit Name on column #3, open file on column #2."""
        self._destroy_inline_entry()

        item_id = self.tree_passed.identify_row(event.y)
        col_id = self.tree_passed.identify_column(event.x)
        if not item_id or not col_id:
            return

        rec_idx = self.passed_item_to_rec_idx.get(item_id)
        if rec_idx is None or rec_idx >= len(self.records):
            return

        rec = self.records[rec_idx]

        if col_id == "#3":
            bbox = self.tree_passed.bbox(item_id, col_id)
            if not bbox:
                return
            x, y, width, height = bbox
            current_val = rec.get("full_name", "")

            t = THEMES[self.current_theme]
            entry = tk.Entry(
                self.tree_passed,
                font=("Segoe UI", 10),
                bg=t["entry_bg"],
                fg=t["entry_fg"],
                insertbackground=t["entry_caret"],
                relief="solid",
                bd=1,
                highlightcolor=t["accent_bg"],
                highlightthickness=1,
            )
            entry.insert(0, current_val)
            entry.select_range(0, tk.END)
            entry.place(x=x, y=y, width=width, height=height)
            entry.focus_set()
            self.active_inline_entry = entry

            def commit_edit(e: Any = None) -> None:
                if self.active_inline_entry is None:
                    return
                new_val = entry.get().strip()
                self._destroy_inline_entry()
                rec["full_name"] = new_val
                current_vals = list(self.tree_passed.item(item_id, "values"))
                current_vals[2] = new_val
                self.tree_passed.item(item_id, values=current_vals)

            def cancel_edit(e: Any = None) -> None:
                self._destroy_inline_entry()

            entry.bind("<Return>", commit_edit)
            entry.bind("<FocusOut>", commit_edit)
            entry.bind("<Escape>", cancel_edit)
        elif col_id == "#2":
            path = rec.get("_full_path", "")
            if path and os.path.exists(path):
                try:
                    open_path(path)
                except Exception as e:
                    messagebox.showerror("Lỗi mở ảnh", f"Không mở được tệp ảnh:\n{e}")

    def _on_split_failed_delete(self, event: Any = None) -> None:
        sel = self.tree_failed.selection()
        if not sel:
            return
        indices = {
            self.failed_item_to_rec_idx[item_id]
            for item_id in sel
            if item_id in self.failed_item_to_rec_idx
        }
        self._delete_records_by_indices(indices)

    def _on_split_passed_delete(self, event: Any = None) -> None:
        sel = self.tree_passed.selection()
        if not sel:
            return
        indices = {
            self.passed_item_to_rec_idx[item_id]
            for item_id in sel
            if item_id in self.passed_item_to_rec_idx
        }
        self._delete_records_by_indices(indices)

    def _on_handle_failed_images_action(self) -> None:
        """Single merged button handler: toggles between moving to 'Ảnh lỗi' and undoing."""
        if self.has_moved_failed_images:
            self._on_undo_move_failed_images()
        else:
            self._on_move_failed_images()

    def _on_move_failed_images(self) -> None:
        if self.is_scanning:
            messagebox.showwarning(
                "Đang quét ảnh",
                "Phần mềm đang xử lý danh sách ảnh. Vui lòng chờ quét xong trước khi gom ảnh lỗi.",
            )
            return

        failed_recs = [
            rec
            for rec in self.records
            if rec.get("_is_error", False)
            and not rec.get("_is_moved_to_error_folder", False)
            and rec.get("_full_path")
        ]

        if not failed_recs:
            messagebox.showinfo("Thông báo", "Không có ảnh lỗi nào trong danh sách cần gom.")
            return

        items = [(rec.get("_full_path", ""), rec.get("full_name", "")) for rec in failed_recs]

        # Automatically locate parent directory and create "Ảnh lỗi" subfolder
        first_path = Path(items[0][0])
        base_dir = (
            Path(self.last_input_dir)
            if self.last_input_dir and Path(self.last_input_dir).is_dir()
            else first_path.parent
        )
        dest_dir = base_dir / "Ảnh lỗi"

        if hasattr(self, "btn_move_toggle"):
            self.btn_move_toggle.state(["disabled"])
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(text=f"Đang gom 0/{len(items)} ảnh lỗi vào thư mục...")

        move_queue = queue.Queue()

        def poll_move_queue():
            finished = False
            try:
                while True:
                    msg_type, data = move_queue.get_nowait()
                    if msg_type == "progress":
                        cur, tot = data
                        self._update_move_progress(cur, tot)
                    elif msg_type == "done":
                        dest, moved, errors = data
                        self._after_move_failed(dest, moved, errors, failed_recs)
                        finished = True
                        break
            except queue.Empty:
                pass

            if not finished:
                self.root.after(40, poll_move_queue)

        def work():
            try:
                dest, moved, errors = move_failed(
                    items,
                    dest_dir,
                    folder_name="Ảnh lỗi",
                    progress=lambda i, total: move_queue.put(("progress", (i, total))),
                )
                move_queue.put(("done", (dest, moved, errors)))
            except Exception as e:
                move_queue.put(("done", (dest_dir, {}, [("", str(e))])))

        self.root.after(40, poll_move_queue)
        threading.Thread(target=work, daemon=True).start()

    def _update_move_progress(self, current: int, total: int) -> None:
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(text=f"Đang gom {current}/{total}...")

    def _after_move_failed(
        self,
        dest: Path,
        moved: dict[str, str],
        errors: list[tuple[str, str]],
        failed_recs: list[dict[str, Any]] | None = None,
    ) -> None:
        if failed_recs is None:
            failed_recs = [
                rec
                for rec in self.records
                if rec.get("_is_error", False) and rec.get("_full_path") in moved
            ]

        self.last_failed_move_dest = dest
        self.last_failed_move_items = {new_p: old_p for old_p, new_p in moved.items()}
        self.last_failed_move_names = {}

        for rec in failed_recs:
            old_p = rec.get("_full_path", "")
            if old_p in moved:
                new_p = moved[old_p]
                rec["_orig_path_before_move"] = old_p
                orig_name = rec.get("source_file", Path(old_p).name)
                rec["_orig_name_before_move"] = orig_name
                self.last_failed_move_names[old_p] = orig_name
                rec["_full_path"] = new_p
                rec["source_file"] = Path(new_p).name
                rec["_is_moved_to_error_folder"] = True

        self.has_moved_failed_images = True
        self.last_moved_log_path = str(dest / "_moved_log.csv")

        self._refresh_preview_table_data()
        if self.is_split_mode:
            self._refresh_split_views()

        if hasattr(self, "btn_move_toggle"):
            self.btn_move_toggle.config(
                text="↩ Hoàn tác gom ảnh",
                style="SmallDanger.TButton",
            )
            self.btn_move_toggle.state(["!disabled"])

        dest_str = str(dest)
        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(text=f"Đã gom {len(moved)} ảnh vào: {dest_str}")

        msg = (
            f"Đã gom thành công {len(moved)} ảnh lỗi vào thư mục:\n{dest_str}\n\n"
            "Danh sách ảnh lỗi đã được làm trống. Bạn có thể bấm nút 'Hoàn tác gom ảnh' bất cứ lúc nào để khôi phục lại."
        )
        if errors:
            msg += f"\n\n{len(errors)} tệp không thể chuyển (đang mở ở chương trình khác hoặc bị khóa)."

        messagebox.showinfo("Đã gom ảnh lỗi", msg)
        try:
            open_path(dest_str)
        except Exception:
            pass

    def _on_undo_move_failed_images(self) -> None:
        """One-click instant undo: moves images out of 'Ảnh lỗi' back to original folder, removes 'Ảnh lỗi' folder."""
        dest = self.last_failed_move_dest
        log_csv = self.last_moved_log_path
        moved_pairs = getattr(self, "last_failed_move_items", {})

        restored_count = 0
        errors = []

        # 1. Restore files back using stored mapping
        for new_p, orig_p in list(moved_pairs.items()):
            new_path = Path(new_p)
            orig_path = Path(orig_p)
            if new_path.exists():
                try:
                    orig_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(new_path), str(orig_path))
                    restored_count += 1
                except OSError as e:
                    errors.append((new_p, str(e)))

        # Fallback to log CSV if moved_pairs was empty for any reason
        if restored_count == 0 and log_csv and Path(log_csv).exists():
            restored_dict, errs = restore_moved(log_csv, delete_empty_folder=True)
            restored_count = len(restored_dict)
            errors.extend(errs)

        # 2. Delete empty "Ảnh lỗi" folder and log
        if dest and dest.exists():
            log_file = dest / "_moved_log.csv"
            if log_file.exists():
                try:
                    log_file.unlink()
                except Exception:
                    pass
            try:
                dest.rmdir()
            except Exception:
                pass

        # 3. Restore records in self.records so they reappear in tree_failed
        for rec in self.records:
            if rec.get("_is_moved_to_error_folder", False):
                orig_p = rec.get("_orig_path_before_move")
                orig_name = rec.get("_orig_name_before_move")
                if orig_p:
                    rec["_full_path"] = orig_p
                if orig_name:
                    rec["source_file"] = orig_name
                rec["_is_moved_to_error_folder"] = False

        self.has_moved_failed_images = False
        self.last_failed_move_dest = None
        self.last_failed_move_items = {}
        self.last_failed_move_names = {}

        # 4. Refresh views
        self._refresh_preview_table_data()
        if self.is_split_mode:
            self._refresh_split_views()

        # 5. Switch button back to State 1
        if hasattr(self, "btn_move_toggle"):
            self.btn_move_toggle.config(
                text="📁 Gom ảnh lỗi vào 1 thư mục",
                style="Primary.TButton",
            )
            fn_count = sum(1 for r in self.records if r.get("_is_error", False))
            if fn_count > 0:
                self.btn_move_toggle.state(["!disabled"])
            else:
                self.btn_move_toggle.state(["disabled"])

        if hasattr(self, "lbl_move_status"):
            self.lbl_move_status.config(
                text="Đã hoàn tác: Các ảnh lỗi đã được đưa trở lại thư mục gốc và xóa thư mục 'Ảnh lỗi'."
            )

        make_preview.cache_clear()

    def _on_restore_failed_images(self) -> None:
        """Alias for _on_undo_move_failed_images for compatibility with test suites."""
        self._on_undo_move_failed_images()


def launch_gui() -> None:
    root = tk.Tk()
    app = CCCDScannerApp(root)
    root.mainloop()
