"""Tests for custom fields — DB, models, reader, writer, API."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.db import repository
from app.main import app
from app.metadata.reader import read_metadata
from app.metadata.writer import write_metadata
from app.models import FileRecord, MetadataUpdate
from conftest import build_wav, IXML_WITH_USER


# ---------------------------------------------------------------------------
# DB + Model tests (Commit 8: 2C.8a)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def _db(tmp_path):
    path = tmp_path / "test.db"
    await repository.connect(str(path))
    yield
    await repository.close()


def _base_record(**overrides) -> dict:
    defaults = {
        "path": "/tmp/test.wav",
        "filename": "test.wav",
        "directory": "/tmp",
        "status": "unmodified",
        "file_hash": "abc123",
        "technical": {
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": 1,
            "duration_seconds": 1.0,
            "frame_count": 44100,
            "audio_format": "PCM",
            "file_size_bytes": 88200,
        },
    }
    defaults.update(overrides)
    return defaults


@pytest.mark.asyncio
async def test_insert_with_custom_fields():
    record = _base_record(custom_fields={"MYTAG": "val", "OTHER": "data"})
    fid = await repository.insert_file(record)
    row = await repository.get_file(fid)
    assert row is not None
    assert row["custom_fields"] == {"MYTAG": "val", "OTHER": "data"}


@pytest.mark.asyncio
async def test_update_custom_fields():
    record = _base_record(custom_fields={"MYTAG": "old"})
    fid = await repository.insert_file(record)
    await repository.update_file(fid, {"custom_fields": {"MYTAG": "new"}})
    row = await repository.get_file(fid)
    assert row["custom_fields"] == {"MYTAG": "new"}


@pytest.mark.asyncio
async def test_insert_without_custom_fields():
    record = _base_record()
    fid = await repository.insert_file(record)
    row = await repository.get_file(fid)
    assert row["custom_fields"] is None


def test_file_record_with_custom_fields():
    fr = FileRecord(
        id="1",
        path="/tmp/test.wav",
        filename="test.wav",
        directory="/tmp",
        technical={
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": 1,
            "duration_seconds": 1.0,
            "frame_count": 44100,
            "audio_format": "PCM",
            "file_size_bytes": 88200,
        },
        custom_fields={"RECORDIST": "John"},
    )
    assert fr.custom_fields == {"RECORDIST": "John"}
    d = fr.model_dump()
    assert d["custom_fields"] == {"RECORDIST": "John"}


def test_metadata_update_with_custom_fields():
    mu = MetadataUpdate(custom_fields={"RECORDIST": "Jane"})
    d = mu.model_dump(exclude_unset=True)
    assert d["custom_fields"] == {"RECORDIST": "Jane"}


# ---------------------------------------------------------------------------
# Reader tests (Commit 9: 2C.8b)
# ---------------------------------------------------------------------------

# iXML with known + unknown USER tags
_IXML_CUSTOM = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<BWFXML>"
    "<IXML_VERSION>1.61</IXML_VERSION>"
    "<USER>"
    "<CATEGORY>AMBIENCE</CATEGORY>"
    "<FXNAME>Forest Birds</FXNAME>"
    "<RECORDIST>John Doe</RECORDIST>"
    "<LOCATION>Forest</LOCATION>"
    "</USER>"
    "</BWFXML>"
)


def test_reader_collects_unknown_user_tags(tmp_path):
    wav = build_wav(ixml_xml=_IXML_CUSTOM)
    p = tmp_path / "custom.wav"
    p.write_bytes(wav)
    meta = read_metadata(str(p))
    assert meta.get("custom_fields") is not None
    assert "RECORDIST" in meta["custom_fields"]
    assert "LOCATION" in meta["custom_fields"]
    assert meta["custom_fields"]["RECORDIST"] == "John Doe"


def test_reader_known_tags_not_in_custom_fields(tmp_path):
    wav = build_wav(ixml_xml=_IXML_CUSTOM)
    p = tmp_path / "custom2.wav"
    p.write_bytes(wav)
    meta = read_metadata(str(p))
    cf = meta.get("custom_fields") or {}
    assert "CATEGORY" not in cf
    assert "FXNAME" not in cf


# ---------------------------------------------------------------------------
# Writer tests (Commit 9: 2C.8b)
# ---------------------------------------------------------------------------


def test_writer_roundtrip_custom_fields(tmp_path):
    wav = build_wav(ixml_xml=IXML_WITH_USER)
    p = tmp_path / "write_custom.wav"
    p.write_bytes(wav)

    write_metadata(
        str(p),
        {
            "category": "WEATHER",
            "custom_fields": {"RECORDIST": "Jane", "LOCATION": "Studio"},
        },
    )

    meta = read_metadata(str(p))
    cf = meta.get("custom_fields") or {}
    assert cf.get("RECORDIST") == "Jane"
    assert cf.get("LOCATION") == "Studio"


def test_writer_custom_fields_only_roundtrip(tmp_path):
    """Custom-fields-only metadata must create iXML from scratch (no existing iXML)."""
    wav = build_wav()  # No iXML chunk at all
    p = tmp_path / "custom_only.wav"
    p.write_bytes(wav)

    write_metadata(
        str(p),
        {"custom_fields": {"RECORDIST": "Jane", "LOCATION": "Studio"}},
    )

    meta = read_metadata(str(p))
    cf = meta.get("custom_fields") or {}
    assert cf.get("RECORDIST") == "Jane"
    assert cf.get("LOCATION") == "Studio"


# ---------------------------------------------------------------------------
# API tests (Commit 9: 2C.8b)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_api_put_custom_fields(client, tmp_path):
    """PUT custom_fields, GET → persisted."""
    wav = build_wav(ixml_xml=IXML_WITH_USER)
    p = tmp_path / "api_custom.wav"
    p.write_bytes(wav)

    # Import
    resp = await client.post("/files/import", json={"directory": str(tmp_path)})
    assert resp.status_code == 200
    file_id = resp.json()["files"][0]["id"]

    # PUT custom_fields
    resp = await client.put(
        f"/files/{file_id}/metadata",
        json={"custom_fields": {"RECORDIST": "Test"}},
    )
    assert resp.status_code == 200
    assert resp.json()["custom_fields"] == {"RECORDIST": "Test"}

    # GET and verify
    resp = await client.get(f"/files/{file_id}")
    assert resp.json()["custom_fields"] == {"RECORDIST": "Test"}


@pytest.mark.asyncio
async def test_api_put_partial_custom_fields_merge(client, tmp_path):
    """PUT partial custom_fields → merges with existing."""
    wav = build_wav(ixml_xml=IXML_WITH_USER)
    p = tmp_path / "api_merge.wav"
    p.write_bytes(wav)

    resp = await client.post("/files/import", json={"directory": str(tmp_path)})
    file_id = resp.json()["files"][0]["id"]

    # First PUT
    await client.put(
        f"/files/{file_id}/metadata",
        json={"custom_fields": {"RECORDIST": "Jane"}},
    )
    # Second PUT — merge
    resp = await client.put(
        f"/files/{file_id}/metadata",
        json={"custom_fields": {"LOCATION": "Studio"}},
    )
    assert resp.status_code == 200
    cf = resp.json()["custom_fields"]
    assert cf["RECORDIST"] == "Jane"
    assert cf["LOCATION"] == "Studio"
