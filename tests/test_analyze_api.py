"""Tests for analysis API endpoints and filename re-ranking (D056)."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.models import ClassificationMatch
from app.routers.analysis import apply_filename_boost, _build_prefill_updates
from app.ucs.filename import FuzzyMatch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import repository
from app.db.repository import insert_file
from app.main import app


@pytest_asyncio.fixture
async def client():
    await repository.connect(":memory:")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    await repository.close()


def _make_record(**overrides) -> dict:
    base = {
        "path": "C:/data/test.wav",
        "filename": "test.wav",
        "directory": "C:/data",
        "status": "unmodified",
        "file_hash": "hash_abc",
        "category": None,
        "subcategory": None,
        "cat_id": None,
        "category_full": None,
        "user_category": None,
        "fx_name": None,
        "description": None,
        "keywords": None,
        "notes": None,
        "designer": None,
        "library": None,
        "project": None,
        "microphone": None,
        "mic_perspective": None,
        "rec_medium": None,
        "release_date": None,
        "rating": None,
        "is_designed": None,
        "technical": {
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": 1,
            "duration_seconds": 1.0,
            "frame_count": 44100,
            "audio_format": "PCM",
            "file_size_bytes": 88244,
        },
        "bext": None,
        "info": None,
    }
    base.update(overrides)
    return base


def _mock_classification():
    return [
        ClassificationMatch(
            cat_id="WATRSurf",
            category="WATER",
            subcategory="SURF",
            category_full="WATER-SURF",
            confidence=0.87,
        ),
    ]


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — 503 when not ready
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_503_when_not_ready(client):
    file_id = await insert_file(_make_record())
    with patch("app.routers.analysis.model_manager.is_ready", return_value=False):
        resp = await client.post(f"/files/{file_id}/analyze", json={"tiers": [1]})
    assert resp.status_code == 503
    assert "Models still loading" in resp.json()["error"]


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — 404 unknown file
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_404_unknown_file(client):
    with patch("app.routers.analysis.model_manager.is_ready", return_value=True):
        resp = await client.post("/files/nonexistent/analyze", json={"tiers": [1]})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — happy path Tier 1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_tier1_happy_path(client):
    file_id = await insert_file(_make_record())
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = _mock_classification()

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch("app.routers.analysis.get_cached_analysis", return_value=None),
        patch("app.routers.analysis.store_cached_analysis"),
    ):
        resp = await client.post(f"/files/{file_id}/analyze", json={"tiers": [1]})

    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis"] is not None
    assert data["analysis"]["classification"][0]["cat_id"] == "WATRSurf"
    assert data["suggestions"] is not None
    assert data["suggestions"]["category"]["value"] == "WATER"


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — cache hit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_cache_hit_skips_inference(client):
    file_id = await insert_file(_make_record())
    cached = {
        "classification": json.dumps(
            [
                {
                    "cat_id": "WATRSurf",
                    "category": "WATER",
                    "subcategory": "SURF",
                    "category_full": "WATER-SURF",
                    "confidence": 0.87,
                }
            ]
        ),
        "caption": None,
        "model_version": "2023",
    }
    mock_classifier = MagicMock()

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch("app.routers.analysis.get_cached_analysis", return_value=cached),
    ):
        resp = await client.post(f"/files/{file_id}/analyze", json={"tiers": [1]})

    assert resp.status_code == 200
    # Classifier should NOT have been called
    mock_classifier.classify.assert_not_called()
    data = resp.json()
    assert data["analysis"]["classification"][0]["cat_id"] == "WATRSurf"


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — force bypasses cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_force_bypasses_cache(client):
    file_id = await insert_file(_make_record())
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = _mock_classification()

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch("app.routers.analysis.get_cached_analysis") as mock_cache,
        patch("app.routers.analysis.store_cached_analysis"),
    ):
        resp = await client.post(
            f"/files/{file_id}/analyze", json={"tiers": [1], "force": True}
        )

    assert resp.status_code == 200
    # Cache should NOT have been checked
    mock_cache.assert_not_called()
    # Classifier SHOULD have been called
    mock_classifier.classify.assert_called_once()


# ---------------------------------------------------------------------------
# POST /files/{id}/analyze — Tier 2 with captioner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_tier2_with_caption(client):
    file_id = await insert_file(_make_record())
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = _mock_classification()
    mock_captioner = MagicMock()
    mock_captioner.caption.return_value = "Ocean waves crashing on a sandy beach."

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch(
            "app.routers.analysis.model_manager.get_captioner",
            return_value=mock_captioner,
        ),
        patch("app.routers.analysis.get_cached_analysis", return_value=None),
        patch("app.routers.analysis.store_cached_analysis"),
    ):
        resp = await client.post(f"/files/{file_id}/analyze", json={"tiers": [1, 2]})

    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis"]["caption"] == "Ocean waves crashing on a sandy beach."
    assert data["suggestions"]["description"] is not None
    assert data["suggestions"]["fx_name"] is not None


# ---------------------------------------------------------------------------
# POST /files/analyze-batch — SSE streaming
# ---------------------------------------------------------------------------


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current_data = line[len("data:") :].strip()
        elif line == "" and current_event and current_data:
            events.append({"event": current_event, "data": json.loads(current_data)})
            current_event = None
            current_data = None
    return events


@pytest.mark.asyncio
async def test_batch_analyze_sse_events(client):
    fid1 = await insert_file(_make_record(path="C:/data/a.wav", filename="a.wav"))
    fid2 = await insert_file(_make_record(path="C:/data/b.wav", filename="b.wav"))

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = _mock_classification()

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch("app.routers.analysis.get_cached_analysis", return_value=None),
        patch("app.routers.analysis.store_cached_analysis"),
    ):
        resp = await client.post(
            "/files/analyze-batch",
            json={"file_ids": [fid1, fid2], "tiers": [1]},
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)

    # Should have: progress, result, progress, result, complete
    event_types = [e["event"] for e in events]
    assert event_types.count("progress") == 2
    assert event_types.count("result") == 2
    assert event_types.count("complete") == 1

    # Check complete event
    complete = [e for e in events if e["event"] == "complete"][0]
    assert complete["data"]["analyzed_count"] == 2
    assert complete["data"]["failed_count"] == 0


@pytest.mark.asyncio
async def test_batch_analyze_503_when_not_ready(client):
    with patch("app.routers.analysis.model_manager.is_ready", return_value=False):
        resp = await client.post(
            "/files/analyze-batch", json={"file_ids": [], "tiers": [1]}
        )
    assert resp.status_code == 503


@pytest.mark.asyncio
async def test_batch_analyze_empty_ids_analyzes_all(client):
    await insert_file(_make_record(path="C:/data/c.wav", filename="c.wav"))
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = _mock_classification()

    with (
        patch("app.routers.analysis.model_manager.is_ready", return_value=True),
        patch(
            "app.routers.analysis.model_manager.get_classifier",
            return_value=mock_classifier,
        ),
        patch("app.routers.analysis.get_cached_analysis", return_value=None),
        patch("app.routers.analysis.store_cached_analysis"),
    ):
        resp = await client.post(
            "/files/analyze-batch", json={"file_ids": [], "tiers": [1]}
        )

    assert resp.status_code == 200
    events = _parse_sse_events(resp.text)
    result_events = [e for e in events if e["event"] == "result"]
    assert len(result_events) == 1


# ---------------------------------------------------------------------------
# apply_filename_boost (D056) — unit tests
# ---------------------------------------------------------------------------


def _make_matches(n: int) -> list[ClassificationMatch]:
    """Create n classification matches with descending confidence."""
    return [
        ClassificationMatch(
            cat_id=f"CAT{i}",
            category="X",
            subcategory="Y",
            category_full="X-Y",
            confidence=round(1.0 / (i + 1), 6),
        )
        for i in range(n)
    ]


def test_filename_boost_reranks():
    """Keyword matches should boost CatIDs above their CLAP-only ranking."""
    matches = _make_matches(10)
    # CAT5 has low CLAP confidence (0.166667) — keyword boost should lift it
    mock_fuzzy = [
        FuzzyMatch(
            cat_id="CAT5",
            category="X",
            subcategory="Y",
            score=3,
            matched_terms=["a", "b", "c"],
        ),
        FuzzyMatch(
            cat_id="CAT8",
            category="X",
            subcategory="Y",
            score=2,
            matched_terms=["a", "b"],
        ),
    ]
    with patch("app.routers.analysis.fuzzy_match", return_value=mock_fuzzy):
        result = apply_filename_boost(matches, "some_descriptive_file.wav", top_n=5)

    assert result[0].cat_id == "CAT5"
    # Blended confidences sum to ~1.0, #1 has highest
    total = sum(r.confidence for r in result)
    assert total == pytest.approx(1.0, abs=0.01)
    assert result[0].confidence > result[1].confidence


def test_filename_boost_no_filename_returns_clap_order():
    """Without filename, returns top_n in CLAP order."""
    matches = _make_matches(10)
    result = apply_filename_boost(matches, None, top_n=3)
    assert len(result) == 3
    assert result[0].cat_id == "CAT0"
    assert result[1].cat_id == "CAT1"
    assert result[2].cat_id == "CAT2"


def test_filename_boost_below_threshold_no_rerank():
    """Single-token match (score=1) should not trigger boost."""
    matches = _make_matches(5)
    mock_fuzzy = [
        FuzzyMatch(
            cat_id="CAT3", category="X", subcategory="Y", score=1, matched_terms=["x"]
        ),
    ]
    with patch("app.routers.analysis.fuzzy_match", return_value=mock_fuzzy):
        result = apply_filename_boost(matches, "generic.wav", top_n=3)

    # CLAP order preserved
    assert result[0].cat_id == "CAT0"


def test_renormalize_no_keyword():
    """No-keyword path renormalizes confidences to sum to ~1.0."""
    matches = _make_matches(10)
    result = apply_filename_boost(matches, None, top_n=5)
    total = sum(r.confidence for r in result)
    assert total == pytest.approx(1.0, abs=0.01)
    # Order preserved
    assert result[0].cat_id == "CAT0"


def test_blend_confidence_boosts_keyword_match():
    """Keyword-boosted item gets highest blended confidence."""
    # Realistic softmax-like confidences (small, close together)
    matches = [
        ClassificationMatch(
            cat_id=f"CAT{i}",
            category="X",
            subcategory="Y",
            category_full="X-Y",
            confidence=round(0.05 - i * 0.003, 6),
        )
        for i in range(10)
    ]
    mock_fuzzy = [
        FuzzyMatch(
            cat_id="CAT7",
            category="X",
            subcategory="Y",
            score=5,
            matched_terms=["a", "b", "c", "d", "e"],
        ),
    ]
    with patch("app.routers.analysis.fuzzy_match", return_value=mock_fuzzy):
        result = apply_filename_boost(matches, "keyword_file.wav", top_n=5)

    assert result[0].cat_id == "CAT7"
    assert result[0].confidence > result[1].confidence
    total = sum(r.confidence for r in result)
    assert total == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# _build_prefill_updates (D064) — unit tests
# ---------------------------------------------------------------------------


def test_prefill_creator_id_when_empty():
    """Creator ID from settings fills empty creator_id field."""
    row = {"creator_id": None, "source_id": None}
    settings = SimpleNamespace(creator_id="PB01", source_id="SRC01")
    updates = _build_prefill_updates(row, settings)
    assert updates == {"creator_id": "PB01", "source_id": "SRC01"}


def test_prefill_skips_when_creator_id_set():
    """Don't overwrite existing creator_id or source_id."""
    row = {"creator_id": "Existing", "source_id": "Existing"}
    settings = SimpleNamespace(creator_id="PB01", source_id="SRC01")
    updates = _build_prefill_updates(row, settings)
    assert updates == {}


def test_prefill_empty_when_no_settings():
    """No pre-fill when settings fields are empty."""
    row = {"creator_id": None, "source_id": None}
    settings = SimpleNamespace(creator_id="", source_id="")
    updates = _build_prefill_updates(row, settings)
    assert updates == {}


def test_prefill_partial_when_one_set():
    """Only fills empty fields, preserves existing ones."""
    row = {"creator_id": "Existing", "source_id": None}
    settings = SimpleNamespace(creator_id="PB01", source_id="SRC01")
    updates = _build_prefill_updates(row, settings)
    assert updates == {"source_id": "SRC01"}


# ---------------------------------------------------------------------------
# Result ordering — confidence sort (D056 fix)
# ---------------------------------------------------------------------------


def test_results_sorted_by_confidence():
    """After keyword boost, results are sorted by descending confidence."""
    # Create matches where keyword boost will reorder items:
    # CAT0 has highest CLAP confidence, CAT7 gets keyword boost
    matches = [
        ClassificationMatch(
            cat_id=f"CAT{i}",
            category="X",
            subcategory="Y",
            category_full="X-Y",
            confidence=round(0.05 - i * 0.003, 6),
        )
        for i in range(10)
    ]
    mock_fuzzy = [
        FuzzyMatch(
            cat_id="CAT7",
            category="X",
            subcategory="Y",
            score=5,
            matched_terms=["a", "b", "c", "d", "e"],
        ),
    ]
    with patch("app.routers.analysis.fuzzy_match", return_value=mock_fuzzy):
        result = apply_filename_boost(matches, "keyword_file.wav", top_n=5)

    # Verify descending confidence order
    for i in range(len(result) - 1):
        assert result[i].confidence >= result[i + 1].confidence, (
            f"result[{i}] ({result[i].confidence}) < result[{i + 1}] ({result[i + 1].confidence})"
        )


def test_renormalize_sorted_by_confidence():
    """No-keyword path also returns results sorted by descending confidence."""
    matches = _make_matches(10)
    result = apply_filename_boost(matches, None, top_n=5)
    for i in range(len(result) - 1):
        assert result[i].confidence >= result[i + 1].confidence
