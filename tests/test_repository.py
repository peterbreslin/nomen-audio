"""Tests for the async SQLite repository."""

import pytest
import pytest_asyncio

from app.db.repository import (
    clear_analysis_cache,
    close,
    connect,
    count_files,
    delete_files_by_paths,
    get_all_files,
    get_cached_analysis,
    get_file,
    get_file_by_path,
    insert_file,
    store_cached_analysis,
    update_file,
    upsert_file,
)


@pytest_asyncio.fixture
async def db():
    """In-memory DB for each test."""
    await connect(":memory:")
    yield
    await close()


def _make_record(**overrides) -> dict:
    """Build a minimal file record dict."""
    base = {
        "path": "/tmp/test.wav",
        "filename": "test.wav",
        "directory": "/tmp",
        "status": "unmodified",
        "file_hash": "abc123",
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


# ---------------------------------------------------------------------------
# Insert + Get
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_insert_and_get_by_id(db):
    rec = _make_record()
    file_id = await insert_file(rec)
    assert file_id is not None

    row = await get_file(file_id)
    assert row is not None
    assert row["path"] == "/tmp/test.wav"
    assert row["filename"] == "test.wav"
    assert row["technical"]["sample_rate"] == 44100


@pytest.mark.asyncio
async def test_get_file_not_found(db):
    row = await get_file("nonexistent")
    assert row is None


# ---------------------------------------------------------------------------
# Get by path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_by_path(db):
    rec = _make_record(path="/data/rain.wav")
    await insert_file(rec)

    row = await get_file_by_path("/data/rain.wav")
    assert row is not None
    assert row["filename"] == "test.wav"

    row2 = await get_file_by_path("/data/missing.wav")
    assert row2 is None


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_inserts_new(db):
    rec = _make_record(path="/data/new.wav")
    file_id = await upsert_file(rec)
    assert file_id is not None
    assert await count_files() == 1


@pytest.mark.asyncio
async def test_upsert_updates_existing(db):
    rec = _make_record(path="/data/update.wav", category=None)
    await upsert_file(rec)

    rec["category"] = "AMBIENCE"
    rec["file_hash"] = "new_hash"
    file_id2 = await upsert_file(rec)

    # Same path → same row (upsert replaces)
    assert await count_files() == 1

    row = await get_file(file_id2)
    assert row["category"] == "AMBIENCE"
    assert row["file_hash"] == "new_hash"


# ---------------------------------------------------------------------------
# Delete by paths
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_files_by_paths(db):
    await insert_file(_make_record(path="/a.wav"))
    await insert_file(_make_record(path="/b.wav"))
    await insert_file(_make_record(path="/c.wav"))
    assert await count_files() == 3

    await delete_files_by_paths(["/a.wav", "/b.wav"])
    assert await count_files() == 1

    row = await get_file_by_path("/c.wav")
    assert row is not None


# ---------------------------------------------------------------------------
# Filtered queries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_all_files_no_filter(db):
    await insert_file(_make_record(path="/a.wav"))
    await insert_file(_make_record(path="/b.wav"))
    rows = await get_all_files()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_get_all_files_filter_status(db):
    await insert_file(_make_record(path="/a.wav", status="unmodified"))
    await insert_file(_make_record(path="/b.wav", status="modified"))
    rows = await get_all_files(status="modified")
    assert len(rows) == 1
    assert rows[0]["status"] == "modified"


@pytest.mark.asyncio
async def test_get_all_files_filter_category(db):
    await insert_file(_make_record(path="/a.wav", category="AMBIENCE"))
    await insert_file(_make_record(path="/b.wav", category="DOORS"))
    rows = await get_all_files(category="DOORS")
    assert len(rows) == 1
    assert rows[0]["category"] == "DOORS"


@pytest.mark.asyncio
async def test_get_all_files_search(db):
    await insert_file(
        _make_record(
            path="/a.wav",
            filename="rain_forest.wav",
            fx_name="Rain Forest",
            keywords="rain, jungle",
        )
    )
    await insert_file(
        _make_record(path="/b.wav", filename="door_slam.wav", fx_name="Door Slam")
    )
    rows = await get_all_files(search="rain")
    assert len(rows) == 1
    assert rows[0]["filename"] == "rain_forest.wav"


@pytest.mark.asyncio
async def test_get_all_files_pagination(db):
    for i in range(5):
        await insert_file(_make_record(path=f"/f{i}.wav"))
    rows = await get_all_files(offset=2, limit=2)
    assert len(rows) == 2


# ---------------------------------------------------------------------------
# Count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_count_files_empty(db):
    assert await count_files() == 0


@pytest.mark.asyncio
async def test_count_files_after_inserts(db):
    await insert_file(_make_record(path="/a.wav"))
    await insert_file(_make_record(path="/b.wav"))
    assert await count_files() == 2


# ---------------------------------------------------------------------------
# JSON column deserialization
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_json_columns_roundtrip(db):
    bext = {"description": "Test BEXT", "originator": "JD"}
    info = {"title": "My Sound", "artist": "Jane"}
    rec = _make_record(path="/json.wav", bext=bext, info=info)
    file_id = await insert_file(rec)

    row = await get_file(file_id)
    assert row["bext"]["description"] == "Test BEXT"
    assert row["info"]["title"] == "My Sound"
    assert isinstance(row["technical"], dict)


# ---------------------------------------------------------------------------
# Analysis cache
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_and_get_cached_analysis(db):
    classification = '[{"cat_id": "WATRSurf", "confidence": 0.87}]'
    await store_cached_analysis("hash_abc", classification, None, "2023")
    result = await get_cached_analysis("hash_abc")
    assert result is not None
    assert result["classification"] == classification
    assert result["model_version"] == "2023"


@pytest.mark.asyncio
async def test_get_cached_analysis_miss(db):
    result = await get_cached_analysis("nonexistent_hash")
    assert result is None


@pytest.mark.asyncio
async def test_store_cached_analysis_overwrite(db):
    await store_cached_analysis("hash_1", "[]", None, "2023")
    await store_cached_analysis("hash_1", '[{"new": true}]', "a caption", "2023")
    result = await get_cached_analysis("hash_1")
    assert result["classification"] == '[{"new": true}]'
    assert result["caption"] == "a caption"


@pytest.mark.asyncio
async def test_clear_analysis_cache(db):
    await store_cached_analysis("h1", "[]", None, "2023")
    await store_cached_analysis("h2", "[]", None, "2023")
    await clear_analysis_cache()
    assert await get_cached_analysis("h1") is None
    assert await get_cached_analysis("h2") is None


# ---------------------------------------------------------------------------
# Analysis column on files table
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analysis_column_roundtrip(db):
    rec = _make_record(path="/analysis.wav")
    file_id = await insert_file(rec)

    analysis_data = {
        "classification": [{"cat_id": "WATRSurf", "confidence": 0.87}],
        "caption": None,
        "model_version": "2023",
        "analyzed_at": "2026-02-14T00:00:00Z",
    }
    await update_file(file_id, {"analysis": analysis_data})
    row = await get_file(file_id)
    assert row["analysis"] is not None
    assert row["analysis"]["classification"][0]["cat_id"] == "WATRSurf"
