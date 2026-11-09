# CCCD QR Scanner for Nger ❤️

A high-performance desktop application for batch-scanning Vietnamese Citizen Identity Card (CCCD) QR codes and exporting parsed personal information directly into Excel spreadsheets.

---

## Key Features

- **5-Pass High-Accuracy QR Engine**:
  - **Pass 1: Fast C++ Native Scan**: Instant decode using `zxing-cpp` (~10ms).
  - **Pass 2: Deep-Learning Super-Resolution**: Built-in OpenCV `WeChatQRCode` Caffe model (~35ms).
  - **Pass 3: Glare Recovery & Quadrant Crop**: CLAHE equalization, 2x cubic upscaling, white quiet zone padding, and 90°/180°/270° rotations.
  - **Pass 4: Compression Auto-Rescue**: Unsharp masking and Lanczos super-upscaling to reconstruct heavily compressed images (Zalo/Messenger artifacts).
  - **Pass 5: Color-Channel Rescue**: Blue and Blue+Green channel isolation to suppress cyan/green CCCD guilloche security backgrounds.
- **Responsive Multi-Threaded Architecture**:
  - Image decoding is offloaded to a worker thread pool (`ThreadPoolExecutor`), keeping the GUI completely responsive during bulk folder processing.
  - Live animated loading indicator (`◐ ◓ ◑ ◒`) during active scans.
- **Enhanced Visual Status & Themes**:
  - Status badge recognition:
    - 🟢 **Success**: Highlighted in soft emerald green (`#ECFDF5`).
    - 🔴 **Failed / Unreadable**: Highlighted in soft rose/red (`#FEF2F2`) with explicit error guidance.
    - ⏳ **Processing**: Highlighted in soft blue (`#EFF6FF`).
  - High-comfort themes: **☀️ Light** (soft off-white `#F1F5F9`) and **🌙 Dark** (slate `#0F172A`).
  - Embedded toolbar controls: Clean single-line layout for image addition, list clearing, and theme switching.
- **Interactive Row Management**:
  - **Delete 1 Row (`🗑 Xóa 1 dòng`)**: Delete a single selected row from the table directly from the bottom control bar.
  - **Delete Multiple Rows (`🗑 Xóa nhiều dòng`)**: Multi-row deletion supporting range selection (`Shift+Click`), multi-selection (`Ctrl+Click`), select-all (`Ctrl+A`), keyboard hotkeys (`Delete`/`Backspace`), and one-click bulk removal of all failed rows.
- **Excel Export**:
  - Create new `.xlsx` files with styled headers and auto-adjusted column widths.
  - Append to existing Excel workbooks with automated `.bak` backup safety.
- **Apple HEIC/HEIF Support**: Native loading of Apple iPhone photo formats via `pillow-heif`.

---

## Project Structure

```text
CCCD for Nger/
├── assets/
│   ├── wechat_models/          # OpenCV WeChatQRCode Caffe model files
│   └── icon.ico                # Application window & installer icon
├── docs/
│   └── edge_cases.md           # Optical limits & photographic best practices
├── src/
│   ├── config.py               # Color themes, column definitions, persistence
│   ├── excel_exporter.py       # OpenPyXL export & template appending engine
│   ├── gui.py                  # Tkinter desktop interface & worker thread pool
│   ├── parser.py               # Vietnamese CCCD QR payload parser & validator
│   └── qr_engine.py            # 5-Pass multi-algorithm QR extraction pipeline
├── tests/
│   ├── test_excel_exporter.py  # Unit tests for Excel creation & appending
│   ├── test_gui_features.py    # Unit tests for UI config & formatting
│   ├── test_parser.py          # Unit tests for payload regex & date conversion
│   └── test_qr_engine.py       # Unit tests for multi-pass decoding & padding
├── build_portable.bat          # PyInstaller standalone portable directory build
├── compile_installer.bat       # Inno Setup Windows installer compiler
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
└── setup_models.py             # Automatic model downloader
```

---

## Installation & Development Setup

### Prerequisites
- Python 3.10+ (tested up to Python 3.14 on Windows 11)

### Setup Virtual Environment
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Download Model Assets
```bash
python setup_models.py
```

### Launch the Application
```bash
python main.py
```

### Run Automated Unit Tests
```bash
pytest
```
*All 23 unit tests pass across parser validation, Excel operations, GUI configuration, and QR extraction.*

---

## Building Executables

### 1. Standalone Portable Folder
Runs unit tests, sets up assets, and packages into `dist/CCCDScanner/`:
```bat
build_portable.bat
```
Run the executable directly via:
```text
dist\CCCDScanner\CCCDScanner.exe
```

### 2. Windows Setup Installer
Compiles a standalone setup wizard using Inno Setup 6:
```bat
compile_installer.bat
```
Output installer:
```text
installer_output\CCCD_Scanner_Setup.exe
```

---

## Edge Cases & Photography Guide

For details on optical resolution limits (Nyquist-Shannon sampling limit) and why extreme long-range shots cannot be decoded, please refer to [docs/edge_cases.md](docs/edge_cases.md).
