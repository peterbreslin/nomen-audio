"""Analysis endpoints — single file and batch (SSE)."""

import asyncio
import json
import logging
import math
import time
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.errors import AppError, FILE_NOT_FOUND, MODEL_NOT_READY

from app.db.repository import (
    get_all_files,
    get_cached_analysis,
    get_cached_llm_pick,
    get_file,
    store_cached_analysis,
    store_cached_llm_pick,
    update_file,
)
from app.ml import model_manager
from app.ml.suggestions import enrich_with_caption, generate_tier1_suggestions
from app.services.flagging import should_flag
from app.services.settings import get_settings
from app.models import (
    AnalysisResult,
    AnalyzeRequest,
    BatchAnalyzeRequest,
    ClassificationMatch,
    FileRecord,
)
from app.db.mappers import dict_to_file_record
from app.llm.prompt_renderer import load_prompt
from app.metadata.reader import read_descriptive_metadata, read_structured_metadata
from app.ucs.filename import fuzzy_match

logger = logging.getLogger(__name__)

# Number of CLAP candidates to cache — large enough for filename re-ranking
# to pull correct CatIDs from deeper ranks.
_CLAP_CANDIDATES = 50

# Filename keyword boost weight (D056). At alpha=10, keywords dominate ranking
# with CLAP as acoustic tiebreaker within keyword-matched candidates.
_FILENAME_ALPHA = 10.0

# Minimum keyword match score to apply boost (prevents spurious single-token boosts).
_FILENAME_MIN_SCORE = 2

# Display weight for keyword evidence in blended confidence.
# At alpha=2.0, a full keyword match roughly doubles the log-odds.
_DISPLAY_ALPHA = 2.0

router = APIRouter(prefix="/files", tags=["analysis"])


# ---------------------------------------------------------------------------
# Batch analysis (SSE) — MUST be before /{file_id} parameterized route
# ---------------------------------------------------------------------------


@router.post("/analyze-batch")
async def analyze_batch(req: BatchAnalyzeRequest):
    """Analyze multiple files with SSE streaming progress."""
    if not model_manager.is_ready():
        raise AppError(MODEL_NOT_READY, 503, "Models still loading")

    if req.file_ids:
        rows = [await get_file(fid) for fid in req.file_ids]
        rows = [r for r in rows if r is not None]
    else:
        rows = await get_all_files()

    analyze_req = AnalyzeRequest(tiers=req.tiers, force=req.force)
    return StreamingResponse(
        _stream_analysis(rows, analyze_req),
        media_type="text/event-stream",
    )


# ---------------------------------------------------------------------------
# Single file analysis
# ---------------------------------------------------------------------------


@router.post("/{file_id}/analyze", response_model=FileRecord)
async def analyze_file(file_id: str, req: AnalyzeRequest) -> FileRecord:
    """Analyze a single file with CLAP classification (+ optional captioning)."""
    if not model_manager.is_ready():
        raise AppError(MODEL_NOT_READY, 503, "Models still loading")

    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, "File not found")

    classification, caption = await _run_analysis(row, req)
    settings = get_settings()
    suggestions = generate_tier1_suggestions(
        classification,
        creator_id=settings.creator_id or None,
        source_id=settings.source_id or None,
    )
    if caption and 2 in req.tiers:
        suggestions = enrich_with_caption(suggestions, caption)

    analysis = AnalysisResult(
        classification=classification,
        caption=caption,
        model_version="2023",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )

    analysis_dict = json.loads(analysis.model_dump_json())
    prefill = _build_prefill_updates(row, settings)
    db_updates: dict = {"analysis": analysis_dict, **prefill}
    if should_flag(classification=classification, category=row.get("category")):
        db_updates["status"] = "flagged"
    await update_file(file_id, db_updates)

    row = await get_file(file_id)
    record = dict_to_file_record(row)
    record.suggestions = suggestions
    return record


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _build_prefill_updates(row: dict, settings) -> dict:
    """Build metadata updates to pre-fill from settings (D064).

    Only fills fields that are currently empty in the file record.
    """
    updates = {}
    if settings.creator_id and not row.get("creator_id"):
        updates["creator_id"] = settings.creator_id
    if settings.source_id and not row.get("source_id"):
        updates["source_id"] = settings.source_id
    return updates


def apply_filename_boost(
    classification: list[ClassificationMatch],
    filename: str | None,
    top_n: int = 5,
    metadata: dict[str, str] | None = None,
) -> list[ClassificationMatch]:
    """Re-rank classification results using filename + metadata keyword overlap.

    Originally D056 (filename-only). Phase 2 Path A extends the token pool with
    embedded iXML/BEXT/INFO descriptive fields when ``metadata`` is supplied.

    Returns the top *top_n* results sorted by combined score. Confidences are
    renormalized to sum to ~1.0 for display purposes.
    """
    if not filename:
        return _renormalize_confidence(classification[:top_n])

    extra_text = " ".join(str(v) for v in metadata.values()) if metadata else None
    matches = fuzzy_match(filename, top_n=50, extra_text=extra_text)
    if not matches or matches[0].score < _FILENAME_MIN_SCORE:
        return _renormalize_confidence(classification[:top_n])

    max_score = matches[0].score
    boost_map = {m.cat_id: m.score / max_score for m in matches}

    scored = [
        (r, r.confidence + _FILENAME_ALPHA * boost_map.get(r.cat_id, 0.0))
        for r in classification
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [r for r, _ in scored[:top_n]]
    blended = _blend_confidence(top, boost_map)
    blended.sort(key=lambda m: m.confidence, reverse=True)
    return blended


def _renormalize_confidence(
    matches: list[ClassificationMatch],
) -> list[ClassificationMatch]:
    """Renormalize confidences to sum to 1.0 (conditional probability over top-N)."""
    total = sum(m.confidence for m in matches)
    if total <= 0:
        return matches
    result = [
        m.model_copy(update={"confidence": m.confidence / total}) for m in matches
    ]
    result.sort(key=lambda m: m.confidence, reverse=True)
    return result


def _blend_confidence(
    matches: list[ClassificationMatch],
    boost_map: dict[str, float],
) -> list[ClassificationMatch]:
    """Blend CLAP and keyword scores into display confidence via log-space softmax."""
    logits = [
        math.log(max(m.confidence, 1e-10))
        + _DISPLAY_ALPHA * boost_map.get(m.cat_id, 0.0)
        for m in matches
    ]
    max_logit = max(logits) if logits else 0.0
    exps = [math.exp(lg - max_logit) for lg in logits]
    total = sum(exps)
    return [
        m.model_copy(update={"confidence": e / total}) for m, e in zip(matches, exps)
    ]


async def _run_analysis(
    row: dict, req: AnalyzeRequest
) -> tuple[list[ClassificationMatch], str | None]:
    """Run classification (+ optional captioning), using cache when available.

    The cache stores raw CLAP results (top _CLAP_CANDIDATES, no boost). The
    filename + metadata boost is always applied fresh so results reflect the
    current filename and embedded metadata even after renames or edits. When
    ``llm_rerank_enabled`` and the LLM provider is loaded, the top-1 of the
    boosted list is replaced by the LLM's pick from the top-10.
    """
    file_hash = row["file_hash"]
    file_path = row["path"]
    filename = row.get("filename")
    metadata = read_structured_metadata(file_path)
    descriptive_metadata = read_descriptive_metadata(file_path)

    cached_classification: list[ClassificationMatch] | None = None
    caption: str | None = None
    if not req.force:
        cached = await get_cached_analysis(file_hash)
        if cached is not None:
            cached_classification = [
                ClassificationMatch(**m) for m in json.loads(cached["classification"])
            ]
            caption = cached.get("caption")

    if cached_classification is None:
        classifier = model_manager.get_classifier()
        cached_classification = await asyncio.to_thread(
            classifier.classify, file_path, _CLAP_CANDIDATES
        )
        if 2 in req.tiers:
            captioner = model_manager.get_captioner()
            caption = await asyncio.to_thread(captioner.caption, file_path)
        cls_json = json.dumps([m.model_dump() for m in cached_classification])
        await store_cached_analysis(file_hash, cls_json, caption, "2023")

    boosted = apply_filename_boost(
        cached_classification, filename, metadata=metadata
    )
    reranked = await _apply_llm_rerank(
        boosted, filename, descriptive_metadata, file_hash, force=req.force
    )
    return reranked, caption


async def _apply_llm_rerank(
    boosted: list[ClassificationMatch],
    filename: str | None,
    descriptive_metadata: dict[str, str],
    file_hash: str,
    *,
    force: bool,
) -> list[ClassificationMatch]:
    """If the setting is on and the LLM is loaded, promote its pick to top-1.

    Soft failure: any unavailability (setting off, model not downloaded, load
    failed) returns the boosted list unchanged. Result is cached by
    (file_hash, prompt_version, model_version); ``force=True`` bypasses cache.
    """
    if not get_settings().llm_rerank_enabled:
        return boosted
    if not filename or not boosted:
        return boosted
    provider = model_manager.get_llm_provider()
    if provider is None:
        return boosted

    prompt = load_prompt()
    if not force:
        cached = await get_cached_llm_pick(
            file_hash, prompt.version, provider.model_version
        )
        if cached is not None:
            return _promote_to_top1(boosted, cached["chosen_cat_id"])

    candidates = boosted[: prompt.candidates_n]
    try:
        result = await asyncio.to_thread(
            provider.pick,
            filename=filename,
            metadata=descriptive_metadata,
            candidates=candidates,
        )
    except Exception:
        logger.exception("LLM rerank failed; using CLAP+boost result")
        return boosted

    await store_cached_llm_pick(
        file_hash=file_hash,
        prompt_version=prompt.version,
        model_version=provider.model_version,
        chosen_cat_id=result.cat_id,
        retried=result.retried,
        fallback_to_clap_top1=result.fallback_to_clap_top1,
        latency_ms=result.latency_ms,
    )
    return _promote_to_top1(boosted, result.cat_id)


def _promote_to_top1(
    ordered: list[ClassificationMatch], chosen_cat_id: str
) -> list[ClassificationMatch]:
    """Move the match with ``chosen_cat_id`` to position 0, preserve rest."""
    for i, m in enumerate(ordered):
        if m.cat_id == chosen_cat_id:
            if i == 0:
                return ordered
            return [m, *ordered[:i], *ordered[i + 1 :]]
    return ordered


async def _analyze_single_for_batch(row: dict, req: AnalyzeRequest) -> dict:
    """Analyze one file and return the SSE result payload."""
    file_id = row["id"]
    classification, caption = await _run_analysis(row, req)
    settings = get_settings()
    suggestions = generate_tier1_suggestions(
        classification,
        creator_id=settings.creator_id or None,
        source_id=settings.source_id or None,
    )
    if caption and 2 in req.tiers:
        suggestions = enrich_with_caption(suggestions, caption)

    analysis = AnalysisResult(
        classification=classification,
        caption=caption,
        model_version="2023",
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    analysis_dict = json.loads(analysis.model_dump_json())
    prefill = _build_prefill_updates(row, settings)
    db_updates: dict = {"analysis": analysis_dict, **prefill}
    if should_flag(classification=classification, category=row.get("category")):
        db_updates["status"] = "flagged"
    await update_file(file_id, db_updates)

    updated = await get_file(file_id)
    record = dict_to_file_record(updated)
    record.suggestions = suggestions
    return {
        "file_id": file_id,
        "success": True,
        "file": json.loads(record.model_dump_json()),
    }


async def _stream_analysis(
    rows: list[dict], req: AnalyzeRequest
) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE events for batch analysis."""
    total = len(rows)
    analyzed = 0
    failed = 0
    start = time.monotonic()

    for i, row in enumerate(rows):
        await asyncio.sleep(0)
        file_id = row["id"]

        yield _sse_event(
            "progress",
            {
                "file_id": file_id,
                "filename": row["filename"],
                "current": i + 1,
                "total": total,
                "status": "analyzing",
            },
        )

        try:
            result = await _analyze_single_for_batch(row, req)
            yield _sse_event("result", result)
            analyzed += 1
        except Exception as e:
            logger.exception("Batch analysis failed for %s", file_id)
            yield _sse_event(
                "error", {"file_id": file_id, "success": False, "error": str(e)}
            )
            failed += 1

    elapsed_ms = int((time.monotonic() - start) * 1000)
    yield _sse_event(
        "complete",
        {
            "analyzed_count": analyzed,
            "failed_count": failed,
            "total_time_ms": elapsed_ms,
        },
    )


def _sse_event(event: str, data: dict) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
