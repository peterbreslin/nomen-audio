"""Tier 1 + Tier 2 suggestion generation from CLAP classification results."""

import re

from app.models import ClassificationMatch, FileRecord, Suggestion, SuggestionsResult
from app.services.settings import get_settings
from app.ucs.engine import get_synonyms
from app.ucs.filename import generate_filename

# Articles to strip from caption when extracting fx_name
_ARTICLES = frozenset({"a", "an", "the", "of", "in", "on", "at", "to", "is", "and"})


def generate_tier1_suggestions(
    classification: list[ClassificationMatch],
    *,
    creator_id: str | None = None,
    source_id: str | None = None,
) -> SuggestionsResult:
    """Generate Tier 1 metadata suggestions from CLAP classification."""
    if not classification:
        return SuggestionsResult()

    top = classification[0]
    conf = top.confidence

    keywords_suggestion = _build_keywords_suggestion(top.cat_id)
    filename_suggestion = _build_filename_suggestion(
        top.cat_id, creator_id=creator_id, source_id=source_id
    )

    return SuggestionsResult(
        category=Suggestion(value=top.category, source="clap", confidence=conf),
        subcategory=Suggestion(value=top.subcategory, source="clap", confidence=conf),
        cat_id=Suggestion(value=top.cat_id, source="clap", confidence=conf),
        category_full=Suggestion(
            value=top.category_full, source="clap", confidence=conf
        ),
        keywords=keywords_suggestion,
        suggested_filename=filename_suggestion,
    )


def enrich_with_caption(
    suggestions: SuggestionsResult, caption: str
) -> SuggestionsResult:
    """Add Tier 2 suggestions from clapcap caption."""
    description = Suggestion(value=caption, source="clapcap", confidence=None)
    fx_name_text = _extract_fx_name(caption)
    fx_name = Suggestion(value=fx_name_text, source="clapcap", confidence=None)

    update: dict = {"description": description, "fx_name": fx_name}

    # Regenerate filename now that fx_name is available
    if suggestions.cat_id:
        update["suggested_filename"] = _build_filename_suggestion(
            suggestions.cat_id.value, fx_name=fx_name_text
        )

    return suggestions.model_copy(update=update)


def _build_keywords_suggestion(cat_id: str) -> Suggestion | None:
    """Build keywords from UCS synonyms for the matched CatID."""
    synonyms = get_synonyms(cat_id)
    if not synonyms:
        return None
    truncated = synonyms[:10]
    return Suggestion(value=", ".join(truncated), source="derived", confidence=None)


def _build_filename_suggestion(
    cat_id: str,
    *,
    fx_name: str | None = None,
    creator_id: str | None = None,
    source_id: str | None = None,
) -> Suggestion | None:
    """Generate a suggested filename from the classified CatID."""
    result = generate_filename(
        cat_id=cat_id, fx_name=fx_name, creator_id=creator_id, source_id=source_id
    )
    return Suggestion(value=result.filename, source="generated", confidence=None)


def hydrate_suggestions(record: FileRecord) -> FileRecord:
    """Regenerate suggestions from stored analysis data (no ML inference).

    Used when loading files from DB that have analysis but no suggestions
    (suggestions are computed at analysis time but not persisted).
    """
    if record.analysis is None:
        return record

    classification = record.analysis.classification
    if not classification:
        return record

    settings = get_settings()
    suggestions = generate_tier1_suggestions(
        classification,
        creator_id=settings.creator_id or None,
        source_id=settings.source_id or None,
    )
    if record.analysis.caption:
        suggestions = enrich_with_caption(suggestions, record.analysis.caption)

    return record.model_copy(update={"suggestions": suggestions})


def _extract_fx_name(caption: str) -> str:
    """Extract a concise FXName from a caption string.

    Takes first 5-6 meaningful words, strips articles, capitalizes.
    """
    words = re.findall(r"[a-zA-Z]+", caption)
    meaningful = [w for w in words if w.lower() not in _ARTICLES]
    selected = meaningful[:6]
    return " ".join(w.capitalize() for w in selected)
