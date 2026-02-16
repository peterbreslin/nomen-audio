"""Tests for the /files API endpoints."""

import json
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import repository
from app.db.repository import store_cached_analysis
from app.main import app
from app.metadata.reader import compute_file_hash
from app.ucs.engine import is_loaded, load_ucs
from conftest import IXML_WITH_USER, build_bext_data, write_wav

UCS_FULL = "data/UCS/UCS v8.2.1 Full List.xlsx"
UCS_TOP = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load_ucs():
    if not is_loaded():
        load_ucs(UCS_FULL, UCS_TOP)


@pytest.fixture
def wav_dir(tmp_path):
    """Directory with 3 synthetic WAV files."""
    write_wav(tmp_path, "one.wav", ixml_xml=IXML_WITH_USER)
    write_wav(tmp_path, "two.wav", bext_data=build_bext_data(description="Rain"))
    write_wav(tmp_path, "three.wav")
    return tmp_path


@pytest_asyncio.fixture
async def client():
    """Async test client with in-memory DB."""
    await repository.connect(":memory:")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await repository.close()


# ---------------------------------------------------------------------------
# POST /files/import
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_import_files(wav_dir, client):
    resp = await client.post(
        "/files/import",
        json={"directory": str(wav_dir), "recursive": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert data["skipped"] == 0
    assert len(data["files"]) == 3
    assert data["import_time_ms"] >= 0


@pytest.mark.asyncio
async def test_import_recursive(tmp_path, client):
    """Recursive flag finds WAVs in subdirectories."""
    sub = tmp_path / "sub"
    sub.mkdir()
    write_wav(tmp_path, "top.wav")
    write_wav(sub, "nested.wav")

    resp = await client.post(
        "/files/import",
        json={"directory": str(tmp_path), "recursive": True},
    )
    assert resp.json()["count"] == 2


@pytest.mark.asyncio
async def test_import_bad_directory(client):
    resp = await client.post(
        "/files/import",
        json={"directory": "/nonexistent/path"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_import_cache_hit(wav_dir, client):
    """Re-importing unchanged files uses cache (no re-read)."""
    resp1 = await client.post(
        "/files/import",
        json={"directory": str(wav_dir)},
    )
    resp2 = await client.post(
        "/files/import",
        json={"directory": str(wav_dir)},
    )
    assert resp1.json()["count"] == 3
    assert resp2.json()["count"] == 3


@pytest.mark.asyncio
async def test_import_skips_corrupted(tmp_path, client):
    """Corrupted WAV file is skipped, not raising."""
    write_wav(tmp_path, "good.wav")
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"NOT A WAV")

    resp = await client.post(
        "/files/import",
        json={"directory": str(tmp_path)},
    )
    data = resp.json()
    assert data["count"] == 1
    assert data["skipped"] == 1
    assert len(data["skipped_paths"]) == 1


@pytest.mark.asyncio
async def test_import_stale_removal(wav_dir, client):
    """Files deleted from disk are removed from DB on re-import."""
    resp1 = await client.post(
        "/files/import",
        json={"directory": str(wav_dir)},
    )
    assert resp1.json()["count"] == 3

    # Delete one file
    os.remove(wav_dir / "one.wav")

    resp2 = await client.post(
        "/files/import",
        json={"directory": str(wav_dir)},
    )
    assert resp2.json()["count"] == 2


@pytest.mark.asyncio
async def test_import_prepopulates_analysis_from_cache(tmp_path, client):
    """Import pre-populates analysis + suggestions when analysis_cache has results."""
    wav_path = write_wav(tmp_path, "test_cached.wav")
    file_hash = compute_file_hash(str(wav_path))

    # Seed analysis_cache with classification data
    classification = [
        {
            "cat_id": "WATRSurf",
            "category": "WATER",
            "subcategory": "SURF",
            "category_full": "WATER-SURF",
            "confidence": 0.87,
        }
    ]
    await store_cached_analysis(file_hash, json.dumps(classification), None, "2023")

    resp = await client.post("/files/import", json={"directory": str(tmp_path)})
    assert resp.status_code == 200
    files = resp.json()["files"]
    cached_file = next(f for f in files if f["filename"] == "test_cached.wav")

    # Analysis should be pre-populated from cache
    assert cached_file["analysis"] is not None
    cls = cached_file["analysis"]["classification"]
    assert len(cls) >= 1
    assert cls[0]["cat_id"] == "WATRSurf"

    # Suggestions should be hydrated from the analysis
    assert cached_file["suggestions"] is not None
    assert cached_file["suggestions"]["category"]["value"] == "WATER"


# ---------------------------------------------------------------------------
# GET /files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_files_after_import(wav_dir, client):
    """GET /files returns all imported records."""
    await client.post("/files/import", json={"directory": str(wav_dir)})
    resp = await client.get("/files")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert len(data["files"]) == 3


@pytest.mark.asyncio
async def test_get_files_filter_category(wav_dir, client):
    """Filter by category returns only matching records."""
    await client.post("/files/import", json={"directory": str(wav_dir)})
    # one.wav has IXML_WITH_USER → category=AMBIENCE
    resp = await client.get("/files", params={"category": "AMBIENCE"})
    data = resp.json()
    assert data["count"] == 1
    assert data["files"][0]["category"] == "AMBIENCE"


# ---------------------------------------------------------------------------
# GET /files/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_file_by_id(wav_dir, client):
    """GET /files/{id} returns a single record."""
    import_resp = await client.post("/files/import", json={"directory": str(wav_dir)})
    file_id = import_resp.json()["files"][0]["id"]

    resp = await client.get(f"/files/{file_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == file_id


@pytest.mark.asyncio
async def test_get_file_not_found(client):
    """GET /files/{id} returns 404 for unknown ID."""
    resp = await client.get("/files/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /files/{id}/audio
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_audio(wav_dir, client):
    """GET /files/{id}/audio returns valid WAV bytes."""
    import_resp = await client.post("/files/import", json={"directory": str(wav_dir)})
    file_id = import_resp.json()["files"][0]["id"]

    resp = await client.get(f"/files/{file_id}/audio")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    # WAV files start with RIFF header
    assert resp.content[:4] == b"RIFF"


@pytest.mark.asyncio
async def test_get_audio_not_found(client):
    """GET /files/{id}/audio returns 404 for unknown ID."""
    resp = await client.get("/files/nonexistent-id/audio")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PUT /files/{id}/metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_metadata_regenerates_filename(wav_dir, client):
    """Editing fx_name regenerates suggested_filename with the new value."""
    import_resp = await client.post("/files/import", json={"directory": str(wav_dir)})
    file_id = import_resp.json()["files"][0]["id"]

    # Set cat_id + fx_name: should generate suggested_filename
    resp = await client.put(
        f"/files/{file_id}/metadata",
        json={"cat_id": "THUN", "fx_name": "Rolling Crack"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggested_filename"] is not None
    assert "Rolling Crack" in data["suggested_filename"]
    assert "Untitled" not in data["suggested_filename"]

    # Now update just fx_name: filename should update accordingly
    resp2 = await client.put(
        f"/files/{file_id}/metadata",
        json={"fx_name": "Deep Rumble"},
    )
    data2 = resp2.json()
    assert "Deep Rumble" in data2["suggested_filename"]
    assert "Rolling Crack" not in data2["suggested_filename"]


@pytest.mark.asyncio
async def test_update_metadata_no_regen_without_catid(wav_dir, client):
    """Editing fx_name without cat_id does not generate suggested_filename."""
    import_resp = await client.post("/files/import", json={"directory": str(wav_dir)})
    # three.wav has no iXML → no cat_id
    files = import_resp.json()["files"]
    bare_file = next(f for f in files if f["filename"] == "three.wav")

    resp = await client.put(
        f"/files/{bare_file['id']}/metadata",
        json={"fx_name": "Ambient Noise"},
    )
    assert resp.status_code == 200
    # No cat_id → no filename regeneration
    assert resp.json()["suggested_filename"] is None
