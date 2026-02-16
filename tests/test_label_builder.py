"""Tests for the CLAP label builder."""

import pytest

from app.ucs.engine import get_all_catinfo, is_loaded, load_ucs

# Module-scoped fixture: load real UCS data once
UCS_FULL = "data/UCS/UCS v8.2.1 Full List.xlsx"
UCS_TOP = "data/UCS/UCS v8.2.1 Top Level Categories.xlsx"


@pytest.fixture(scope="module", autouse=True)
def _load_ucs():
    if not is_loaded():
        load_ucs(UCS_FULL, UCS_TOP)


# ---------------------------------------------------------------------------
# get_all_catinfo
# ---------------------------------------------------------------------------


def test_get_all_catinfo_count():
    infos = get_all_catinfo()
    assert len(infos) == 753


def test_get_all_catinfo_has_fields():
    infos = get_all_catinfo()
    info = infos[0]
    assert info.cat_id
    assert info.category
    assert info.subcategory
    assert info.explanation


# ---------------------------------------------------------------------------
# Label builder
# ---------------------------------------------------------------------------


def test_build_labels_count():
    from app.ml.label_builder import build_labels

    labels = build_labels()
    assert len(labels) == 753


def test_build_labels_dual_phrases():
    from app.ml.label_builder import build_labels

    labels = build_labels()
    for entry in labels:
        assert len(entry.phrases) == 2
        # Both use canonical MS-CLAP prefix
        for phrase in entry.phrases:
            assert phrase.startswith("this is the sound of ")


def test_flatten_phrases():
    from app.ml.label_builder import build_labels, flatten_phrases

    labels = build_labels()
    phrases, meta = flatten_phrases(labels)
    assert len(phrases) == len(meta)
    assert len(phrases) == 753 * 2  # two phrases per subcategory (curated + raw)
    assert all("cat_id" in m for m in meta)


def test_compute_labels_hash_deterministic():
    from app.ml.label_builder import build_labels, compute_labels_hash

    labels = build_labels()
    h1 = compute_labels_hash(labels)
    h2 = compute_labels_hash(labels)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# Curated acoustic descriptions (4G)
# ---------------------------------------------------------------------------


def test_load_descriptions_file_exists():
    from app.ml.label_builder import _load_descriptions

    desc = _load_descriptions()
    assert len(desc) == 753
    for cat_id, text in desc.items():
        assert isinstance(text, str)
        assert len(text) > 0, f"Empty description for {cat_id}"


def test_build_labels_uses_curated_descriptions():
    from app.ml.label_builder import _load_descriptions, build_labels

    labels = build_labels()
    desc = _load_descriptions()
    by_catid = {e.cat_id: e for e in labels}
    # First phrase should use curated description
    for cat_id in ["AIRBrst", "WATRSurf", "DSGNBass"]:
        entry = by_catid[cat_id]
        expected_desc = desc[cat_id]
        assert entry.phrases[0] == f"this is the sound of {expected_desc}", (
            f"{cat_id}: got '{entry.phrases[0]}'"
        )


def test_fallback_to_explanation():
    from app.ml.label_builder import _get_description

    # Unknown CatID falls back to the provided fallback text
    result = _get_description("ZZZFake", "some fallback explanation")
    assert result == "some fallback explanation"


def test_curated_descriptions_all_lowercase_start():
    from app.ml.label_builder import _load_descriptions

    desc = _load_descriptions()
    for cat_id, text in desc.items():
        assert text[0].islower(), (
            f"{cat_id} description starts uppercase: '{text[:30]}...'"
        )
