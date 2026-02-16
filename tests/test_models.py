"""Tests for Pydantic models."""

import json

import pytest
from pydantic import ValidationError

from app.models import (
    AnalysisResult,
    AnalyzeRequest,
    BatchAnalyzeRequest,
    BextInfo,
    ClassificationMatch,
    FileRecord,
    ImportRequest,
    ImportResponse,
    RiffInfo,
    Suggestion,
    SuggestionsResult,
    TechnicalInfo,
)


# ---------------------------------------------------------------------------
# TechnicalInfo
# ---------------------------------------------------------------------------


def test_technical_info_valid():
    t = TechnicalInfo(
        sample_rate=48000,
        bit_depth=24,
        channels=1,
        duration_seconds=2.34,
        frame_count=112320,
        audio_format="PCM",
        file_size_bytes=538624,
    )
    assert t.sample_rate == 48000
    assert t.audio_format == "PCM"


# ---------------------------------------------------------------------------
# BextInfo / RiffInfo
# ---------------------------------------------------------------------------


def test_bext_info_all_none():
    b = BextInfo()
    assert b.description is None
    assert b.time_reference is None


def test_riff_info_all_none():
    r = RiffInfo()
    assert r.title is None


# ---------------------------------------------------------------------------
# FileRecord — minimal valid
# ---------------------------------------------------------------------------

MINIMAL_TECHNICAL = {
    "sample_rate": 44100,
    "bit_depth": 16,
    "channels": 1,
    "duration_seconds": 1.0,
    "frame_count": 44100,
    "audio_format": "PCM",
    "file_size_bytes": 88244,
}


def test_file_record_minimal():
    rec = FileRecord(
        id="abc-123",
        path="/tmp/test.wav",
        filename="test.wav",
        directory="/tmp",
        technical=MINIMAL_TECHNICAL,
    )
    assert rec.status == "unmodified"
    assert rec.changed_fields == []
    assert rec.category is None
    assert rec.rename_on_save is True
    assert rec.analysis is None
    assert rec.suggestions is None


# ---------------------------------------------------------------------------
# FileRecord — invalid status
# ---------------------------------------------------------------------------


def test_file_record_invalid_status():
    with pytest.raises(ValidationError):
        FileRecord(
            id="abc",
            path="/tmp/test.wav",
            filename="test.wav",
            directory="/tmp",
            technical=MINIMAL_TECHNICAL,
            status="INVALID",
        )


# ---------------------------------------------------------------------------
# FileRecord — JSON round-trip
# ---------------------------------------------------------------------------


def test_file_record_json_roundtrip():
    rec = FileRecord(
        id="abc-123",
        path="/tmp/test.wav",
        filename="test.wav",
        directory="/tmp",
        technical=MINIMAL_TECHNICAL,
        category="AMBIENCE",
        bext=BextInfo(description="Test"),
        info=RiffInfo(title="My Sound"),
    )
    data = json.loads(rec.model_dump_json())
    rec2 = FileRecord(**data)
    assert rec2.id == rec.id
    assert rec2.category == "AMBIENCE"
    assert rec2.bext.description == "Test"
    assert rec2.info.title == "My Sound"


# ---------------------------------------------------------------------------
# ImportRequest / ImportResponse
# ---------------------------------------------------------------------------


def test_import_request_defaults():
    req = ImportRequest(directory="/tmp/sounds")
    assert req.recursive is True


def test_import_response():
    resp = ImportResponse(
        files=[],
        count=0,
        skipped=0,
        skipped_paths=[],
        import_time_ms=42,
    )
    assert resp.count == 0
    assert resp.import_time_ms == 42


# ---------------------------------------------------------------------------
# ClassificationMatch
# ---------------------------------------------------------------------------


def test_classification_match_valid():
    m = ClassificationMatch(
        cat_id="WATRSurf",
        category="WATER",
        subcategory="SURF",
        category_full="WATER-SURF",
        confidence=0.87,
    )
    assert m.cat_id == "WATRSurf"
    assert m.confidence == 0.87


def test_classification_match_invalid_confidence():
    with pytest.raises(ValidationError):
        ClassificationMatch(
            cat_id="X",
            category="X",
            subcategory="X",
            category_full="X-X",
            confidence=1.5,
        )


# ---------------------------------------------------------------------------
# AnalysisResult
# ---------------------------------------------------------------------------


def test_analysis_result_construction():
    match = ClassificationMatch(
        cat_id="WATRSurf",
        category="WATER",
        subcategory="SURF",
        category_full="WATER-SURF",
        confidence=0.87,
    )
    result = AnalysisResult(
        classification=[match],
        caption=None,
        model_version="2023",
        analyzed_at="2026-02-14T00:00:00Z",
    )
    assert len(result.classification) == 1
    assert result.caption is None
    assert result.model_version == "2023"


def test_analysis_result_json_roundtrip():
    match = ClassificationMatch(
        cat_id="WATRSurf",
        category="WATER",
        subcategory="SURF",
        category_full="WATER-SURF",
        confidence=0.87,
    )
    result = AnalysisResult(
        classification=[match],
        caption="ocean waves",
        model_version="2023",
        analyzed_at="2026-02-14T00:00:00Z",
    )
    data = json.loads(result.model_dump_json())
    result2 = AnalysisResult(**data)
    assert result2.classification[0].cat_id == "WATRSurf"
    assert result2.caption == "ocean waves"


# ---------------------------------------------------------------------------
# Suggestion / SuggestionsResult
# ---------------------------------------------------------------------------


def test_suggestion_valid():
    s = Suggestion(value="WATER", source="clap", confidence=0.87)
    assert s.value == "WATER"
    assert s.source == "clap"


def test_suggestion_invalid_source():
    with pytest.raises(ValidationError):
        Suggestion(value="X", source="invalid_source", confidence=0.5)


def test_suggestions_result_partial():
    sr = SuggestionsResult(
        category=Suggestion(value="WATER", source="clap", confidence=0.87),
    )
    assert sr.category is not None
    assert sr.subcategory is None
    assert sr.fx_name is None


# ---------------------------------------------------------------------------
# AnalyzeRequest / BatchAnalyzeRequest
# ---------------------------------------------------------------------------


def test_analyze_request_defaults():
    req = AnalyzeRequest()
    assert req.tiers == [1]
    assert req.force is False


def test_batch_analyze_request_defaults():
    req = BatchAnalyzeRequest()
    assert req.file_ids == []
    assert req.tiers == [1]


# ---------------------------------------------------------------------------
# FileRecord with analysis
# ---------------------------------------------------------------------------


def test_file_record_with_analysis():
    match = ClassificationMatch(
        cat_id="WATRSurf",
        category="WATER",
        subcategory="SURF",
        category_full="WATER-SURF",
        confidence=0.87,
    )
    analysis = AnalysisResult(
        classification=[match],
        caption=None,
        model_version="2023",
        analyzed_at="2026-02-14T00:00:00Z",
    )
    suggestions = SuggestionsResult(
        category=Suggestion(value="WATER", source="clap", confidence=0.87),
    )
    rec = FileRecord(
        id="abc-123",
        path="/tmp/test.wav",
        filename="test.wav",
        directory="/tmp",
        technical=MINIMAL_TECHNICAL,
        analysis=analysis,
        suggestions=suggestions,
    )
    assert rec.analysis.classification[0].cat_id == "WATRSurf"
    assert rec.suggestions.category.value == "WATER"

    # JSON round-trip
    data = json.loads(rec.model_dump_json())
    rec2 = FileRecord(**data)
    assert rec2.analysis.model_version == "2023"
    assert rec2.suggestions.category.confidence == 0.87
