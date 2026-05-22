"""Tests for the ML model manager singleton."""

from unittest.mock import MagicMock, patch

import pytest

from app.ml import model_manager


class _StubProvider:
    """Stand-in for OllamaProvider in tests — never hits the network."""

    reachable = False

    def __init__(self, **kwargs):
        pass

    def is_reachable(self):
        return _StubProvider.reachable


@pytest.fixture(autouse=True)
def _reset_manager(monkeypatch):
    """Reset model_manager module state before each test."""
    model_manager._classifier = None
    model_manager._captioner = None
    model_manager._loading = False
    model_manager._ready = False
    model_manager._error = None
    model_manager._status_message = ""
    model_manager._llm_reachable_cache = None
    # Stub OllamaProvider so get_status()'s probe never touches the real daemon.
    _StubProvider.reachable = False
    monkeypatch.setattr(model_manager, "OllamaProvider", _StubProvider)
    yield
    model_manager._classifier = None
    model_manager._captioner = None
    model_manager._loading = False
    model_manager._ready = False
    model_manager._error = None
    model_manager._status_message = ""
    model_manager._llm_reachable_cache = None


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def test_initial_status():
    status = model_manager.get_status()
    assert status["loading"] is False
    assert status["clap_loaded"] is False
    assert status["embeddings_ready"] is False


@patch("app.ml.model_manager._load_pipeline")
def test_start_loading_sets_loading(mock_pipeline):
    mock_pipeline.return_value = None
    model_manager.start_loading()
    # Give thread a moment to start
    import time

    time.sleep(0.05)
    # Thread ran _load_pipeline which was mocked
    # After the mock returns, loading should be done
    model_manager.get_status()  # verify no crash


@patch("app.ml.model_manager._load_pipeline")
def test_start_loading_success_sets_ready(mock_pipeline):
    def fake_load():
        model_manager._classifier = MagicMock()
        model_manager._classifier.is_ready.return_value = True
        model_manager._ready = True

    mock_pipeline.side_effect = fake_load
    model_manager.start_loading()
    import time

    time.sleep(0.1)
    assert model_manager.is_ready() is True
    status = model_manager.get_status()
    assert status["clap_loaded"] is True
    assert status["embeddings_ready"] is True


@patch("app.ml.model_manager._load_pipeline")
def test_start_loading_error(mock_pipeline):
    mock_pipeline.side_effect = RuntimeError("Model download failed")
    model_manager.start_loading()
    import time

    time.sleep(0.1)
    assert model_manager.is_ready() is False
    status = model_manager.get_status()
    assert status["error"] is not None
    assert "Model download failed" in status["error"]


# ---------------------------------------------------------------------------
# get_classifier
# ---------------------------------------------------------------------------


def test_get_classifier_raises_when_not_ready():
    with pytest.raises(RuntimeError, match="not ready"):
        model_manager.get_classifier()


def test_get_classifier_returns_when_ready():
    mock_cls = MagicMock()
    model_manager._classifier = mock_cls
    model_manager._ready = True
    assert model_manager.get_classifier() is mock_cls


# ---------------------------------------------------------------------------
# get_captioner (lazy load)
# ---------------------------------------------------------------------------


@patch("app.ml.model_manager.CLAPCaptioner")
def test_get_captioner_lazy_loads(mock_cap_cls):
    mock_instance = MagicMock()
    mock_cap_cls.return_value = mock_instance
    model_manager._ready = True

    cap = model_manager.get_captioner()
    assert cap is mock_instance
    mock_instance.load_model.assert_called_once()


@patch("app.ml.model_manager.CLAPCaptioner")
def test_get_captioner_reuses_instance(mock_cap_cls):
    mock_instance = MagicMock()
    model_manager._captioner = mock_instance
    model_manager._ready = True

    cap = model_manager.get_captioner()
    assert cap is mock_instance
    mock_cap_cls.assert_not_called()


# ---------------------------------------------------------------------------
# LLM rerank status (probe cache + enabled gate)
# ---------------------------------------------------------------------------


def test_get_status_skips_probe_when_rerank_disabled(monkeypatch):
    """Don't probe Ollama if rerank is off — short-circuits to False."""
    from app.services.settings import AppSettings

    fake = AppSettings(llm_rerank_enabled=False)
    monkeypatch.setattr("app.services.settings.get_settings", lambda: fake)
    _StubProvider.reachable = True  # would return True if probed

    status = model_manager.get_status()

    assert status["llm_rerank_enabled"] is False
    assert status["llm_provider_reachable"] is False


def test_probe_llm_reachable_caches_within_ttl(monkeypatch):
    """One Ollama probe per TTL window, even across many calls."""
    from app.services.settings import AppSettings

    calls = []

    class CountingProvider:
        def __init__(self, **kwargs):
            pass

        def is_reachable(self):
            calls.append(1)
            return True

    monkeypatch.setattr(model_manager, "OllamaProvider", CountingProvider)
    fake = AppSettings(llm_rerank_enabled=True)

    assert model_manager._probe_llm_reachable(fake) is True
    assert model_manager._probe_llm_reachable(fake) is True
    assert model_manager._probe_llm_reachable(fake) is True
    assert len(calls) == 1


def test_probe_llm_reachable_reprobes_after_ttl(monkeypatch):
    """Once the TTL expires, the next call re-probes the daemon."""
    from app.services.settings import AppSettings

    calls = []

    class CountingProvider:
        def __init__(self, **kwargs):
            pass

        def is_reachable(self):
            calls.append(1)
            return True

    monkeypatch.setattr(model_manager, "OllamaProvider", CountingProvider)
    fake = AppSettings(llm_rerank_enabled=True)

    model_manager._probe_llm_reachable(fake)
    # Forge a cache entry older than the TTL.
    ts, reachable = model_manager._llm_reachable_cache
    model_manager._llm_reachable_cache = (
        ts - model_manager._LLM_REACHABLE_TTL - 1,
        reachable,
    )
    model_manager._probe_llm_reachable(fake)

    assert len(calls) == 2
