"""Tests for the CLAP classifier module."""

from unittest.mock import MagicMock

import numpy as np
import pytest

from app.ml.classifier import CLAPClassifier


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def classifier():
    return CLAPClassifier()


def _make_mock_model(similarity_scores: list[float]):
    """Create a mock CLAP model that returns given similarity scores."""
    model = MagicMock()
    model.get_audio_embeddings.return_value = np.array([[0.1, 0.2]])
    # similarity: shape (1, N)
    model.compute_similarity.return_value = np.array([similarity_scores])
    return model


# ---------------------------------------------------------------------------
# is_ready
# ---------------------------------------------------------------------------


def test_not_ready_before_load(classifier):
    assert classifier.is_ready() is False


def test_ready_after_embeddings(classifier):
    # Manually set internal state
    classifier._model = MagicMock()
    classifier._text_embeddings = np.array([[0.1, 0.2]])
    classifier._text_meta = [{"cat_id": "X", "category": "X", "subcategory": "X"}]
    assert classifier.is_ready() is True


# ---------------------------------------------------------------------------
# classify — basic
# ---------------------------------------------------------------------------


def test_classify_returns_sorted_matches(classifier):
    meta = [
        {"cat_id": "WATRSurf", "category": "WATER", "subcategory": "SURF"},
        {"cat_id": "AIRBrst", "category": "AIR", "subcategory": "BURST"},
        {"cat_id": "ROCKImpt", "category": "ROCK", "subcategory": "IMPACT"},
    ]
    scores = [5.0, 1.0, 3.0]
    model = _make_mock_model(scores)
    classifier._model = model
    classifier._text_embeddings = np.array([[0.1]] * 3)
    classifier._text_meta = meta

    results = classifier.classify("/fake/path.wav", top_n=5)
    assert len(results) == 3
    assert results[0].cat_id == "WATRSurf"
    assert results[1].cat_id == "ROCKImpt"
    assert results[2].cat_id == "AIRBrst"
    # Softmax: confidences in [0, 1] and descending
    assert 0.0 < results[0].confidence <= 1.0
    assert results[0].confidence > results[1].confidence > results[2].confidence


# ---------------------------------------------------------------------------
# classify — grouping by CatID
# ---------------------------------------------------------------------------


def test_classify_groups_by_catid(classifier):
    # Two phrases for same CatID, take max logit
    meta = [
        {"cat_id": "WATRSurf", "category": "WATER", "subcategory": "SURF"},
        {"cat_id": "WATRSurf", "category": "WATER", "subcategory": "SURF"},
        {"cat_id": "AIRBrst", "category": "AIR", "subcategory": "BURST"},
    ]
    scores = [2.0, 5.0, 1.0]  # second WATRSurf phrase scores higher
    model = _make_mock_model(scores)
    classifier._model = model
    classifier._text_embeddings = np.array([[0.1]] * 3)
    classifier._text_meta = meta

    results = classifier.classify("/fake/path.wav", top_n=5)
    assert len(results) == 2  # grouped
    assert results[0].cat_id == "WATRSurf"
    assert results[0].confidence > results[1].confidence


# ---------------------------------------------------------------------------
# classify — top_n
# ---------------------------------------------------------------------------


def test_classify_top_n(classifier):
    meta = [
        {"cat_id": f"CAT{i}", "category": "X", "subcategory": "Y"} for i in range(10)
    ]
    scores = [0.1 * i for i in range(10)]
    model = _make_mock_model(scores)
    classifier._model = model
    classifier._text_embeddings = np.array([[0.1]] * 10)
    classifier._text_meta = meta

    results = classifier.classify("/fake/path.wav", top_n=3)
    assert len(results) == 3


# ---------------------------------------------------------------------------
# save/load embeddings
# ---------------------------------------------------------------------------


def test_save_load_embeddings(classifier, tmp_path):
    embeddings = np.random.randn(10, 128).astype(np.float32)
    meta = [
        {"cat_id": f"CAT{i}", "category": "X", "subcategory": "Y"} for i in range(10)
    ]
    classifier._text_embeddings = embeddings
    classifier._text_meta = meta

    path = tmp_path / "emb.npz"
    label_hash = "abc123"
    classifier.save_embeddings(str(path), label_hash)
    assert path.exists()

    # Load into fresh classifier
    c2 = CLAPClassifier()
    loaded = c2.load_embeddings(str(path), label_hash)
    assert loaded is True
    # load_embeddings converts to torch tensor; compare as numpy
    assert np.allclose(c2._text_embeddings.numpy(), embeddings)
    assert c2._text_meta == meta


def test_load_embeddings_hash_mismatch(classifier, tmp_path):
    embeddings = np.random.randn(5, 64).astype(np.float32)
    meta = [{"cat_id": f"C{i}", "category": "X", "subcategory": "Y"} for i in range(5)]
    classifier._text_embeddings = embeddings
    classifier._text_meta = meta

    path = tmp_path / "emb.npz"
    classifier.save_embeddings(str(path), "hash_v1")

    c2 = CLAPClassifier()
    loaded = c2.load_embeddings(str(path), "hash_v2")
    assert loaded is False
    assert c2._text_embeddings is None
