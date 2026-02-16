"""Tests for the metadata reader module."""

import os

from conftest import (
    IXML_WITH_USER,
    IXML_WITH_VENDOR,
    build_bext_data,
    write_wav,
)

from app.metadata.reader import compute_file_hash, read_metadata


# ---------------------------------------------------------------------------
# read_metadata — technical fields
# ---------------------------------------------------------------------------


def test_read_metadata_technical_fields(tmp_path):
    """Technical fields extracted from fmt + data chunks."""
    path = write_wav(
        tmp_path,
        "tech.wav",
        num_samples=200,
        sample_rate=48000,
        channels=2,
        bits_per_sample=16,
    )
    result = read_metadata(str(path))

    tech = result["technical"]
    assert tech["sample_rate"] == 48000
    assert tech["bit_depth"] == 16
    assert tech["channels"] == 2
    assert tech["frame_count"] == 200
    assert tech["audio_format"] == "PCM"
    assert tech["file_size_bytes"] == os.path.getsize(path)
    assert tech["duration_seconds"] > 0


# ---------------------------------------------------------------------------
# read_metadata — BEXT extraction
# ---------------------------------------------------------------------------


def test_read_metadata_bext_fields(tmp_path):
    """BEXT chunk fields correctly extracted."""
    bext = build_bext_data(description="Rainstorm recording", originator="JD")
    path = write_wav(tmp_path, "bext.wav", bext_data=bext)
    result = read_metadata(str(path))

    assert result["bext"] is not None
    assert result["bext"]["description"] == "Rainstorm recording"
    assert result["bext"]["originator"] == "JD"
    assert result["bext"]["originator_date"] == "2024-01-01"


def test_read_metadata_no_bext(tmp_path):
    """Missing BEXT chunk → bext is None."""
    path = write_wav(tmp_path, "nobext.wav")
    result = read_metadata(str(path))
    assert result["bext"] is None


# ---------------------------------------------------------------------------
# read_metadata — RIFF INFO extraction
# ---------------------------------------------------------------------------


def test_read_metadata_no_info(tmp_path):
    """Missing RIFF INFO → info is None."""
    path = write_wav(tmp_path, "noinfo.wav")
    result = read_metadata(str(path))
    assert result["info"] is None


# ---------------------------------------------------------------------------
# read_metadata — iXML USER fields
# ---------------------------------------------------------------------------


def test_read_metadata_ixml_user_fields(tmp_path):
    """USER fields extracted from iXML."""
    path = write_wav(tmp_path, "user.wav", ixml_xml=IXML_WITH_USER)
    result = read_metadata(str(path))

    assert result["category"] == "AMBIENCE"
    assert result["fx_name"] == "Forest Birds"
    assert result["microphone"] == "MKH416"


# ---------------------------------------------------------------------------
# read_metadata — USER overrides ASWG
# ---------------------------------------------------------------------------


def test_read_metadata_user_overrides_aswg(tmp_path):
    """When both USER and ASWG have the same field, USER wins."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<USER><CATEGORY>FROM_USER</CATEGORY><FXNAME>UserName</FXNAME></USER>"
        "<ASWG><category>FROM_ASWG</category><fxName>AswgName</fxName></ASWG>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "override.wav", ixml_xml=ixml)
    result = read_metadata(str(path))

    assert result["category"] == "FROM_USER"
    assert result["fx_name"] == "UserName"


def test_read_metadata_aswg_fallback(tmp_path):
    """ASWG fields used when USER doesn't have them."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<ASWG><category>AMBIENCE</category><project>MyProject</project></ASWG>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "aswg.wav", ixml_xml=ixml)
    result = read_metadata(str(path))

    assert result["category"] == "AMBIENCE"
    assert result["project"] == "MyProject"


# ---------------------------------------------------------------------------
# read_metadata — vendor block with both USER + ASWG
# ---------------------------------------------------------------------------


def test_read_metadata_vendor_ixml(tmp_path):
    """Vendor block iXML still extracts USER + ASWG fields."""
    path = write_wav(tmp_path, "vendor.wav", ixml_xml=IXML_WITH_VENDOR)
    result = read_metadata(str(path))

    assert result["category"] == "AMBIENCE"
    assert result["fx_name"] == "Forest Birds"
    assert result["microphone"] == "MKH416"


# ---------------------------------------------------------------------------
# read_metadata — plain WAV (no iXML)
# ---------------------------------------------------------------------------


def test_read_metadata_no_ixml(tmp_path):
    """No iXML chunk → all metadata fields None."""
    path = write_wav(tmp_path, "plain.wav")
    result = read_metadata(str(path))

    assert result["category"] is None
    assert result["fx_name"] is None
    assert result["description"] is None
    assert result["keywords"] is None


# ---------------------------------------------------------------------------
# read_metadata — all 18 nullable fields present in result
# ---------------------------------------------------------------------------


def test_read_metadata_has_all_nullable_fields(tmp_path):
    """Result dict always contains all 22 nullable metadata keys."""
    path = write_wav(tmp_path, "fields.wav")
    result = read_metadata(str(path))

    expected_keys = {
        "category",
        "subcategory",
        "cat_id",
        "category_full",
        "user_category",
        "fx_name",
        "description",
        "keywords",
        "notes",
        "designer",
        "library",
        "project",
        "microphone",
        "mic_perspective",
        "rec_medium",
        "release_date",
        "rating",
        "is_designed",
        "manufacturer",
        "rec_type",
        "creator_id",
        "source_id",
    }
    for key in expected_keys:
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# read_metadata — ASWG fallback: originator → designer
# ---------------------------------------------------------------------------


def test_read_metadata_aswg_originator_fallback(tmp_path):
    """ASWG originator used as designer when creatorId is absent."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<ASWG><originator>JohnDoe</originator></ASWG>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "orig_fallback.wav", ixml_xml=ixml)
    result = read_metadata(str(path))
    assert result["designer"] == "JohnDoe"


def test_read_metadata_aswg_source_id(tmp_path):
    """ASWG sourceId maps to source_id field (not library)."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<ASWG><sourceId>SRC123</sourceId></ASWG>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "srcid.wav", ixml_xml=ixml)
    result = read_metadata(str(path))
    assert result["source_id"] == "SRC123"
    assert result["library"] is None


def test_read_metadata_aswg_creator_id_separate_from_originator(tmp_path):
    """ASWG creatorId maps to creator_id; originator maps to designer."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML>"
        "<ASWG>"
        "<originator>Fallback</originator>"
        "<creatorId>Primary</creatorId>"
        "</ASWG>"
        "</BWFXML>"
    )
    path = write_wav(tmp_path, "precedence.wav", ixml_xml=ixml)
    result = read_metadata(str(path))
    assert result["designer"] == "Fallback"
    assert result["creator_id"] == "Primary"


# ---------------------------------------------------------------------------
# compute_file_hash
# ---------------------------------------------------------------------------


def test_compute_file_hash_deterministic(tmp_path):
    """Same file → same hash."""
    path = write_wav(tmp_path, "hash.wav")
    h1 = compute_file_hash(str(path))
    h2 = compute_file_hash(str(path))
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_compute_file_hash_changes_on_modification(tmp_path):
    """Modifying file changes the hash."""
    path = write_wav(tmp_path, "mutable.wav")
    h1 = compute_file_hash(str(path))

    # Append bytes to change content
    with open(path, "ab") as f:
        f.write(b"\x00" * 100)

    h2 = compute_file_hash(str(path))
    assert h1 != h2
