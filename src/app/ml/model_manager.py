"""ML model manager — singleton pattern for background model loading."""

import logging
import os
import threading

from app import paths
from app.llm.ollama_provider import OllamaProvider
from app.ml.captioner import CLAPCaptioner
from app.ml.classifier import CLAPClassifier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

_classifier: CLAPClassifier | None = None
_captioner: CLAPCaptioner | None = None
_llm_provider: OllamaProvider | None = None
_loading: bool = False
_ready: bool = False
_error: str | None = None
_status_message: str = ""
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_loading() -> None:
    """Spawn a daemon thread to load CLAP model and precompute embeddings."""
    global _loading, _error, _status_message
    _loading = True
    _error = None
    _status_message = "Starting model load..."

    thread = threading.Thread(target=_load_wrapper, daemon=True)
    thread.start()


def get_status() -> dict:
    """Return current model status for the /models/status endpoint."""
    cls = _classifier
    cap = _captioner
    return {
        "clap_loaded": cls is not None and cls._model is not None,
        "clapcap_loaded": cap is not None,
        "embeddings_ready": cls is not None and cls.is_ready(),
        "embeddings_count": (len(cls._text_meta) if cls and cls._text_meta else 0),
        "loading": _loading,
        "error": _error,
        "status_message": _status_message,
    }


def get_classifier() -> CLAPClassifier:
    """Return the loaded classifier. Raises RuntimeError if not ready."""
    with _lock:
        if not _ready or _classifier is None:
            raise RuntimeError("Classifier not ready")
        return _classifier


def get_captioner() -> CLAPCaptioner:
    """Lazy-load and return the captioner."""
    global _captioner
    with _lock:
        if _captioner is None:
            _captioner = CLAPCaptioner()
            _captioner.load_model()
            logger.info("CLAPCaptioner lazy-loaded")
    return _captioner


def get_llm_provider() -> OllamaProvider | None:
    """Lazy-construct and return the Ollama-backed LLM rerank provider.

    Returns None when settings disable rerank or the daemon is unreachable.
    Callers treat this as a soft failure and fall back to CLAP + boost.
    """
    from app.services.settings import get_settings

    settings = get_settings()
    global _llm_provider
    with _lock:
        if _llm_provider is not None:
            return _llm_provider
        provider = OllamaProvider(
            model=settings.llm_ollama_model,
            base_url=settings.llm_ollama_base_url,
        )
        if not provider.is_reachable():
            logger.info(
                "Ollama daemon not reachable at %s; rerank disabled",
                settings.llm_ollama_base_url,
            )
            return None
        _llm_provider = provider
        logger.info(
            "OllamaProvider ready (model=%s)", settings.llm_ollama_model
        )
        return _llm_provider


def is_ready() -> bool:
    with _lock:
        return _ready


# ---------------------------------------------------------------------------
# Background loading
# ---------------------------------------------------------------------------


def _load_wrapper() -> None:
    """Wrapper that catches errors and updates status."""
    global _loading, _error, _status_message
    try:
        _load_pipeline()
        _status_message = "Models ready"
    except Exception as e:
        with _lock:
            _error = str(e)
            _status_message = f"Error: {e}"
        logger.exception("Model loading failed")
    finally:
        with _lock:
            _loading = False


def _load_pipeline() -> None:
    """Load CLAP model, build labels, precompute/cache embeddings."""
    global _classifier, _ready, _status_message

    from app.ml.label_builder import (
        build_labels,
        compute_labels_hash,
        flatten_phrases,
    )

    _status_message = "Loading CLAP model..."
    classifier = CLAPClassifier()
    classifier.load_model()

    _status_message = "Building UCS labels..."
    labels = build_labels()
    label_hash = compute_labels_hash(labels)
    phrases, meta = flatten_phrases(labels)

    # Try loading from cache
    cache_dir = paths.get_cache_dir()
    embeddings_file = os.path.join(cache_dir, "text_embeddings.npz")
    os.makedirs(cache_dir, exist_ok=True)
    if classifier.load_embeddings(embeddings_file, label_hash):
        _status_message = "Loaded cached embeddings"
        with _lock:
            _classifier = classifier
            _ready = True
        return

    _status_message = f"Computing text embeddings ({len(phrases)} phrases)..."
    classifier.precompute_embeddings(phrases, meta)
    classifier.save_embeddings(embeddings_file, label_hash)
    with _lock:
        _classifier = classifier
        _ready = True
    _status_message = "Models ready"
