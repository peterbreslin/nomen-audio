"""Tests for Tier 1/2 suggestion generator."""

from unittest.mock import patch

import pytest

from app.models import AnalysisResult, ClassificationMatch, FileRecord, TechnicalInfo
from app.ucs.engine import is_loaded, load_ucs

UCS_FULL = "data/UCS/UCS v8.2.1 Full List.xlsx"
UCS_TOP = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load_ucs():
    if not is_loaded():
        load_ucs(UCS_FULL, UCS_TOP)


def _make_matches() -> list[ClassificationMatch]:
    return [
        ClassificationMatch(
            cat_id="WATRSurf",
            category="WATER",
            subcategory="SURF",
            category_full="WATER-SURF",
            confidence=0.87,
        ),
        ClassificationMatch(
            cat_id="AIRBrst",
            category="AIR",
            subcategory="BURST",
            category_full="AIR-BURST",
            confidence=0.45,
        ),
    ]


# ---------------------------------------------------------------------------
# Tier 1 suggestions
# ---------------------------------------------------------------------------


def test_tier1_category_suggestion():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.category is not None
    assert result.category.value == "WATER"
    assert result.category.source == "clap"
    assert result.category.confidence == pytest.approx(0.87, abs=0.01)


def test_tier1_subcategory_suggestion():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.subcategory.value == "SURF"


def test_tier1_cat_id_suggestion():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.cat_id.value == "WATRSurf"


def test_tier1_category_full_suggestion():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.category_full.value == "WATER-SURF"


def test_tier1_keywords_from_synonyms():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.keywords is not None
    assert result.keywords.source == "derived"


def test_tier1_suggested_filename():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.suggested_filename is not None
    assert result.suggested_filename.source == "generated"
    assert "WATRSurf" in result.suggested_filename.value


def test_tier1_filename_includes_creator_id():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(
        _make_matches(), creator_id="JD", source_id="SRC"
    )
    assert result.suggested_filename is not None
    assert "JD" in result.suggested_filename.value
    assert "SRC" in result.suggested_filename.value


def test_tier1_no_fx_name():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.fx_name is None


def test_tier1_no_description():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions(_make_matches())
    assert result.description is None


def test_tier1_empty_classification():
    from app.ml.suggestions import generate_tier1_suggestions

    result = generate_tier1_suggestions([])
    assert result.category is None


# ---------------------------------------------------------------------------
# Tier 2 enrichment
# ---------------------------------------------------------------------------


def test_enrich_with_caption_adds_description():
    from app.ml.suggestions import enrich_with_caption, generate_tier1_suggestions

    base = generate_tier1_suggestions(_make_matches())
    enriched = enrich_with_caption(base, "Ocean waves crashing on a sandy beach.")
    assert enriched.description is not None
    assert enriched.description.source == "clapcap"
    assert enriched.description.confidence is None
    assert "Ocean waves" in enriched.description.value


def test_enrich_with_caption_adds_fx_name():
    from app.ml.suggestions import enrich_with_caption, generate_tier1_suggestions

    base = generate_tier1_suggestions(_make_matches())
    enriched = enrich_with_caption(base, "Ocean waves crashing on a sandy beach.")
    assert enriched.fx_name is not None
    assert enriched.fx_name.source == "clapcap"
    assert enriched.fx_name.confidence is None


def test_enrich_regenerates_filename_with_fx_name():
    """After tier 2 adds fx_name, suggested_filename must include it (not 'Untitled')."""
    from app.ml.suggestions import enrich_with_caption, generate_tier1_suggestions

    base = generate_tier1_suggestions(_make_matches())
    assert "Untitled" in base.suggested_filename.value  # tier 1 has no fx_name

    enriched = enrich_with_caption(base, "Ocean waves crashing on a sandy beach.")
    assert enriched.suggested_filename is not None
    assert "Untitled" not in enriched.suggested_filename.value
    assert enriched.fx_name.value in enriched.suggested_filename.value


# ---------------------------------------------------------------------------
# hydrate_suggestions
# ---------------------------------------------------------------------------


def _make_file_record(*, analysis=None) -> FileRecord:
    return FileRecord(
        id="test-id",
        path="C:/data/test.wav",
        filename="test.wav",
        directory="C:/data",
        technical=TechnicalInfo(
            sample_rate=44100,
            bit_depth=16,
            channels=1,
            duration_seconds=1.0,
            frame_count=44100,
            audio_format="PCM",
            file_size_bytes=88244,
        ),
        analysis=analysis,
    )


def test_hydrate_suggestions_from_stored_analysis():
    from app.ml.suggestions import hydrate_suggestions
    from types import SimpleNamespace

    analysis = AnalysisResult(
        classification=_make_matches(),
        caption="Ocean waves crashing on a sandy beach.",
        model_version="2023",
        analyzed_at="2025-01-01T00:00:00Z",
    )
    record = _make_file_record(analysis=analysis)
    assert record.suggestions is None

    with patch(
        "app.ml.suggestions.get_settings",
        return_value=SimpleNamespace(creator_id="JD", source_id="SRC"),
    ):
        hydrated = hydrate_suggestions(record)

    assert hydrated.suggestions is not None
    assert hydrated.suggestions.category.value == "WATER"
    assert hydrated.suggestions.cat_id.value == "WATRSurf"
    assert hydrated.suggestions.description is not None
    assert hydrated.suggestions.fx_name is not None


def test_hydrate_suggestions_no_analysis_returns_unchanged():
    from app.ml.suggestions import hydrate_suggestions

    record = _make_file_record(analysis=None)
    result = hydrate_suggestions(record)
    assert result.suggestions is None
