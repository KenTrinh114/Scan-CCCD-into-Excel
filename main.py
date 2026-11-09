"""Application entry point for CCCD QR Bulk Extractor."""

import sys
import ctypes

def enable_high_dpi() -> None:
    """Enable Windows high DPI scaling and register AppUserModelID for taskbar icon."""
    if sys.platform == "win32":
        try:
            # Set Process DPI Awareness (Per-Monitor v2 or System-aware)
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass
        try:
            # Register explicit AppUserModelID so Windows taskbar displays the custom app icon
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nger.CCCDScanner.App.v1")
        except Exception:
            pass

def main() -> None:
    enable_high_dpi()
    from src.gui import launch_gui
    launch_gui()

if __name__ == "__main__":
    main()
