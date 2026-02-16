"""Tests for Phase 2B — Metadata Writing API + File Rename."""

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import repository
from app.db.repository import get_file, insert_file, update_file
from app.main import app
from app.metadata.writer import verify_write
from conftest import write_wav


def _make_record(**overrides) -> dict:
    """Build a minimal file record dict."""
    base = {
        "path": "/tmp/test.wav",
        "filename": "test.wav",
        "directory": "/tmp",
        "status": "unmodified",
        "changed_fields": [],
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
        "suggested_filename": None,
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db():
    """In-memory DB for repository-level tests."""
    await repository.connect(":memory:")
    yield
    await repository.close()


@pytest_asyncio.fixture
async def client():
    """Async test client with in-memory DB."""
    await repository.connect(":memory:")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await repository.close()


# ---------------------------------------------------------------------------
# 2B.0 — update_file() repository tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_file_single_field(db):
    """Update one column, verify others unchanged."""
    fid = await insert_file(_make_record(category="AMBIENCE"))
    await update_file(fid, {"category": "WEATHER"})
    row = await get_file(fid)
    assert row["category"] == "WEATHER"
    assert row["status"] == "unmodified"


@pytest.mark.asyncio
async def test_update_file_rejects_bad_column(db):
    """Unknown column raises ValueError."""
    fid = await insert_file(_make_record())
    with pytest.raises(ValueError, match="Invalid columns"):
        await update_file(fid, {"nonexistent_col": "value"})


@pytest.mark.asyncio
async def test_update_file_json_column(db):
    """JSON column (changed_fields) serializes and deserializes correctly."""
    fid = await insert_file(_make_record())
    await update_file(fid, {"changed_fields": ["category", "fx_name"]})
    row = await get_file(fid)
    assert row["changed_fields"] == ["category", "fx_name"]


# ---------------------------------------------------------------------------
# Helper: seed a file record via import
# ---------------------------------------------------------------------------


async def _seed_file(client, tmp_path, filename="test.wav", **wav_kwargs) -> dict:
    """Import a synthetic WAV and return the first FileRecord dict."""
    write_wav(tmp_path, filename, **wav_kwargs)
    resp = await client.post(
        "/files/import", json={"directory": str(tmp_path), "recursive": False}
    )
    return resp.json()["files"][0]


# ---------------------------------------------------------------------------
# 2B.1 — PUT /files/{id}/metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_metadata_single_field(tmp_path, client):
    """Updates 1 field, status='modified', fx_name in changed_fields."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.put(
        f"/files/{rec['id']}/metadata", json={"fx_name": "Thunder Roll"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["fx_name"] == "Thunder Roll"
    assert data["status"] == "modified"
    assert "fx_name" in data["changed_fields"]


@pytest.mark.asyncio
async def test_put_metadata_multiple_fields(tmp_path, client):
    """3 fields, all in changed_fields."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "WEATHER", "subcategory": "THUNDER", "fx_name": "Boom"},
    )
    data = resp.json()
    assert data["category"] == "WEATHER"
    assert data["subcategory"] == "THUNDER"
    assert data["fx_name"] == "Boom"
    assert set(data["changed_fields"]) >= {"category", "subcategory", "fx_name"}


@pytest.mark.asyncio
async def test_put_metadata_preserves_unchanged(tmp_path, client):
    """Edit fx_name, category unchanged."""
    rec = await _seed_file(client, tmp_path)
    # Set category first
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "AMBIENCE"})
    # Now update only fx_name
    resp = await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "Rain"})
    data = resp.json()
    assert data["category"] == "AMBIENCE"
    assert data["fx_name"] == "Rain"


@pytest.mark.asyncio
async def test_put_metadata_accumulates_changed(tmp_path, client):
    """PUT cat, then PUT fx_name -> changed_fields has both."""
    rec = await _seed_file(client, tmp_path)
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "WEATHER"})
    resp = await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "Rain"})
    data = resp.json()
    assert "category" in data["changed_fields"]
    assert "fx_name" in data["changed_fields"]


@pytest.mark.asyncio
async def test_put_metadata_suggested_filename(tmp_path, client):
    """Persists suggested_filename, survives GET round-trip."""
    rec = await _seed_file(client, tmp_path)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"suggested_filename": "WTHRThun_Thunder-Roll_TESTLIB.wav"},
    )
    resp = await client.get(f"/files/{rec['id']}")
    assert resp.json()["suggested_filename"] == "WTHRThun_Thunder-Roll_TESTLIB.wav"


@pytest.mark.asyncio
async def test_put_metadata_not_found(client):
    """404 for unknown ID."""
    resp = await client.put("/files/nonexistent-id/metadata", json={"fx_name": "X"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_metadata_empty_body(tmp_path, client):
    """No-op, status stays 'unmodified'."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.put(f"/files/{rec['id']}/metadata", json={})
    data = resp.json()
    assert data["status"] == "unmodified"


@pytest.mark.asyncio
async def test_put_metadata_clear_field(tmp_path, client):
    """Explicit null clears a field."""
    rec = await _seed_file(client, tmp_path)
    await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "Thunder"})
    resp = await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": None})
    data = resp.json()
    assert data["fx_name"] is None
    assert "fx_name" in data["changed_fields"]


# ---------------------------------------------------------------------------
# 2B.2 — POST /files/{id}/save (without rename)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_writes_metadata(tmp_path, client):
    """Save writes metadata to disk, verify_write confirms."""
    rec = await _seed_file(client, tmp_path)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "WEATHER", "fx_name": "Thunder Roll"},
    )
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    # Verify on disk
    result = verify_write(
        rec["path"], {"category": "WEATHER", "fx_name": "Thunder Roll"}
    )
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_save_status_and_changed(tmp_path, client):
    """After save: status='saved', changed_fields=[]."""
    rec = await _seed_file(client, tmp_path)
    await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "Rain"})
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    data = resp.json()
    assert data["file"]["status"] == "saved"
    assert data["file"]["changed_fields"] == []


@pytest.mark.asyncio
async def test_save_updates_hash(tmp_path, client):
    """file_hash changes after write (file content changed)."""
    rec = await _seed_file(client, tmp_path)
    row_before = await get_file(rec["id"])
    original_hash = row_before["file_hash"]

    await client.put(f"/files/{rec['id']}/metadata", json={"category": "WEATHER"})
    await client.post(f"/files/{rec['id']}/save", json={"rename": False})

    row_after = await get_file(rec["id"])
    assert row_after["file_hash"] != original_hash


@pytest.mark.asyncio
async def test_save_external_change(tmp_path, client):
    """Tamper file on disk after import → save returns 409."""
    rec = await _seed_file(client, tmp_path)
    await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "X"})
    # Tamper the file
    with open(rec["path"], "ab") as f:
        f.write(b"\x00" * 100)

    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_save_file_missing(tmp_path, client):
    """File deleted from disk → save returns 404."""
    rec = await _seed_file(client, tmp_path)
    os.remove(rec["path"])

    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_save_not_found(client):
    """Bad ID → 404."""
    resp = await client.post("/files/nonexistent-id/save", json={"rename": False})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_save_unmodified_file(tmp_path, client):
    """Save without prior PUT → 200 (writes current metadata)."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# 2B.3 — Rename logic in save
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_with_rename(tmp_path, client):
    """File moved, DB path updated, old gone, new exists."""
    rec = await _seed_file(client, tmp_path)
    new_name = "WTHRThun_Thunder-Roll.wav"
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "WEATHER", "suggested_filename": new_name},
    )
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": True})
    data = resp.json()
    assert data["renamed"] is True
    assert data["new_path"].endswith(new_name)
    # Old file gone
    assert not os.path.exists(rec["path"])
    # New file exists
    assert os.path.exists(data["new_path"])
    # DB updated
    row = await get_file(rec["id"])
    assert row["filename"] == new_name


@pytest.mark.asyncio
async def test_rename_no_suggested(tmp_path, client):
    """rename=True but no suggested_filename → renamed=False."""
    rec = await _seed_file(client, tmp_path)
    await client.put(f"/files/{rec['id']}/metadata", json={"fx_name": "Rain"})
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": True})
    assert resp.json()["renamed"] is False


@pytest.mark.asyncio
async def test_rename_same_filename(tmp_path, client):
    """suggested == current → renamed=False."""
    rec = await _seed_file(client, tmp_path)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"suggested_filename": rec["filename"]},
    )
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": True})
    assert resp.json()["renamed"] is False


@pytest.mark.asyncio
async def test_rename_conflict(tmp_path, client):
    """Target exists → 409."""
    rec = await _seed_file(client, tmp_path)
    conflict_name = "conflict.wav"
    # Create a file at the target path
    write_wav(tmp_path, conflict_name)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"suggested_filename": conflict_name},
    )
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": True})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_rename_conflict_before_write(tmp_path, client):
    """409 + original file unmodified (no metadata written)."""
    rec = await _seed_file(client, tmp_path)
    original_bytes = open(rec["path"], "rb").read()
    conflict_name = "conflict.wav"
    write_wav(tmp_path, conflict_name)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "WEATHER", "suggested_filename": conflict_name},
    )
    resp = await client.post(f"/files/{rec['id']}/save", json={"rename": True})
    assert resp.status_code == 409
    # Original file should be untouched
    assert open(rec["path"], "rb").read() == original_bytes


# ---------------------------------------------------------------------------
# 2B.4 — POST /files/save-batch
# ---------------------------------------------------------------------------


async def _seed_multiple(client, tmp_path, count=3):
    """Import multiple synthetic WAVs and return their FileRecord dicts."""
    for i in range(count):
        write_wav(tmp_path, f"file{i}.wav")
    resp = await client.post(
        "/files/import", json={"directory": str(tmp_path), "recursive": False}
    )
    return resp.json()["files"]


@pytest.mark.asyncio
async def test_batch_save_all_success(tmp_path, client):
    """3 files, all succeed."""
    recs = await _seed_multiple(client, tmp_path, 3)
    ids = [r["id"] for r in recs]
    resp = await client.post(
        "/files/save-batch", json={"file_ids": ids, "rename": False}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["saved_count"] == 3
    assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_batch_save_partial_failure(tmp_path, client):
    """1 file deleted from disk, 2 succeed, 1 fails."""
    recs = await _seed_multiple(client, tmp_path, 3)
    # Delete one file from disk
    os.remove(recs[0]["path"])
    ids = [r["id"] for r in recs]
    resp = await client.post(
        "/files/save-batch", json={"file_ids": ids, "rename": False}
    )
    data = resp.json()
    assert data["saved_count"] == 2
    assert data["failed_count"] == 1
    failed = [r for r in data["results"] if not r["success"]]
    assert len(failed) == 1


@pytest.mark.asyncio
async def test_batch_save_empty_list(client):
    """0/0 counts."""
    resp = await client.post(
        "/files/save-batch", json={"file_ids": [], "rename": False}
    )
    data = resp.json()
    assert data["saved_count"] == 0
    assert data["failed_count"] == 0


@pytest.mark.asyncio
async def test_batch_save_with_rename(tmp_path, client):
    """Batch rename works."""
    recs = await _seed_multiple(client, tmp_path, 2)
    for i, rec in enumerate(recs):
        await client.put(
            f"/files/{rec['id']}/metadata",
            json={"suggested_filename": f"renamed{i}.wav"},
        )
    ids = [r["id"] for r in recs]
    resp = await client.post(
        "/files/save-batch", json={"file_ids": ids, "rename": True}
    )
    data = resp.json()
    assert data["saved_count"] == 2
    renamed = [r for r in data["results"] if r["renamed"]]
    assert len(renamed) == 2


# ---------------------------------------------------------------------------
# 2B.5 — POST /files/{id}/revert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_revert_restores_original(tmp_path, client):
    """Edit → revert → original category restored, status=unmodified."""
    rec = await _seed_file(client, tmp_path)
    original_category = rec["category"]
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "WEATHER"})
    resp = await client.post(f"/files/{rec['id']}/revert")
    data = resp.json()
    assert data["category"] == original_category
    assert data["status"] == "unmodified"


@pytest.mark.asyncio
async def test_revert_after_save(tmp_path, client):
    """Save → edit → revert → reads saved values from disk."""
    rec = await _seed_file(client, tmp_path)
    # Save with category WEATHER
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "WEATHER"})
    await client.post(f"/files/{rec['id']}/save", json={"rename": False})
    # Edit again
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "DOORS"})
    # Revert should read from disk (which has WEATHER)
    resp = await client.post(f"/files/{rec['id']}/revert")
    assert resp.json()["category"] == "WEATHER"


@pytest.mark.asyncio
async def test_revert_clears_changed(tmp_path, client):
    """changed_fields → [] after revert."""
    rec = await _seed_file(client, tmp_path)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "X", "fx_name": "Y"},
    )
    resp = await client.post(f"/files/{rec['id']}/revert")
    assert resp.json()["changed_fields"] == []


@pytest.mark.asyncio
async def test_revert_not_found(client):
    """404 for unknown ID."""
    resp = await client.post("/files/nonexistent-id/revert")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revert_file_missing(tmp_path, client):
    """File deleted from disk → 404."""
    rec = await _seed_file(client, tmp_path)
    os.remove(rec["path"])
    resp = await client.post(f"/files/{rec['id']}/revert")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_revert_preserves_import_fallbacks(tmp_path, client):
    """Revert re-applies import-time BEXT/INFO fallbacks (C1 fix)."""
    from conftest import build_bext_data

    bext = build_bext_data(description="BEXT desc from disk")
    rec = await _seed_file(client, tmp_path, bext_data=bext)
    # Import should have applied fallback: BEXT description → iXML description
    assert rec["description"] == "BEXT desc from disk"
    # Edit something
    await client.put(f"/files/{rec['id']}/metadata", json={"category": "WEATHER"})
    # Revert should re-read + re-apply fallback
    resp = await client.post(f"/files/{rec['id']}/revert")
    data = resp.json()
    assert data["description"] == "BEXT desc from disk"
    assert data["status"] == "unmodified"


@pytest.mark.asyncio
async def test_revert_restores_custom_fields(tmp_path, client):
    """Revert re-reads custom_fields from disk (C2 fix)."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML><USER><RECORDIST>Jane</RECORDIST></USER></BWFXML>"
    )
    rec = await _seed_file(client, tmp_path, ixml_xml=ixml)
    assert rec["custom_fields"] == {"RECORDIST": "Jane"}
    # Edit custom_fields in DB
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"custom_fields": {"RECORDIST": "Bob", "NEWTAG": "val"}},
    )
    # Revert should restore from disk (only RECORDIST=Jane)
    resp = await client.post(f"/files/{rec['id']}/revert")
    data = resp.json()
    assert data["custom_fields"] == {"RECORDIST": "Jane"}


# ---------------------------------------------------------------------------
# 2B.6 — POST /files/apply-metadata
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_metadata(tmp_path, client):
    """Copy category+designer from source to 2 targets."""
    recs = await _seed_multiple(client, tmp_path, 3)
    source = recs[0]
    await client.put(
        f"/files/{source['id']}/metadata",
        json={"category": "WEATHER", "designer": "JD"},
    )
    resp = await client.post(
        "/files/apply-metadata",
        json={
            "source_id": source["id"],
            "target_ids": [recs[1]["id"], recs[2]["id"]],
            "fields": ["category", "designer"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    for rec in data["updated"]:
        assert rec["category"] == "WEATHER"
        assert rec["designer"] == "JD"


@pytest.mark.asyncio
async def test_apply_metadata_tracks_changed(tmp_path, client):
    """Target changed_fields includes copied fields."""
    recs = await _seed_multiple(client, tmp_path, 2)
    await client.put(f"/files/{recs[0]['id']}/metadata", json={"category": "WEATHER"})
    resp = await client.post(
        "/files/apply-metadata",
        json={
            "source_id": recs[0]["id"],
            "target_ids": [recs[1]["id"]],
            "fields": ["category"],
        },
    )
    target = resp.json()["updated"][0]
    assert "category" in target["changed_fields"]


@pytest.mark.asyncio
async def test_apply_metadata_source_404(client):
    """Bad source ID → 404."""
    resp = await client.post(
        "/files/apply-metadata",
        json={
            "source_id": "nonexistent",
            "target_ids": ["also-nonexistent"],
            "fields": ["category"],
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_apply_metadata_invalid_field(tmp_path, client):
    """Bad field name → 422."""
    recs = await _seed_multiple(client, tmp_path, 2)
    resp = await client.post(
        "/files/apply-metadata",
        json={
            "source_id": recs[0]["id"],
            "target_ids": [recs[1]["id"]],
            "fields": ["nonexistent_field"],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_apply_metadata_skips_missing_target(tmp_path, client):
    """1 target missing → partial success."""
    recs = await _seed_multiple(client, tmp_path, 2)
    await client.put(f"/files/{recs[0]['id']}/metadata", json={"category": "WEATHER"})
    resp = await client.post(
        "/files/apply-metadata",
        json={
            "source_id": recs[0]["id"],
            "target_ids": [recs[1]["id"], "nonexistent-id"],
            "fields": ["category"],
        },
    )
    data = resp.json()
    assert data["count"] == 1


# ---------------------------------------------------------------------------
# 2B.7 — POST /files/{id}/save with copy=true (Save as Copy)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_save_as_copy(tmp_path, client):
    """Save as copy creates copy at chosen path, original untouched."""
    rec = await _seed_file(client, tmp_path)
    await client.put(
        f"/files/{rec['id']}/metadata",
        json={"category": "WEATHER", "fx_name": "Thunder Roll"},
    )

    copy_path = str(tmp_path / "copy.wav")
    resp = await client.post(
        f"/files/{rec['id']}/save",
        json={"rename": False, "save_copy": True, "copy_path": copy_path},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["copied"] is True
    assert data["copy_path"] == copy_path

    # Copy file exists on disk
    assert os.path.exists(copy_path)

    # Original file still exists
    assert os.path.exists(rec["path"])

    # Original status stays modified (not saved)
    row = await get_file(rec["id"])
    assert row["status"] == "modified"

    # Verify metadata written to copy
    result = verify_write(copy_path, {"category": "WEATHER", "fx_name": "Thunder Roll"})
    assert result["ok"] is True


@pytest.mark.asyncio
async def test_save_as_copy_missing_path(tmp_path, client):
    """copy=True without copy_path → 422."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.post(
        f"/files/{rec['id']}/save",
        json={"rename": False, "save_copy": True},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_save_as_copy_bad_directory(tmp_path, client):
    """copy_path with nonexistent parent dir → 422."""
    rec = await _seed_file(client, tmp_path)
    resp = await client.post(
        f"/files/{rec['id']}/save",
        json={
            "rename": False,
            "save_copy": True,
            "copy_path": str(tmp_path / "nonexistent" / "copy.wav"),
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Batch update (5.7A)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_update_happy_path(client):
    """Batch update sets values on multiple files."""
    id1 = await insert_file(_make_record(path="/tmp/a.wav", filename="a.wav"))
    id2 = await insert_file(_make_record(path="/tmp/b.wav", filename="b.wav"))

    resp = await client.post(
        "/files/batch-update",
        json={"file_ids": [id1, id2], "updates": {"designer": "JD", "library": "LIB1"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert all(f["designer"] == "JD" for f in data["updated"])
    assert all(f["library"] == "LIB1" for f in data["updated"])
    assert all(f["status"] == "modified" for f in data["updated"])


@pytest.mark.asyncio
async def test_batch_update_invalid_field_422(client):
    """Batch update with invalid field name returns 422."""
    fid = await insert_file(_make_record())

    resp = await client.post(
        "/files/batch-update",
        json={"file_ids": [fid], "updates": {"bogus_field": "X"}},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_batch_update_missing_file_partial(client):
    """Batch update skips missing files, updates the rest."""
    fid = await insert_file(_make_record())

    resp = await client.post(
        "/files/batch-update",
        json={"file_ids": [fid, "nonexistent-id"], "updates": {"designer": "JD"}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 1
