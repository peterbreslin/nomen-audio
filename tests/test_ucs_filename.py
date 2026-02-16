"""Tests for UCS filename module — fuzzy matching, parser, generator."""

from unittest.mock import patch

import pytest

from app.ucs.engine import load_ucs
from app.services.settings import AppSettings, load_settings, update_settings
from app.ucs.filename import (
    FuzzyMatch,
    fuzzy_match,
    generate_filename,
    parse_filename,
    render_library_template,
    _tokenize_filename,
)

FULL_LIST = "data/UCS/UCS v8.2.1 Full List.xlsx"
TOP_LEVEL = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load():
    load_ucs(FULL_LIST, TOP_LEVEL)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_underscore_split(self):
        tokens = _tokenize_filename("wooden_door_creak")
        assert tokens == ["wooden", "door", "creak"]

    def test_camel_case(self):
        tokens = _tokenize_filename("CabinDoorCreak")
        assert "cabin" in tokens
        assert "door" in tokens
        assert "creak" in tokens

    def test_strips_extension(self):
        tokens = _tokenize_filename("wooden_door_creak.wav")
        assert "wav" not in tokens
        assert "wooden" in tokens

    def test_hyphen_split(self):
        tokens = _tokenize_filename("wood-door-open")
        assert tokens == ["wood", "door", "open"]

    def test_deduplicates(self):
        tokens = _tokenize_filename("door_door_open")
        assert tokens.count("door") == 1


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


class TestFuzzyMatch:
    def test_wooden_door_creak(self):
        matches = fuzzy_match("wooden_door_creak.wav")
        cat_ids = [m.cat_id for m in matches]
        assert "DOORWood" in cat_ids

    def test_no_matches_gibberish(self):
        matches = fuzzy_match("xyz123.wav")
        assert matches == []

    def test_returns_fuzzy_match_objects(self):
        matches = fuzzy_match("wooden_door_creak.wav")
        assert all(isinstance(m, FuzzyMatch) for m in matches)
        for m in matches:
            assert m.score > 0
            assert len(m.matched_terms) > 0

    def test_top_n_limit(self):
        matches = fuzzy_match("heavy rain metal roof.wav", top_n=3)
        assert len(matches) <= 3

    def test_sorted_by_score_desc(self):
        matches = fuzzy_match("wooden_door_creak.wav")
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Filename parser
# ---------------------------------------------------------------------------


class TestParseFilename:
    def test_basic_four_block(self):
        """DOORWood_Cabin Door Open Close_JDOE_MYGAME.wav"""
        r = parse_filename("DOORWood_Cabin Door Open Close_JDOE_MYGAME.wav")
        assert r.is_ucs_compliant is True
        assert r.cat_id == "DOORWood"
        assert r.category == "DOORS"
        assert r.subcategory == "WOOD"
        assert r.category_full == "DOORS-WOOD"
        assert r.fx_name == "Cabin Door Open Close"
        assert r.creator_id == "JDOE"
        assert r.source_id == "MYGAME"

    def test_with_user_category(self):
        """GUNAuto-EXT_UZI 9mm-Rapid Fire_TN_DORY.wav"""
        r = parse_filename("GUNAuto-EXT_UZI 9mm-Rapid Fire_TN_DORY.wav")
        assert r.is_ucs_compliant is True
        assert r.cat_id == "GUNAuto"
        assert r.user_category == "EXT"
        assert r.fx_name == "UZI 9mm-Rapid Fire"
        assert r.creator_id == "TN"
        assert r.source_id == "DORY"

    def test_with_user_data(self):
        """GUNAuto_Uzi 9mm_TN_DORY_SM57.wav — 5 blocks"""
        r = parse_filename("GUNAuto_Uzi 9mm_TN_DORY_SM57.wav")
        assert r.is_ucs_compliant is True
        assert r.fx_name == "Uzi 9mm"
        assert r.creator_id == "TN"
        assert r.source_id == "DORY"
        assert r.user_data == "SM57"

    def test_with_vendor_category(self):
        """GUNAuto_Remington870-Single Shot_TN_DORY.wav"""
        r = parse_filename("GUNAuto_Remington870-Single Shot_TN_DORY.wav")
        assert r.is_ucs_compliant is True
        assert r.vendor_category == "Remington870"
        assert r.fx_name == "Remington870-Single Shot"

    def test_minimal_two_block(self):
        """DOORWood_Cabin Door.wav — only CatID + FXName"""
        r = parse_filename("DOORWood_Cabin Door.wav")
        assert r.is_ucs_compliant is True
        assert r.cat_id == "DOORWood"
        assert r.fx_name == "Cabin Door"
        assert r.creator_id is None
        assert r.source_id is None

    def test_non_ucs_filename(self):
        """wooden_door_creak.wav → not compliant, has fuzzy matches"""
        r = parse_filename("wooden_door_creak.wav")
        assert r.is_ucs_compliant is False
        assert r.cat_id is None
        assert r.fuzzy_matches is not None
        assert len(r.fuzzy_matches) > 0
        assert r.raw_tokens is not None

    def test_catid_only(self):
        """DOORWood.wav — just a CatID, no other blocks"""
        r = parse_filename("DOORWood.wav")
        assert r.is_ucs_compliant is True
        assert r.cat_id == "DOORWood"
        assert r.fx_name is None

    def test_three_block(self):
        """DOORWood_Cabin Door Open_JDOE.wav — 3 blocks"""
        r = parse_filename("DOORWood_Cabin Door Open_JDOE.wav")
        assert r.is_ucs_compliant is True
        assert r.fx_name == "Cabin Door Open"
        assert r.creator_id == "JDOE"
        assert r.source_id is None


# ---------------------------------------------------------------------------
# Filename generator
# ---------------------------------------------------------------------------


class TestGenerateFilename:
    def test_basic_four_block(self):
        r = generate_filename(
            cat_id="DOORWood",
            fx_name="Cabin Door Open Close",
            creator_id="JDOE",
            source_id="MYGAME",
        )
        assert r.filename == "DOORWood_Cabin Door Open Close_JDOE_MYGAME.wav"
        assert r.valid is True
        assert r.warnings == []

    def test_with_user_category(self):
        r = generate_filename(
            cat_id="GUNAuto",
            fx_name="Rapid Fire",
            creator_id="TN",
            source_id="DORY",
            user_category="EXT",
        )
        assert r.filename == "GUNAuto-EXT_Rapid Fire_TN_DORY.wav"

    def test_with_user_data(self):
        r = generate_filename(
            cat_id="GUNAuto",
            fx_name="Uzi 9mm",
            creator_id="TN",
            source_id="DORY",
            user_data="SM57",
        )
        assert r.filename == "GUNAuto_Uzi 9mm_TN_DORY_SM57.wav"

    def test_long_fx_name_warning(self):
        r = generate_filename(
            cat_id="DOORWood",
            fx_name="A" * 30,
            creator_id="JDOE",
            source_id="MYGAME",
        )
        assert r.valid is True
        assert any("25" in w for w in r.warnings)

    def test_missing_creator_id_warning(self):
        with patch("app.services.settings.get_settings", return_value=AppSettings()):
            r = generate_filename(cat_id="DOORWood", fx_name="Cabin Door")
        assert r.valid is True
        assert any("creator_id" in w for w in r.warnings)

    def test_illegal_chars_sanitized(self):
        r = generate_filename(
            cat_id="DOORWood",
            fx_name='Door: "Open" <Close>',
            creator_id="JDOE",
            source_id="MYGAME",
        )
        assert ":" not in r.filename
        assert '"' not in r.filename
        assert "<" not in r.filename

    def test_invalid_cat_id(self):
        r = generate_filename(cat_id="INVALID", fx_name="Test")
        assert r.valid is False

    def test_missing_fx_name_uses_untitled(self):
        r = generate_filename(cat_id="DOORWood", creator_id="JDOE", source_id="MYGAME")
        assert "Untitled" in r.filename


# ---------------------------------------------------------------------------
# Settings integration
# ---------------------------------------------------------------------------


class TestGeneratorWithSettings:
    @pytest.fixture(autouse=True)
    def _fresh_settings(self, tmp_path):
        path = tmp_path / "settings.json"
        load_settings(str(path))

    def test_settings_creator_id_default(self):
        update_settings({"creator_id": "ABC"})
        r = generate_filename(cat_id="DOORWood", fx_name="Test", source_id="SRC")
        assert "ABC" in r.filename

    def test_settings_source_id_default(self):
        update_settings({"source_id": "MYLIB"})
        r = generate_filename(cat_id="DOORWood", fx_name="Test", creator_id="JD")
        assert "MYLIB" in r.filename

    def test_explicit_overrides_settings(self):
        update_settings({"creator_id": "DEFAULT"})
        r = generate_filename(
            cat_id="DOORWood", fx_name="Test", creator_id="EXPLICIT", source_id="SRC"
        )
        assert "EXPLICIT" in r.filename
        assert "DEFAULT" not in r.filename


class TestLibraryTemplate:
    @pytest.fixture(autouse=True)
    def _fresh_settings(self, tmp_path):
        path = tmp_path / "settings.json"
        load_settings(str(path))

    def test_both_vars(self):
        result = render_library_template(source_id="SRC", library_name="MyLib")
        assert result == "SRC MyLib"

    def test_missing_source_id(self):
        result = render_library_template(source_id=None, library_name="MyLib")
        assert result.strip() == "MyLib"

    def test_custom_template(self):
        update_settings({"library_template": "{library_name} [{source_id}]"})
        result = render_library_template(source_id="SRC", library_name="MyLib")
        assert result == "MyLib [SRC]"
