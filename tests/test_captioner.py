"""Tests for the CLAP captioner module."""

from app.ml.captioner import _cleanup_caption


def test_cleanup_strip_whitespace():
    assert _cleanup_caption("  hello world  ") == "Hello world."


def test_cleanup_capitalize():
    assert _cleanup_caption("ocean waves") == "Ocean waves."


def test_cleanup_already_punctuated():
    assert _cleanup_caption("Ocean waves.") == "Ocean waves."


def test_cleanup_exclamation():
    assert _cleanup_caption("loud crash!") == "Loud crash!"


def test_cleanup_truncate():
    long = "a" * 300
    result = _cleanup_caption(long)
    assert len(result) <= 256
    assert result.endswith("...")


def test_cleanup_empty():
    assert _cleanup_caption("") == ""
    assert _cleanup_caption("   ") == ""
