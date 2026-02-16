"""UCS filename utilities — tokenizer, fuzzy matching, parser, generator."""

import re
from dataclasses import dataclass

from app.ucs.engine import CatInfo, get_catid_info, get_synonym_index


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FuzzyMatch:
    """A candidate UCS match for a non-UCS filename."""

    cat_id: str
    category: str
    subcategory: str
    score: int
    matched_terms: list[str]


@dataclass
class ParsedFilename:
    """Result of parsing a filename against UCS convention."""

    is_ucs_compliant: bool
    cat_id: str | None = None
    category: str | None = None
    subcategory: str | None = None
    category_full: str | None = None
    user_category: str | None = None
    fx_name: str | None = None
    vendor_category: str | None = None
    creator_id: str | None = None
    source_id: str | None = None
    user_data: str | None = None
    fuzzy_matches: list[FuzzyMatch] | None = None
    raw_tokens: list[str] | None = None


@dataclass
class GeneratedFilename:
    """Result of generating a UCS-compliant filename."""

    filename: str
    valid: bool
    warnings: list[str]


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

_CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _tokenize_filename(name: str) -> list[str]:
    """Split filename into lowercase tokens, stripping extension."""
    # Strip .wav extension
    if name.lower().endswith(".wav"):
        name = name[:-4]

    # Split camelCase boundaries
    name = _CAMEL_RE.sub("_", name)

    # Split on underscores, hyphens, spaces
    parts = re.split(r"[_\-\s]+", name)

    # Lowercase, deduplicate, filter empty
    seen: set[str] = set()
    tokens: list[str] = []
    for p in parts:
        low = p.lower()
        if low and low not in seen:
            seen.add(low)
            tokens.append(low)

    return tokens


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


def fuzzy_match(filename: str, top_n: int = 5) -> list[FuzzyMatch]:
    """Score each CatID by synonym/name token overlap, return top-N."""
    tokens = _tokenize_filename(filename)
    if not tokens:
        return []

    syn_idx = get_synonym_index()

    # Accumulate scores per CatID
    scores: dict[str, list[str]] = {}

    for token in tokens:
        # Check synonym index
        cat_ids = syn_idx.get(token, [])
        for cid in cat_ids:
            scores.setdefault(cid, []).append(token)

        # Check category/subcategory name matches
        _match_cat_sub_names(token, scores)

    if not scores:
        return []

    # Build results sorted by score desc
    results: list[FuzzyMatch] = []
    for cid, matched in scores.items():
        info = get_catid_info(cid)
        if info is None:
            continue
        results.append(
            FuzzyMatch(
                cat_id=cid,
                category=info.category,
                subcategory=info.subcategory,
                score=len(matched),
                matched_terms=sorted(set(matched)),
            )
        )

    results.sort(key=lambda m: m.score, reverse=True)
    return results[:top_n]


# ---------------------------------------------------------------------------
# Filename parser
# ---------------------------------------------------------------------------


def parse_filename(filename: str) -> ParsedFilename:
    """Parse a filename per UCS convention (06-ucs-filename-convention.md).

    If the first block is a valid CatID, parse UCS fields.
    Otherwise, run fuzzy matching and return non-compliant result.
    """
    stem = filename
    if stem.lower().endswith(".wav"):
        stem = stem[:-4]

    blocks = stem.split("_")
    cat_id_str, user_category = _split_catid_block(blocks[0])

    info = get_catid_info(cat_id_str)
    if info is None:
        return _build_non_ucs_result(filename)

    return _build_ucs_result(info, user_category, blocks)


def _split_catid_block(block: str) -> tuple[str, str | None]:
    """Split block 0 on first '-'. Returns (catid_candidate, user_category)."""
    idx = block.find("-")
    if idx == -1:
        return block, None
    return block[:idx], block[idx + 1 :] or None


def _build_ucs_result(
    info: CatInfo, user_category: str | None, blocks: list[str]
) -> ParsedFilename:
    """Build ParsedFilename from validated CatID and remaining blocks."""
    n = len(blocks)
    fx_name = None
    creator_id = None
    source_id = None
    user_data = None
    vendor_category = None

    if n >= 5:
        fx_name = "_".join(blocks[1 : n - 3])
        creator_id = blocks[n - 3]
        source_id = blocks[n - 2]
        user_data = blocks[n - 1]
    elif n == 4:
        fx_name = blocks[1]
        creator_id = blocks[2]
        source_id = blocks[3]
    elif n == 3:
        fx_name = blocks[1]
        creator_id = blocks[2]
    elif n == 2:
        fx_name = blocks[1]

    # Extract VendorCategory from FXName (text before first '-')
    if fx_name and "-" in fx_name:
        vendor_category = fx_name.split("-", 1)[0]

    return ParsedFilename(
        is_ucs_compliant=True,
        cat_id=info.cat_id,
        category=info.category,
        subcategory=info.subcategory,
        category_full=info.category_full,
        user_category=user_category,
        fx_name=fx_name,
        vendor_category=vendor_category,
        creator_id=creator_id,
        source_id=source_id,
        user_data=user_data,
    )


def _build_non_ucs_result(filename: str) -> ParsedFilename:
    """Build ParsedFilename for non-UCS filenames with fuzzy matches."""
    tokens = _tokenize_filename(filename)
    matches = fuzzy_match(filename)
    return ParsedFilename(
        is_ucs_compliant=False,
        fuzzy_matches=matches if matches else None,
        raw_tokens=tokens if tokens else None,
    )


# ---------------------------------------------------------------------------
# Filename generator
# ---------------------------------------------------------------------------

_ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|]')


def generate_filename(
    cat_id: str,
    fx_name: str | None = None,
    creator_id: str | None = None,
    source_id: str | None = None,
    user_category: str | None = None,
    user_data: str | None = None,
) -> GeneratedFilename:
    """Generate a UCS-compliant filename from metadata fields."""
    from app.services.settings import get_settings

    warnings: list[str] = []

    # Validate CatID
    info = get_catid_info(cat_id)
    if info is None:
        return GeneratedFilename(
            filename=f"{cat_id}_Untitled.wav", valid=False, warnings=["Invalid CatID"]
        )

    # Fall back to settings defaults
    settings = get_settings()
    if not creator_id and settings.creator_id:
        creator_id = settings.creator_id
    if not source_id and settings.source_id:
        source_id = settings.source_id

    # Build CatID block
    catid_block = cat_id
    if user_category:
        catid_block = f"{cat_id}-{user_category}"

    # FXName
    if not fx_name:
        fx_name = "Untitled"
        warnings.append("Missing fx_name, using 'Untitled'")
    if len(fx_name) > 25:
        warnings.append(f"FXName exceeds 25 chars ({len(fx_name)})")

    # Creator/Source warnings
    if not creator_id:
        warnings.append("Missing creator_id")
    if not source_id:
        warnings.append("Missing source_id")

    # Assemble parts
    parts = [catid_block, fx_name]
    if creator_id:
        parts.append(creator_id)
    if source_id:
        parts.append(source_id)
    if user_data:
        parts.append(user_data)

    raw = "_".join(parts) + ".wav"
    filename = _ILLEGAL_CHARS_RE.sub("", raw)

    return GeneratedFilename(filename=filename, valid=True, warnings=warnings)


def render_library_template(
    source_id: str | None = None, library_name: str | None = None
) -> str:
    """Render the library field from settings template and provided values."""
    from collections import defaultdict

    from app.services.settings import get_settings

    template = get_settings().library_template
    defaults = defaultdict(
        str,
        {
            "source_id": source_id or "",
            "library_name": library_name or "",
        },
    )
    result = template.format_map(defaults)
    # Collapse multiple spaces from missing vars
    return " ".join(result.split())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _match_cat_sub_names(token: str, scores: dict[str, list[str]]) -> None:
    """Check if token matches any category or subcategory name (prefix-aware)."""
    if len(token) < 3:
        return
    from app.ucs.engine import get_categories, get_subcategories, lookup_catid

    for cat in get_categories():
        cat_low = cat.lower()
        cat_match = cat_low.startswith(token) or token.startswith(cat_low)
        for sub in get_subcategories(cat):
            sub_low = sub.lower()
            sub_match = sub_low.startswith(token) or token.startswith(sub_low)
            if cat_match or sub_match:
                cid = lookup_catid(cat, sub)
                if cid:
                    scores.setdefault(cid, []).append(token)
