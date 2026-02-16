"""Tests for UCS engine — spreadsheet parser + synonym retrieval."""

import pytest

from app.ucs.engine import (
    get_categories,
    get_category_explanation,
    get_catid_info,
    get_subcategories,
    get_synonym_index,
    get_synonyms,
    is_loaded,
    load_ucs,
    lookup_catid,
)

FULL_LIST = "data/UCS/UCS v8.2.1 Full List.xlsx"
TOP_LEVEL = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load():
    load_ucs(FULL_LIST, TOP_LEVEL)


def test_is_loaded():
    assert is_loaded() is True


def test_categories_count():
    cats = get_categories()
    assert len(cats) == 82


def test_categories_sorted():
    cats = get_categories()
    assert cats == sorted(cats)


def test_subcategories_doors():
    subs = get_subcategories("DOORS")
    assert "WOOD" in subs
    assert "METAL" in subs
    assert len(subs) >= 5


def test_subcategories_unknown_returns_empty():
    assert get_subcategories("NONEXISTENT") == []


def test_catid_info_door_wood():
    info = get_catid_info("DOORWood")
    assert info is not None
    assert info.cat_id == "DOORWood"
    assert info.category == "DOORS"
    assert info.subcategory == "WOOD"
    assert info.category_full == "DOORS-WOOD"


def test_catid_info_gun_auto():
    info = get_catid_info("GUNAuto")
    assert info is not None
    assert info.category == "GUNS"
    assert info.subcategory == "AUTOMATIC"


def test_catid_info_air_blow():
    info = get_catid_info("AIRBlow")
    assert info is not None
    assert info.category == "AIR"
    assert info.subcategory == "BLOW"


def test_catid_info_unknown_returns_none():
    assert get_catid_info("INVALID") is None


def test_reverse_lookup():
    cat_id = lookup_catid("DOORS", "WOOD")
    assert cat_id == "DOORWood"


def test_reverse_lookup_unknown():
    assert lookup_catid("NOPE", "NADA") is None


def test_category_explanation_air():
    explanation = get_category_explanation("AIR")
    assert explanation is not None
    assert "air" in explanation.lower()


def test_category_explanation_unknown():
    assert get_category_explanation("NONEXISTENT") is None


def test_synonyms_air_blow():
    syns = get_synonyms("AIRBlow")
    assert len(syns) > 0
    assert "Compressed" in syns


def test_synonyms_unknown():
    assert get_synonyms("INVALID") == []


def test_synonym_index_compressed():
    idx = get_synonym_index()
    results = idx.get("compressed", [])
    assert "AIRBlow" in results


def test_synonym_index_lowercase_keys():
    idx = get_synonym_index()
    for key in idx:
        assert key == key.lower()


def test_cannon_maps_to_gun_cano():
    """'cannon' extra synonym should map to GUNCano."""
    idx = get_synonym_index()
    assert "cannon" in idx
    assert "GUNCano" in idx["cannon"]
