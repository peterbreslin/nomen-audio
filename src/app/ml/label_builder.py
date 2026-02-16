"""Build CLAP text labels from UCS engine data for zero-shot classification."""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from importlib import resources

from app.ucs.engine import get_all_catinfo

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LabelEntry:
    """A UCS subcategory with its CLAP text phrases."""

    cat_id: str
    category: str
    subcategory: str
    phrases: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Curated acoustic descriptions (D053)
# ---------------------------------------------------------------------------

_descriptions_cache: dict[str, str] | None = None


def _load_descriptions() -> dict[str, str]:
    """Load curated acoustic descriptions from JSON, cached at module level."""
    global _descriptions_cache
    if _descriptions_cache is not None:
        return _descriptions_cache
    pkg = resources.files("app.ml")
    data = json.loads(pkg.joinpath("acoustic_descriptions.json").read_text("utf-8"))
    _descriptions_cache = data["descriptions"]
    logger.info("Loaded %d curated acoustic descriptions", len(_descriptions_cache))
    return _descriptions_cache


def _get_description(cat_id: str, fallback: str) -> str:
    """Look up curated description for a CatID, falling back to explanation."""
    desc = _load_descriptions()
    return desc.get(cat_id, fallback)


# ---------------------------------------------------------------------------
# Label building
# ---------------------------------------------------------------------------


_PROMPT_PREFIX = "this is the sound of "


def build_labels() -> list[LabelEntry]:
    """Build CLAP text labels for all UCS subcategories.

    Two phrases per subcategory (D054 dual-label mean-pooling):
      1. Curated acoustic description (D053)
      2. Raw UCS explanation (broader coverage)
    Both use the canonical MS-CLAP prefix "this is the sound of".
    When curated == raw (unknown CatID fallback), deduplicates to one phrase.
    """
    entries: list[LabelEntry] = []
    for info in get_all_catinfo():
        curated = _get_description(info.cat_id, info.explanation)
        phrases = [f"{_PROMPT_PREFIX}{curated}"]
        if curated != info.explanation:
            phrases.append(f"{_PROMPT_PREFIX}{info.explanation}")
        entries.append(
            LabelEntry(
                cat_id=info.cat_id,
                category=info.category,
                subcategory=info.subcategory,
                phrases=phrases,
            )
        )
    return entries


def flatten_phrases(labels: list[LabelEntry]) -> tuple[list[str], list[dict]]:
    """Flatten label entries into parallel lists of phrases and metadata.

    Returns:
        (phrases, meta) where meta[i] maps to phrases[i] with keys:
        cat_id, category, subcategory.
    """
    phrases: list[str] = []
    meta: list[dict] = []
    for entry in labels:
        for phrase in entry.phrases:
            phrases.append(phrase)
            meta.append(
                {
                    "cat_id": entry.cat_id,
                    "category": entry.category,
                    "subcategory": entry.subcategory,
                }
            )
    return phrases, meta


def compute_labels_hash(labels: list[LabelEntry]) -> str:
    """SHA-256 of sorted phrases for cache invalidation."""
    all_phrases = sorted(p for entry in labels for p in entry.phrases)
    content = "\n".join(all_phrases).encode("utf-8")
    return hashlib.sha256(content).hexdigest()
