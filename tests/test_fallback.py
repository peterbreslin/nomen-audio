"""Tests for BEXT/INFO fallback — import-time merge + save-time fallback."""

from app.metadata.reader import read_metadata
from app.metadata.writer import write_metadata
from conftest import build_bext_data, build_info_chunk, build_wav


# ---------------------------------------------------------------------------
# Import-time merge tests
# ---------------------------------------------------------------------------


class TestImportFallback:
    def test_bext_description_to_ixml(self, tmp_path):
        """WAV with BEXT description but no iXML → description populated."""
        bext = build_bext_data(description="A thunderstorm recording")
        wav = build_wav(bext_data=bext)
        p = tmp_path / "bext_only.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        # Apply fallback (tested through _apply_import_fallbacks)
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["description"] == "A thunderstorm recording"

    def test_info_title_to_fx_name(self, tmp_path):
        """WAV with INFO INAM but no iXML → fx_name populated."""
        info_chunk = build_info_chunk({b"INAM": "Thunder Rumble"})
        wav = build_wav(extra_chunks=[info_chunk])
        p = tmp_path / "info_title.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["fx_name"] == "Thunder Rumble"

    def test_bext_originator_over_info_artist(self, tmp_path):
        """BEXT originator takes precedence over INFO artist for designer."""
        bext = build_bext_data(originator="BEXT_PERSON")
        info_chunk = build_info_chunk({b"IART": "INFO_PERSON"})
        wav = build_wav(bext_data=bext, extra_chunks=[info_chunk])
        p = tmp_path / "precedence.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["designer"] == "BEXT_PERSON"

    def test_ixml_preserved_over_info(self, tmp_path):
        """If iXML category already set, INFO genre does NOT overwrite."""
        ixml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<BWFXML><USER><CATEGORY>WEATHER</CATEGORY></USER></BWFXML>"
        )
        info_chunk = build_info_chunk({b"IGNR": "DESIGNED"})
        wav = build_wav(ixml_xml=ixml, extra_chunks=[info_chunk])
        p = tmp_path / "no_overwrite.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["category"] == "WEATHER"

    def test_info_comment_to_notes(self, tmp_path):
        """INFO comment → notes when iXML notes empty."""
        info_chunk = build_info_chunk({b"ICMT": "A great recording"})
        wav = build_wav(extra_chunks=[info_chunk])
        p = tmp_path / "info_comment.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["notes"] == "A great recording"

    def test_info_product_to_library(self, tmp_path):
        """INFO product (IPRD) → library when iXML library empty."""
        info_chunk = build_info_chunk({b"IPRD": "My Sound Library"})
        wav = build_wav(extra_chunks=[info_chunk])
        p = tmp_path / "info_product.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["library"] == "My Sound Library"

    def test_info_keywords_to_keywords(self, tmp_path):
        """INFO keywords (IKEY) → keywords when iXML keywords empty."""
        info_chunk = build_info_chunk({b"IKEY": "thunder;storm;rain"})
        wav = build_wav(extra_chunks=[info_chunk])
        p = tmp_path / "info_keywords.wav"
        p.write_bytes(wav)
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["keywords"] == "thunder;storm;rain"


# ---------------------------------------------------------------------------
# Save-time write tests
# ---------------------------------------------------------------------------


class TestSaveFallback:
    def test_save_writes_list_info(self, tmp_path):
        """Save with fx_name → LIST-INFO INAM written."""
        wav = build_wav()
        p = tmp_path / "save_info.wav"
        p.write_bytes(wav)

        write_metadata(str(p), {"fx_name": "Thunder Rumble", "designer": "JDOE"})
        meta = read_metadata(str(p))

        # INFO should now have title and artist
        assert meta["info"] is not None
        assert meta["info"]["title"] == "Thunder Rumble"
        assert meta["info"]["artist"] == "JDOE"

    def test_preserve_existing_info_sub_chunks(self, tmp_path):
        """Existing INFO sub-chunks preserved — fill gaps only (D028)."""
        info_chunk = build_info_chunk(
            {
                b"ISFT": "TestSoftware",
                b"INAM": "Old Name",
            }
        )
        wav = build_wav(extra_chunks=[info_chunk])
        p = tmp_path / "preserve_info.wav"
        p.write_bytes(wav)

        write_metadata(str(p), {"fx_name": "New Name", "designer": "JDOE"})
        meta = read_metadata(str(p))
        assert meta["info"] is not None
        # Existing INAM preserved (fill gaps only)
        assert meta["info"]["title"] == "Old Name"
        # Existing ISFT preserved (not in our write set)
        assert meta["info"]["software"] == "TestSoftware"
        # New IART filled in (was empty gap)
        assert meta["info"]["artist"] == "JDOE"


# ---------------------------------------------------------------------------
# Full roundtrip
# ---------------------------------------------------------------------------


class TestFullRoundtrip:
    def test_import_edit_save_reread(self, tmp_path):
        """Import with BEXT/INFO → edit → save → re-read → verify all chunks."""
        bext = build_bext_data(description="Original BEXT desc")
        info_chunk = build_info_chunk({b"INAM": "Original Title"})
        wav = build_wav(bext_data=bext, extra_chunks=[info_chunk])
        p = tmp_path / "roundtrip.wav"
        p.write_bytes(wav)

        # Import and apply fallback
        meta = read_metadata(str(p))
        from app.routers.files import _apply_import_fallbacks

        meta = _apply_import_fallbacks(meta)
        assert meta["description"] == "Original BEXT desc"
        assert meta["fx_name"] == "Original Title"

        # Save with updated fields
        write_metadata(
            str(p),
            {
                "description": "Updated description",
                "fx_name": "Updated Title",
                "category": "WEATHER",
                "designer": "TESTER",
            },
        )

        # Re-read and verify
        meta2 = read_metadata(str(p))
        assert meta2["description"] == "Updated description"
        assert meta2["fx_name"] == "Updated Title"
        assert meta2["category"] == "WEATHER"
        # BEXT should have updated description
        assert meta2["bext"] is not None
        assert meta2["bext"]["description"] == "Updated description"
        # INFO: existing INAM preserved (fill gaps), new fields filled
        assert meta2["info"] is not None
        assert meta2["info"]["title"] == "Original Title"  # preserved
        assert meta2["info"]["artist"] == "TESTER"  # new gap filled
        assert meta2["info"]["genre"] == "WEATHER"  # new gap filled
