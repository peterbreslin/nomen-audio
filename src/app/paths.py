"""Path resolution — auto-detects dev vs production (PyInstaller frozen) mode."""

import os
import sys

# Module-level cache
_bundle_dir: str | None = None
_data_dir: str | None = None


def init() -> None:
    """Initialize path resolution and create necessary directories in production."""
    global _bundle_dir, _data_dir

    if getattr(sys, "frozen", False):
        # PyInstaller onedir: bundled data in _internal (sys._MEIPASS), writable in %APPDATA%
        _bundle_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        _data_dir = os.path.join(os.environ["APPDATA"], "NomenAudio")

        # Create writable directories in production
        os.makedirs(_data_dir, exist_ok=True)
        os.makedirs(os.path.join(_data_dir, "cache"), exist_ok=True)
    else:
        # Dev: everything under ./data/ relative to CWD
        _bundle_dir = "data"
        _data_dir = "data"


def get_db_path() -> str:
    """Return path to SQLite database file."""
    if _data_dir is None:
        raise RuntimeError("paths.init() not called")
    return os.path.join(_data_dir, "nomen.db")


def get_settings_path() -> str:
    """Return path to settings.json file."""
    if _data_dir is None:
        raise RuntimeError("paths.init() not called")
    return os.path.join(_data_dir, "settings.json")


def get_cache_dir() -> str:
    """Return path to cache directory."""
    if _data_dir is None:
        raise RuntimeError("paths.init() not called")
    return os.path.join(_data_dir, "cache")


def get_ucs_full_list() -> str:
    """Return path to UCS Full List xlsx file."""
    if _bundle_dir is None:
        raise RuntimeError("paths.init() not called")
    return os.path.join(_bundle_dir, "UCS", "UCS v8.2.1 Full List.xlsx")


def get_ucs_top_level() -> str:
    """Return path to UCS Top Level Categories xlsx file."""
    if _bundle_dir is None:
        raise RuntimeError("paths.init() not called")
    return os.path.join(_bundle_dir, "UCS", "UCS v8.2.1 Top Level Categories.xlsx")
