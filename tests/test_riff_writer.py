"""Pytest tests for the RIFF writer module.

Uses synthetic WAV fixtures — no external file dependencies.
"""

from wavinfo import WavInfoReader

from app.metadata.writer import write_metadata

from app.metadata.reader import read_metadata

from conftest import (
    IXML_WITH_VENDOR,
    MINIMAL_IXML,
    TEST_METADATA,
    build_bext_data,
    build_wav,
    count_chunks,
    get_aswg_field,
    get_user_field,
    parse_ixml_source,
    write_wav,
)


# ---------------------------------------------------------------------------
# 1B.1 — Fixture validation
# ---------------------------------------------------------------------------


def test_build_wav_parseable(tmp_path):
    """WavInfoReader can parse a bare synthetic WAV."""
    p = write_wav(tmp_path)
    info = WavInfoReader(str(p))
    assert info.data.frame_count == 100
    assert info.fmt.sample_rate == 44100


def test_build_wav_with_bext_and_ixml(tmp_path):
    """Optional bext and iXML chunks are parsed correctly."""
    bext = build_bext_data(description="hello", originator="me")
    p = write_wav(tmp_path, bext_data=bext, ixml_xml=MINIMAL_IXML)
    info = WavInfoReader(str(p))
    assert info.bext is not None
    root = parse_ixml_source(info)
    assert root is not None
    assert root.tag == "BWFXML"


# ---------------------------------------------------------------------------
# 1B.2 — Core writer tests
# ---------------------------------------------------------------------------


def test_write_no_existing_metadata(tmp_path):
    """WAV with only fmt+data. Writer creates bext+iXML from scratch."""
    p = write_wav(tmp_path)
    original = WavInfoReader(str(p))
    original_frames = original.data.frame_count

    write_metadata(str(p), TEST_METADATA)
    updated = WavInfoReader(str(p))

    # Audio integrity
    assert updated.data.frame_count == original_frames

    # BEXT created
    assert updated.bext is not None
    desc = updated.bext.description
    if isinstance(desc, bytes):
        desc = desc.rstrip(b"\x00").decode("ascii", errors="replace")
    assert desc == TEST_METADATA["description"]

    # iXML created with USER + ASWG fields
    root = parse_ixml_source(updated)
    assert root is not None
    assert get_user_field(root, "CATEGORY") == "WEATHER"
    assert get_user_field(root, "CATID") == "WTHRThun"
    assert get_user_field(root, "FXNAME") == "Thunder Rumble Low"
    assert get_user_field(root, "EMBEDDER") == "NomenAudio"
    assert get_aswg_field(root, "category") == "WEATHER"
    assert get_aswg_field(root, "catId") == "WTHRThun"
    assert get_aswg_field(root, "contentType") == "sfx"


def test_write_existing_bext_and_ixml(tmp_path):
    """WAV with bext (date=2024-01-01) + minimal iXML. Updates bext, adds USER/ASWG."""
    bext = build_bext_data(description="old desc", originator="OLD")
    p = write_wav(tmp_path, bext_data=bext, ixml_xml=MINIMAL_IXML)
    original = WavInfoReader(str(p))
    original_frames = original.data.frame_count

    write_metadata(str(p), TEST_METADATA)
    updated = WavInfoReader(str(p))

    # Audio integrity
    assert updated.data.frame_count == original_frames

    # BEXT description updated
    desc = updated.bext.description
    if isinstance(desc, bytes):
        desc = desc.rstrip(b"\x00").decode("ascii", errors="replace")
    assert desc == TEST_METADATA["description"]

    # Origination date preserved
    orig_date = updated.bext.originator_date
    if isinstance(orig_date, bytes):
        orig_date = orig_date.rstrip(b"\x00").decode("ascii", errors="replace")
    assert orig_date == "2024-01-01"

    # iXML has VERSION + USER fields
    root = parse_ixml_source(updated)
    assert root is not None
    assert root.find("IXML_VERSION") is not None
    assert get_user_field(root, "CATEGORY") == "WEATHER"
    assert get_user_field(root, "EMBEDDER") == "NomenAudio"


def test_write_preserves_vendor_blocks(tmp_path):
    """WAV with iXML containing STEINBERG+USER+ASWG. Vendor blocks preserved."""
    bext = build_bext_data()
    p = write_wav(tmp_path, bext_data=bext, ixml_xml=IXML_WITH_VENDOR)
    original = WavInfoReader(str(p))
    orig_root = parse_ixml_source(original)
    assert orig_root is not None
    assert orig_root.find("STEINBERG") is not None

    write_metadata(str(p), TEST_METADATA)
    updated = WavInfoReader(str(p))

    root = parse_ixml_source(updated)
    assert root is not None

    # Vendor block preserved
    steinberg = root.find("STEINBERG")
    assert steinberg is not None
    assert steinberg.find("PRODUCT").text == "Nuendo"

    # USER/CATEGORY updated
    assert get_user_field(root, "CATEGORY") == "WEATHER"

    # Existing USER field not in our metadata preserved
    assert get_user_field(root, "MICROPHONE") == "MKH416"


def test_idempotency(tmp_path):
    """Write twice with same metadata — frame_count same, no duplicate blocks."""
    p = write_wav(tmp_path)

    write_metadata(str(p), TEST_METADATA)
    first = WavInfoReader(str(p))
    first_frames = first.data.frame_count
    first_root = parse_ixml_source(first)

    write_metadata(str(p), TEST_METADATA)
    second = WavInfoReader(str(p))
    second_root = parse_ixml_source(second)

    assert second.data.frame_count == first_frames

    assert first_root is not None and second_root is not None
    for tag in ("CATEGORY", "CATID", "FXNAME", "DESCRIPTION"):
        assert get_user_field(second_root, tag) == get_user_field(first_root, tag)

    assert len(second_root.findall("USER")) == 1
    assert len(second_root.findall("ASWG")) == 1


# ---------------------------------------------------------------------------
# 1B.4 — Duplicate chunk tests
# ---------------------------------------------------------------------------


def test_duplicate_bext_produces_single_output(tmp_path):
    """WAV with 2 bext chunks -> output has exactly 1."""
    bext1 = build_bext_data(description="first")
    bext2 = build_bext_data(description="second")
    wav = build_wav(bext_data=bext1, extra_chunks=[(b"bext", bext2)])
    assert count_chunks(wav, b"bext") == 2

    p = tmp_path / "dup_bext.wav"
    p.write_bytes(wav)
    write_metadata(str(p), TEST_METADATA)

    output = p.read_bytes()
    assert count_chunks(output, b"bext") == 1


def test_duplicate_ixml_produces_single_output(tmp_path):
    """WAV with 2 iXML chunks -> output has exactly 1."""
    ixml1 = MINIMAL_IXML.encode("utf-8")
    ixml2 = MINIMAL_IXML.encode("utf-8")
    wav = build_wav(ixml_raw_bytes=ixml1, extra_chunks=[(b"iXML", ixml2)])
    assert count_chunks(wav, b"iXML") == 2

    p = tmp_path / "dup_ixml.wav"
    p.write_bytes(wav)
    write_metadata(str(p), TEST_METADATA)

    output = p.read_bytes()
    assert count_chunks(output, b"iXML") == 1


# ---------------------------------------------------------------------------
# 1B.5 — iXML encoding tests
# ---------------------------------------------------------------------------


def test_ixml_utf16le_decoded_correctly(tmp_path):
    """iXML with UTF-16 LE BOM -> decoded and existing fields preserved."""
    xml_with_vendor = IXML_WITH_VENDOR
    raw = b"\xff\xfe" + xml_with_vendor.encode("utf-16-le")
    p = write_wav(tmp_path, ixml_raw_bytes=raw, filename="utf16le.wav")
    write_metadata(str(p), TEST_METADATA)

    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert root is not None
    assert get_user_field(root, "CATEGORY") == "WEATHER"
    # STEINBERG block from original UTF-16 iXML must be preserved
    assert root.find("STEINBERG") is not None


def test_ixml_latin1_decoded_correctly(tmp_path):
    """iXML with Latin-1 e-acute in preserved field -> character not mangled."""
    # \xe9 = e-acute in Latin-1, which is NOT valid UTF-8
    # Place it in MICROPHONE which our metadata doesn't overwrite
    raw = (
        b'<?xml version="1.0" encoding="UTF-8"?>'
        b"<BWFXML><IXML_VERSION>1.61</IXML_VERSION>"
        b"<USER><MICROPHONE>Br\xfcel</MICROPHONE></USER></BWFXML>"
    )
    p = write_wav(tmp_path, ixml_raw_bytes=raw, filename="latin1.wav")
    write_metadata(str(p), TEST_METADATA)

    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert root is not None
    assert get_user_field(root, "CATEGORY") == "WEATHER"
    # \xfc = u-umlaut in Latin-1 -> should be preserved as "Br\u00fcel"
    mic = get_user_field(root, "MICROPHONE")
    assert mic is not None
    assert "\ufffd" not in mic, f"Replacement char found in MICROPHONE: {mic!r}"


# ---------------------------------------------------------------------------
# 1B.6 — verify_write tests
# ---------------------------------------------------------------------------


def test_verify_write_ok_after_write(tmp_path):
    """verify_write returns ok=True after a successful write."""
    from app.metadata.writer import verify_write

    p = write_wav(tmp_path)
    write_metadata(str(p), TEST_METADATA)
    result = verify_write(str(p), TEST_METADATA)
    assert result["ok"] is True, f"Errors: {result['errors']}"


def test_verify_write_detects_mismatch(tmp_path):
    """verify_write returns ok=False when metadata differs from file."""
    from app.metadata.writer import verify_write

    p = write_wav(tmp_path)
    write_metadata(str(p), TEST_METADATA)
    wrong_meta = {**TEST_METADATA, "category": "NONEXISTENT"}
    result = verify_write(str(p), wrong_meta)
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# 1B.7 — Edge case tests (spec S7)
# ---------------------------------------------------------------------------


def test_file_too_small(tmp_path):
    """File < 12 bytes raises ValueError."""
    p = tmp_path / "tiny.wav"
    p.write_bytes(b"RIFF\x00\x00")
    import pytest

    with pytest.raises(ValueError, match="too small"):
        write_metadata(str(p), TEST_METADATA)


def test_rifx_header(tmp_path):
    """File with RIFX header raises ValueError."""
    import pytest

    wav = bytearray(build_wav())
    wav[0:4] = b"RIFX"
    p = tmp_path / "rifx.wav"
    p.write_bytes(wav)
    with pytest.raises(ValueError, match="Big-endian RIFX"):
        write_metadata(str(p), TEST_METADATA)


def test_rf64_header(tmp_path):
    """File with RF64 header raises ValueError."""
    import pytest

    wav = bytearray(build_wav())
    wav[0:4] = b"RF64"
    p = tmp_path / "rf64.wav"
    p.write_bytes(wav)
    with pytest.raises(ValueError, match="RF64"):
        write_metadata(str(p), TEST_METADATA)


def test_chunk_size_past_eof(tmp_path):
    """Data chunk claims more bytes than available -> truncated, write succeeds."""
    import struct as st

    wav = bytearray(build_wav(num_samples=10))
    # Find data chunk and inflate its claimed size
    pos = 12
    while pos + 8 <= len(wav):
        cid = wav[pos : pos + 4]
        sz = st.unpack_from("<I", wav, pos + 4)[0]
        if cid == b"data":
            st.pack_into("<I", wav, pos + 4, sz + 9999)
            break
        pos += 8 + sz + (sz % 2)

    p = tmp_path / "truncated.wav"
    p.write_bytes(wav)
    write_metadata(str(p), TEST_METADATA)
    info = WavInfoReader(str(p))
    assert info.fmt.sample_rate == 44100


def test_invalid_xml_in_ixml(tmp_path):
    """iXML with invalid XML -> discarded, fresh iXML created."""
    p = write_wav(tmp_path, ixml_raw_bytes=b"<not><valid xml", filename="bad_xml.wav")
    write_metadata(str(p), TEST_METADATA)
    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert root is not None
    assert get_user_field(root, "CATEGORY") == "WEATHER"


def test_no_bwfxml_root(tmp_path):
    """iXML with non-BWFXML root -> discarded, fresh iXML created."""
    xml = '<?xml version="1.0"?><OTHER><FOO>bar</FOO></OTHER>'
    p = write_wav(tmp_path, ixml_xml=xml, filename="other_root.wav")
    write_metadata(str(p), TEST_METADATA)
    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert root is not None
    assert root.tag == "BWFXML"
    assert get_user_field(root, "CATEGORY") == "WEATHER"


def test_data_chunk_odd_size(tmp_path):
    """99 samples, 8-bit mono = 99 bytes (odd) -> pad byte correct, frame_count=99."""
    p = write_wav(tmp_path, num_samples=99, bits_per_sample=8, filename="odd.wav")
    info = WavInfoReader(str(p))
    assert info.data.frame_count == 99

    write_metadata(str(p), TEST_METADATA)
    updated = WavInfoReader(str(p))
    assert updated.data.frame_count == 99


def test_readonly_file(tmp_path):
    """Read-only file raises PermissionError."""
    import os
    import pytest

    p = write_wav(tmp_path, filename="readonly.wav")
    os.chmod(str(p), 0o444)
    try:
        with pytest.raises(PermissionError):
            write_metadata(str(p), TEST_METADATA)
    finally:
        os.chmod(str(p), 0o644)


def test_unknown_chunks_preserved(tmp_path):
    """Unknown chunks (cue, smpl, XYZW) are preserved byte-for-byte."""
    cue_data = b"\x01\x00\x00\x00" + b"\x00" * 20  # minimal cue
    smpl_data = b"\x00" * 36  # minimal smpl
    xyzw_data = b"custom chunk data here"
    extra = [
        (b"cue ", cue_data),
        (b"smpl", smpl_data),
        (b"XYZW", xyzw_data),
    ]
    p = write_wav(tmp_path, extra_chunks=extra, filename="extras.wav")
    original = p.read_bytes()
    for cid in (b"cue ", b"smpl", b"XYZW"):
        assert count_chunks(original, cid) == 1

    write_metadata(str(p), TEST_METADATA)
    output = p.read_bytes()
    for cid in (b"cue ", b"smpl", b"XYZW"):
        assert count_chunks(output, cid) == 1

    # Verify XYZW data is byte-for-byte identical
    import struct as st

    pos = 12
    while pos + 8 <= len(output):
        cid = output[pos : pos + 4]
        sz = st.unpack_from("<I", output, pos + 4)[0]
        if cid == b"XYZW":
            assert output[pos + 8 : pos + 8 + sz] == xyzw_data
            break
        pos += 8 + sz + (sz % 2)


# ---------------------------------------------------------------------------
# Regression — release_date not injected when unset
# ---------------------------------------------------------------------------


def test_write_does_not_inject_release_date(tmp_path):
    """Writing metadata without release_date should not auto-inject one."""
    metadata = {"category": "WEATHER", "fx_name": "Thunder Roll"}
    p = write_wav(tmp_path, filename="no_date.wav")
    write_metadata(str(p), metadata)
    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert root is not None
    assert get_user_field(root, "RELEASEDATE") is None


def test_write_preserves_existing_release_date(tmp_path):
    """Writing metadata to a file that already has RELEASEDATE preserves it."""
    ixml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<BWFXML><IXML_VERSION>1.61</IXML_VERSION>"
        "<USER><CATEGORY>AMBIENCE</CATEGORY>"
        "<RELEASEDATE>2024-06-15</RELEASEDATE></USER></BWFXML>"
    )
    p = write_wav(tmp_path, ixml_xml=ixml, filename="has_date.wav")
    write_metadata(str(p), {"category": "WEATHER"})
    info = WavInfoReader(str(p))
    root = parse_ixml_source(info)
    assert get_user_field(root, "RELEASEDATE") == "2024-06-15"


# ---------------------------------------------------------------------------
# LIST-INFO writer tests
# ---------------------------------------------------------------------------


def test_list_info_created_from_metadata(tmp_path):
    """Write metadata → LIST-INFO chunk created with correct sub-chunks."""
    wav = build_wav()
    p = tmp_path / "info_create.wav"
    p.write_bytes(wav)

    write_metadata(str(p), {"fx_name": "Thunder", "designer": "JDOE"})
    meta = read_metadata(str(p))
    assert meta["info"] is not None
    assert meta["info"]["title"] == "Thunder"
    assert meta["info"]["artist"] == "JDOE"


# ---------------------------------------------------------------------------
# verify_write — ASWG field verification
# ---------------------------------------------------------------------------


def test_verify_write_detects_aswg_mismatch(tmp_path):
    """verify_write returns error when ASWG field differs from metadata."""
    from app.metadata.writer import verify_write

    p = write_wav(tmp_path)
    write_metadata(str(p), TEST_METADATA)
    # Verify against wrong cat_id — ASWG catId should mismatch
    wrong = {**TEST_METADATA, "cat_id": "BOGUS_ID"}
    result = verify_write(str(p), wrong)
    assert result["ok"] is False
    assert any("catId" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# verify_write — BEXT originator verification
# ---------------------------------------------------------------------------


def test_verify_write_detects_bext_originator_mismatch(tmp_path):
    """verify_write returns error when BEXT originator differs from metadata."""
    from app.metadata.writer import verify_write

    p = write_wav(tmp_path)
    write_metadata(str(p), TEST_METADATA)
    wrong = {**TEST_METADATA, "designer": "SOMEBODY_ELSE"}
    result = verify_write(str(p), wrong)
    assert result["ok"] is False
    assert any("originator" in e.lower() for e in result["errors"])


# ---------------------------------------------------------------------------
# verify_write — INFO field verification
# ---------------------------------------------------------------------------


def test_verify_write_detects_info_mismatch(tmp_path):
    """verify_write returns error when INFO field differs from metadata."""
    from app.metadata.writer import verify_write

    p = write_wav(tmp_path)
    write_metadata(str(p), TEST_METADATA)
    wrong = {**TEST_METADATA, "library": "WRONGLIB"}
    result = verify_write(str(p), wrong)
    assert result["ok"] is False
    # Must contain an INFO-specific error (IPRD = product tag for library)
    assert any("INFO" in e and "IPRD" in e for e in result["errors"])


# ---------------------------------------------------------------------------
# ASWG-only field round-trip test
# ---------------------------------------------------------------------------


def test_aswg_only_fields_roundtrip(tmp_path):
    """Fields in ASWG_KEY_MAP but not USER_KEY_MAP survive write→read cycle."""
    metadata = {"project": "MyProject", "is_designed": "true"}
    p = write_wav(tmp_path, filename="aswg_only.wav")
    write_metadata(str(p), metadata)

    from app.metadata.reader import read_metadata

    result = read_metadata(str(p))
    assert result["project"] == "MyProject"
    assert result["is_designed"] == "true"


# ---------------------------------------------------------------------------
# LIST-INFO writer tests (continued)
# ---------------------------------------------------------------------------


def test_list_adtl_preserved(tmp_path):
    """Existing LIST-adtl chunk preserved unchanged through write."""
    # Build a fake LIST-adtl chunk
    adtl_data = b"adtl" + b"\x00" * 20
    adtl_chunk = (b"LIST", adtl_data)
    wav = build_wav(extra_chunks=[adtl_chunk])
    p = tmp_path / "adtl_preserve.wav"
    p.write_bytes(wav)

    write_metadata(str(p), {"fx_name": "Test"})

    # Re-read and check LIST chunks
    with open(str(p), "rb") as f:
        raw = f.read()
    # Should have at least one LIST chunk (adtl preserved + maybe INFO created)
    assert raw.count(b"LIST") >= 1
    assert b"adtl" in raw
