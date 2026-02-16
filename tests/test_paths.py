"""Tests for path resolution module."""

import os
import sys
from unittest.mock import patch

import pytest

from app import paths


@pytest.fixture(autouse=True)
def reset_paths():
    """Reset module-level cache before each test."""
    paths._bundle_dir = None
    paths._data_dir = None
    yield
    paths._bundle_dir = None
    paths._data_dir = None


def test_init_dev_mode():
    """In dev mode (not frozen), both dirs point to 'data'."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        assert paths._bundle_dir == "data"
        assert paths._data_dir == "data"


def test_init_frozen_mode():
    """In frozen mode (PyInstaller), bundle dir = _MEIPASS, data dir = %APPDATA%."""
    fake_meipass = r"C:\Program Files\Nomen Audio\_internal"
    fake_appdata = r"C:\Users\TestUser\AppData\Roaming"

    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", fake_meipass, create=True),
        patch.dict(os.environ, {"APPDATA": fake_appdata}),
        patch("os.makedirs") as mock_makedirs,
    ):
        paths.init()
        assert paths._bundle_dir == r"C:\Program Files\Nomen Audio\_internal"
        assert paths._data_dir == r"C:\Users\TestUser\AppData\Roaming\NomenAudio"

        # Verify directories are created
        assert mock_makedirs.call_count == 2
        mock_makedirs.assert_any_call(
            r"C:\Users\TestUser\AppData\Roaming\NomenAudio", exist_ok=True
        )
        mock_makedirs.assert_any_call(
            r"C:\Users\TestUser\AppData\Roaming\NomenAudio\cache", exist_ok=True
        )


def test_get_db_path_dev():
    """DB path in dev mode."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        assert paths.get_db_path() == os.path.join("data", "nomen.db")


def test_get_db_path_frozen():
    """DB path in frozen mode."""
    fake_appdata = r"C:\Users\TestUser\AppData\Roaming"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", r"C:\fake\_internal", create=True),
        patch.dict(os.environ, {"APPDATA": fake_appdata}),
        patch("os.makedirs"),
    ):
        paths.init()
        assert paths.get_db_path() == r"C:\Users\TestUser\AppData\Roaming\NomenAudio\nomen.db"


def test_get_settings_path_dev():
    """Settings path in dev mode."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        assert paths.get_settings_path() == os.path.join("data", "settings.json")


def test_get_settings_path_frozen():
    """Settings path in frozen mode."""
    fake_appdata = r"C:\Users\TestUser\AppData\Roaming"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", r"C:\fake\_internal", create=True),
        patch.dict(os.environ, {"APPDATA": fake_appdata}),
        patch("os.makedirs"),
    ):
        paths.init()
        assert paths.get_settings_path() == r"C:\Users\TestUser\AppData\Roaming\NomenAudio\settings.json"


def test_get_cache_dir_dev():
    """Cache dir in dev mode."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        assert paths.get_cache_dir() == os.path.join("data", "cache")


def test_get_cache_dir_frozen():
    """Cache dir in frozen mode."""
    fake_appdata = r"C:\Users\TestUser\AppData\Roaming"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", r"C:\fake\_internal", create=True),
        patch.dict(os.environ, {"APPDATA": fake_appdata}),
        patch("os.makedirs"),
    ):
        paths.init()
        assert paths.get_cache_dir() == r"C:\Users\TestUser\AppData\Roaming\NomenAudio\cache"


def test_get_ucs_full_list_dev():
    """UCS Full List path in dev mode."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        expected = os.path.join("data", "UCS", "UCS v8.2.1 Full List.xlsx")
        assert paths.get_ucs_full_list() == expected


def test_get_ucs_full_list_frozen():
    """UCS Full List path in frozen mode — bundled read-only data in _MEIPASS."""
    fake_meipass = r"C:\Program Files\Nomen Audio\_internal"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", fake_meipass, create=True),
        patch.dict(os.environ, {"APPDATA": r"C:\Users\TestUser\AppData\Roaming"}),
        patch("os.makedirs"),
    ):
        paths.init()
        expected = rf"{fake_meipass}\UCS\UCS v8.2.1 Full List.xlsx"
        assert paths.get_ucs_full_list() == expected


def test_get_ucs_top_level_dev():
    """UCS Top Level path in dev mode."""
    with patch.object(sys, "frozen", False, create=True):
        paths.init()
        expected = os.path.join("data", "UCS", "UCS v8.2.1 Top Level Categories.xlsx")
        assert paths.get_ucs_top_level() == expected


def test_get_ucs_top_level_frozen():
    """UCS Top Level path in frozen mode — bundled read-only data in _MEIPASS."""
    fake_meipass = r"C:\Program Files\Nomen Audio\_internal"
    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", fake_meipass, create=True),
        patch.dict(os.environ, {"APPDATA": r"C:\Users\TestUser\AppData\Roaming"}),
        patch("os.makedirs"),
    ):
        paths.init()
        expected = rf"{fake_meipass}\UCS\UCS v8.2.1 Top Level Categories.xlsx"
        assert paths.get_ucs_top_level() == expected


def test_get_path_before_init_raises():
    """Calling path getters before init() raises RuntimeError."""
    with pytest.raises(RuntimeError, match="paths.init\\(\\) not called"):
        paths.get_db_path()

    with pytest.raises(RuntimeError, match="paths.init\\(\\) not called"):
        paths.get_settings_path()

    with pytest.raises(RuntimeError, match="paths.init\\(\\) not called"):
        paths.get_cache_dir()

    with pytest.raises(RuntimeError, match="paths.init\\(\\) not called"):
        paths.get_ucs_full_list()

    with pytest.raises(RuntimeError, match="paths.init\\(\\) not called"):
        paths.get_ucs_top_level()
