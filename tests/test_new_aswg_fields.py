"""Tests for new ASWG extended fields: manufacturer, rec_type, creator_id, source_id."""

import pytest

from conftest import (
    get_aswg_field,
    get_user_field,
    parse_ixml_source,
    write_wav,
)

from app.metadata.reader import read_metadata
from app.metadata.writer import write_metadata


# ---------------------------------------------------------------------------
# iXML read — ASWG tags
# ---------------------------------------------------------------------------

IXML_WITH_ASWG_EXTENDED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<BWFXML>"
    "<IXML_VERSION>1.61</IXML_VERSION>"
    "<ASWG>"
    "<manufacturer>Sennheiser</manufacturer>"
    "<recType>field</recType>"
    "<creatorId>PB01</creatorId>"
    "<sourceId>MYLIB</sourceId>"
    "</ASWG>"
    "</BWFXML>"
)


def test_read_aswg_extended_fields(tmp_path):
    """ASWG manufacturer/recType/creatorId/sourceId map to correct FileRecord keys."""
    path = write_wav(tmp_path, "aswg_ext.wav", ixml_xml=IXML_WITH_ASWG_EXTENDED)
    result = read_metadata(str(path))
    assert result["manufacturer"] == "Sennheiser"
    assert result["rec_type"] == "field"
    assert result["creator_id"] == "PB01"
    assert result["source_id"] == "MYLIB"


# ---------------------------------------------------------------------------
# iXML read — USER tags
# ---------------------------------------------------------------------------

IXML_WITH_USER_EXTENDED = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<BWFXML>"
    "<IXML_VERSION>1.61</IXML_VERSION>"
    "<USER>"
    "<MANUFACTURER>Neumann</MANUFACTURER>"
    "<RECTYPE>studio</RECTYPE>"
    "<CREATORID>JD02</CREATORID>"
    "<SOURCEID>OTHERLIB</SOURCEID>"
    "</USER>"
    "</BWFXML>"
)


def test_read_user_extended_fields(tmp_path):
    """USER MANUFACTURER/RECTYPE/CREATORID/SOURCEID map to correct keys."""
    path = write_wav(tmp_path, "user_ext.wav", ixml_xml=IXML_WITH_USER_EXTENDED)
    result = read_metadata(str(path))
    assert result["manufacturer"] == "Neumann"
    assert result["rec_type"] == "studio"
    assert result["creator_id"] == "JD02"
    assert result["source_id"] == "OTHERLIB"


def test_user_overrides_aswg_extended(tmp_path):
    """USER tags have higher priority than ASWG for extended fields."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<ASWG><manufacturer>AKG</manufacturer><creatorId>A</creatorId></ASWG>"
        "<USER><MANUFACTURER>Shure</MANUFACTURER><CREATORID>B</CREATORID></USER>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "override.wav", ixml_xml=ixml)
    result = read_metadata(str(path))
    assert result["manufacturer"] == "Shure"
    assert result["creator_id"] == "B"


# ---------------------------------------------------------------------------
# Write + round-trip
# ---------------------------------------------------------------------------


def test_write_extended_fields_roundtrip(tmp_path):
    """Write new fields → read back → values match."""
    path = write_wav(tmp_path, "roundtrip.wav")
    metadata = {
        "manufacturer": "DPA",
        "rec_type": "ambisonic",
        "creator_id": "XY99",
        "source_id": "BIGLIB",
    }
    write_metadata(str(path), metadata)
    result = read_metadata(str(path))
    assert result["manufacturer"] == "DPA"
    assert result["rec_type"] == "ambisonic"
    assert result["creator_id"] == "XY99"
    assert result["source_id"] == "BIGLIB"


def test_write_extended_fields_ixml_tags(tmp_path):
    """Written iXML contains correct USER and ASWG tags for new fields."""
    from wavinfo import WavInfoReader

    path = write_wav(tmp_path, "tags.wav")
    metadata = {
        "manufacturer": "Schoeps",
        "rec_type": "foley",
        "creator_id": "AB01",
        "source_id": "TESTLIB",
    }
    write_metadata(str(path), metadata)
    info = WavInfoReader(str(path))
    root = parse_ixml_source(info)
    assert root is not None

    # USER tags (ALL CAPS)
    assert get_user_field(root, "MANUFACTURER") == "Schoeps"
    assert get_user_field(root, "RECTYPE") == "foley"
    assert get_user_field(root, "CREATORID") == "AB01"
    assert get_user_field(root, "SOURCEID") == "TESTLIB"

    # ASWG tags (camelCase)
    assert get_aswg_field(root, "manufacturer") == "Schoeps"
    assert get_aswg_field(root, "recType") == "foley"
    assert get_aswg_field(root, "creatorId") == "AB01"
    assert get_aswg_field(root, "sourceId") == "TESTLIB"


# ---------------------------------------------------------------------------
# DB migration (idempotent)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_aswg_migration_idempotent(tmp_path):
    """Migration adds columns and is safe to run twice."""
    import aiosqlite

    from app.db.schema import init_db

    db_path = tmp_path / "test.db"
    async with aiosqlite.connect(str(db_path)) as db:
        await init_db(db)
        # Run again — should not raise
        await init_db(db)

        cursor = await db.execute("PRAGMA table_info(files)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "manufacturer" in columns
        assert "rec_type" in columns
        assert "creator_id" in columns
        assert "source_id" in columns


# ---------------------------------------------------------------------------
# MetadataUpdate model accepts new fields
# ---------------------------------------------------------------------------


def test_metadata_update_accepts_new_fields():
    """MetadataUpdate Pydantic model accepts the 4 new fields."""
    from app.models import MetadataUpdate

    update = MetadataUpdate(
        manufacturer="Sony",
        rec_type="studio",
        creator_id="XX",
        source_id="YY",
    )
    dumped = update.model_dump(exclude_unset=True)
    assert dumped["manufacturer"] == "Sony"
    assert dumped["rec_type"] == "studio"
    assert dumped["creator_id"] == "XX"
    assert dumped["source_id"] == "YY"
