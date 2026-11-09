"""Shared pytest fixtures."""

from pathlib import Path
import tkinter as tk
import pytest


@pytest.fixture(autouse=True)
def isolate_test_appdata(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch):
    """Ensure tests run with clean isolated configuration in a temp AppData directory."""
    temp_appdata = tmp_path_factory.mktemp("test_appdata")
    monkeypatch.setenv("LOCALAPPDATA", str(temp_appdata))


@pytest.fixture(scope="session")
def shared_root():
    """Create a single shared hidden Tk instance for test session."""
    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError:
        pytest.skip("Tkinter display not available in headless test environment")
    yield root
    try:
        root.destroy()
    except Exception:
        pass
