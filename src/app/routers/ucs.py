"""UCS data endpoints — categories, lookup, parse, generate."""

from dataclasses import asdict

from fastapi import APIRouter
from pydantic import BaseModel

from app.errors import AppError, VALIDATION_ERROR

from app.ucs.engine import (
    get_categories,
    get_catid_info,
    get_category_explanation,
    get_subcategories,
    get_synonyms,
    lookup_catid,
)
from app.ucs.filename import generate_filename, parse_filename

router = APIRouter(prefix="/ucs", tags=["ucs"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ParseFilenameRequest(BaseModel):
    filename: str


class GenerateFilenameRequest(BaseModel):
    cat_id: str
    fx_name: str | None = None
    creator_id: str | None = None
    source_id: str | None = None
    user_category: str | None = None
    user_data: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/categories")
def list_categories() -> dict:
    """Full nested category tree for dropdown population."""
    tree = []
    for cat_name in get_categories():
        explanation = get_category_explanation(cat_name) or ""
        subs = []
        for sub_name in get_subcategories(cat_name):
            info = get_catid_info(_lookup_catid(cat_name, sub_name))
            if info is None:
                continue
            subs.append(
                {
                    "name": sub_name,
                    "cat_id": info.cat_id,
                    "category_full": info.category_full,
                    "explanation": info.explanation,
                }
            )
        tree.append(
            {"name": cat_name, "explanation": explanation, "subcategories": subs}
        )
    return {"categories": tree}


@router.get("/lookup/{cat_id}")
def lookup(cat_id: str) -> dict:
    """Details + synonyms for a single CatID."""
    info = get_catid_info(cat_id)
    if info is None:
        raise AppError(VALIDATION_ERROR, 404, f"Unknown CatID: {cat_id}")
    return {
        "cat_id": info.cat_id,
        "category": info.category,
        "subcategory": info.subcategory,
        "category_full": info.category_full,
        "explanation": info.explanation,
        "synonyms": get_synonyms(cat_id),
    }


@router.post("/parse-filename")
def parse(body: ParseFilenameRequest) -> dict:
    """Parse a filename per UCS convention."""
    result = parse_filename(body.filename)
    return asdict(result)


@router.post("/generate-filename")
def generate(body: GenerateFilenameRequest) -> dict:
    """Assemble a UCS-compliant filename from fields."""
    result = generate_filename(
        cat_id=body.cat_id,
        fx_name=body.fx_name,
        creator_id=body.creator_id,
        source_id=body.source_id,
        user_category=body.user_category,
        user_data=body.user_data,
    )
    return asdict(result)


def _lookup_catid(category: str, subcategory: str) -> str | None:
    """Thin wrapper for testability."""
    return lookup_catid(category, subcategory)
