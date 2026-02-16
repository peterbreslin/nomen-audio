"""File import and retrieval endpoints."""

import errno
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.errors import (
    AppError,
    DISK_FULL,
    FILE_CHANGED,
    FILE_LOCKED,
    FILE_NOT_FOUND,
    FILE_READ_ONLY,
    RENAME_CONFLICT,
    VALIDATION_ERROR,
)

from app.db.mappers import dict_to_file_record
from app.db.repository import (
    delete_files_by_paths,
    get_all_files,
    get_cached_analysis,
    get_file,
    get_file_by_path,
    update_file,
    upsert_file,
)
from app.metadata.reader import compute_file_hash, read_metadata
from app.metadata.writer import verify_write, write_metadata
from app.models import (
    AnalysisResult,
    ApplyMetadataRequest,
    ApplyMetadataResponse,
    BatchSaveRequest,
    BatchSaveResponse,
    BatchSaveResult,
    BatchUpdateRequest,
    BatchUpdateResponse,
    ClassificationMatch,
    FileRecord,
    ImportRequest,
    ImportResponse,
    MetadataUpdate,
    SaveRequest,
    SaveResponse,
)
from app.ml.suggestions import hydrate_suggestions
from app.routers.analysis import apply_filename_boost
from app.services.flagging import should_flag

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/files", tags=["files"])


@router.post("/import", response_model=ImportResponse)
async def import_files(req: ImportRequest) -> ImportResponse:
    """Scan a directory for WAV files, read metadata, store in DB."""
    directory = Path(req.directory)
    if not directory.is_dir():
        raise AppError(VALIDATION_ERROR, 422, f"Not a directory: {req.directory}")

    start = time.monotonic()

    # Discover WAV files
    pattern = "**/*.wav" if req.recursive else "*.wav"
    wav_paths = sorted(directory.glob(pattern))

    records: list[FileRecord] = []
    skipped_paths: list[str] = []
    seen_paths: set[str] = set()

    for wav_path in wav_paths:
        abs_path = str(wav_path.resolve())
        seen_paths.add(abs_path)
        try:
            record = await _import_single_file(wav_path, abs_path)
            records.append(record)
        except Exception:
            logger.warning("Skipping unreadable file: %s", abs_path, exc_info=True)
            skipped_paths.append(abs_path)

    # Remove stale records from this directory
    await _remove_stale_records(str(directory.resolve()), seen_paths)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    return ImportResponse(
        files=records,
        count=len(records),
        skipped=len(skipped_paths),
        skipped_paths=skipped_paths,
        import_time_ms=elapsed_ms,
    )


@router.get("", response_model=dict)
async def list_files(
    status: str | None = None,
    category: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 1000,
) -> dict:
    """List all file records with optional filters."""
    rows = await get_all_files(
        status=status, category=category, search=search, offset=offset, limit=limit
    )
    files = [hydrate_suggestions(dict_to_file_record(r)) for r in rows]
    return {"files": files, "count": len(files)}


@router.post("/save-batch", response_model=BatchSaveResponse)
async def save_batch(body: BatchSaveRequest) -> BatchSaveResponse:
    """Save multiple files in sequence, collecting per-file results."""
    results: list[BatchSaveResult] = []
    for fid in body.file_ids:
        try:
            resp = await save_file(fid, SaveRequest(rename=body.rename))
            results.append(
                BatchSaveResult(
                    id=fid,
                    success=True,
                    renamed=resp.renamed,
                    new_path=resp.new_path,
                )
            )
        except AppError as e:
            results.append(BatchSaveResult(id=fid, success=False, error=e.detail))
        except Exception as e:
            results.append(BatchSaveResult(id=fid, success=False, error=str(e)))
    saved = sum(1 for r in results if r.success)
    return BatchSaveResponse(
        results=results, saved_count=saved, failed_count=len(results) - saved
    )


@router.post("/apply-metadata", response_model=ApplyMetadataResponse)
async def apply_metadata(body: ApplyMetadataRequest) -> ApplyMetadataResponse:
    """Copy metadata fields from source file to target files (in-memory only)."""
    source = await get_file(body.source_id)
    if source is None:
        raise AppError(FILE_NOT_FOUND, 404, f"Source not found: {body.source_id}")

    # Validate field names
    invalid = set(body.fields) - set(_META_KEYS)
    if invalid:
        raise AppError(VALIDATION_ERROR, 422, f"Invalid fields: {invalid}")

    # Extract source values for requested fields
    field_values = {f: source.get(f) for f in body.fields}

    results: list[FileRecord] = []
    for target_id in body.target_ids:
        target = await get_file(target_id)
        if target is None:
            continue
        existing_changed = set(target.get("changed_fields") or [])
        new_changed = existing_changed | set(body.fields)
        updates = {
            **field_values,
            "status": "modified",
            "changed_fields": sorted(new_changed),
        }
        await update_file(target_id, updates)
        updated = await get_file(target_id)
        results.append(dict_to_file_record(updated))

    return ApplyMetadataResponse(updated=results, count=len(results))


@router.post("/batch-update", response_model=BatchUpdateResponse)
async def batch_update(body: BatchUpdateRequest) -> BatchUpdateResponse:
    """Set arbitrary metadata values on multiple files (D060)."""
    invalid = set(body.updates.keys()) - set(_META_KEYS)
    if invalid:
        raise AppError(VALIDATION_ERROR, 422, f"Invalid fields: {invalid}")

    results: list[FileRecord] = []
    for file_id in body.file_ids:
        row = await get_file(file_id)
        if row is None:
            logger.warning("batch-update: file %s not found, skipping", file_id)
            continue
        existing_changed = set(row.get("changed_fields") or [])
        new_changed = existing_changed | set(body.updates.keys())
        updates = {
            **body.updates,
            "status": "modified",
            "changed_fields": sorted(new_changed),
        }
        await update_file(file_id, updates)
        updated = await get_file(file_id)
        results.append(dict_to_file_record(updated))

    return BatchUpdateResponse(updated=results, count=len(results))


@router.get("/{file_id}", response_model=FileRecord)
async def get_file_by_id(file_id: str) -> FileRecord:
    """Get a single file record by ID."""
    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, f"File not found: {file_id}")
    return hydrate_suggestions(dict_to_file_record(row))


@router.put("/{file_id}/metadata", response_model=FileRecord)
async def update_metadata(file_id: str, body: MetadataUpdate) -> FileRecord:
    """Update metadata fields for a file. Partial update semantics."""
    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, f"File not found: {file_id}")

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        return dict_to_file_record(row)

    # Merge custom_fields (union, not replace)
    if "custom_fields" in changes and changes["custom_fields"] is not None:
        existing_cf = row.get("custom_fields") or {}
        merged_cf = {**existing_cf, **changes["custom_fields"]}
        changes["custom_fields"] = merged_cf

    # Accumulate changed fields
    existing_changed = set(row.get("changed_fields") or [])
    new_changed = existing_changed | set(changes.keys())
    changes["changed_fields"] = sorted(new_changed)

    # Recompute flag status: if flagged file now has valid category, clear flag
    changes["status"] = _compute_status_after_edit(row, changes)

    # Regenerate suggested_filename when constituent fields change
    _maybe_regen_filename(row, changes)

    await update_file(file_id, changes)

    updated = await get_file(file_id)
    return dict_to_file_record(updated)


@router.post("/{file_id}/save", response_model=SaveResponse)
async def save_file(file_id: str, body: SaveRequest = SaveRequest()) -> SaveResponse:
    """Write metadata to disk and optionally rename the file."""
    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, f"File not found: {file_id}")

    old_path = row["path"]
    file_path = Path(old_path)
    if not file_path.is_file():
        raise AppError(FILE_NOT_FOUND, 404, "File missing on disk")

    # Hash check for external modification
    current_hash = compute_file_hash(old_path)
    if current_hash != row["file_hash"]:
        raise AppError(FILE_CHANGED, 409, "File modified externally")

    # --- Save as Copy branch ---
    if body.save_copy:
        return await _save_as_copy(row, body, old_path)

    # Check rename before writing metadata (D015)
    will_rename, target_path = _check_rename(body, row)

    # Collect metadata to write
    metadata = {k: row[k] for k in _META_KEYS if row.get(k) is not None}
    if row.get("custom_fields"):
        metadata["custom_fields"] = row["custom_fields"]

    if not os.access(old_path, os.W_OK):
        raise AppError(FILE_READ_ONLY, 403, f"File is read-only: {old_path}")

    try:
        write_metadata(old_path, metadata)
    except PermissionError:
        raise AppError(FILE_LOCKED, 409, f"File is locked: {old_path}")
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise AppError(DISK_FULL, 507, "Not enough disk space")
        raise

    result = verify_write(old_path, metadata)
    if not result["ok"]:
        raise AppError(
            "WRITE_FAILED", 500, f"Write verification failed: {result['errors']}"
        )

    return await _finalize_save(file_id, old_path, target_path, will_rename)


@router.post("/{file_id}/revert", response_model=FileRecord)
async def revert_file(file_id: str) -> FileRecord:
    """Discard in-memory changes by re-reading metadata from disk."""
    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, f"File not found: {file_id}")

    file_path = Path(row["path"])
    if not file_path.is_file():
        raise AppError(FILE_NOT_FOUND, 404, "File missing on disk")

    meta = read_metadata(row["path"])
    meta = _apply_import_fallbacks(meta)
    new_hash = compute_file_hash(row["path"])

    updates = {k: meta.get(k) for k in _META_KEYS}
    updates.update(
        {
            "status": "unmodified",
            "changed_fields": [],
            "file_hash": new_hash,
            "suggested_filename": None,
            "technical": meta["technical"],
            "bext": meta.get("bext"),
            "info": meta.get("info"),
            "custom_fields": meta.get("custom_fields"),
        }
    )
    await update_file(file_id, updates)

    updated = await get_file(file_id)
    return dict_to_file_record(updated)


@router.get("/{file_id}/audio")
async def get_file_audio(file_id: str) -> FileResponse:
    """Stream audio file from disk for playback."""
    row = await get_file(file_id)
    if row is None:
        raise AppError(FILE_NOT_FOUND, 404, f"File not found: {file_id}")

    file_path = Path(row["path"])
    if not file_path.is_file():
        raise AppError(FILE_NOT_FOUND, 404, f"File missing on disk: {row['path']}")

    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=row["filename"],
    )


def _compute_status_after_edit(row: dict, changes: dict) -> str:
    """Determine file status after a metadata edit.

    If the file was flagged and the edit resolves the flag condition
    (e.g., user sets a category), change to 'modified'. Otherwise 'modified'.
    """
    if row.get("status") != "flagged":
        return "modified"

    # Use updated category (from changes or existing row)
    new_category = changes.get("category", row.get("category"))
    analysis_raw = row.get("analysis")
    classification = None
    if analysis_raw and isinstance(analysis_raw, dict):
        classification = [
            ClassificationMatch(**m) for m in analysis_raw.get("classification", [])
        ]
    if should_flag(classification=classification, category=new_category):
        return "flagged"
    return "modified"


_FILENAME_FIELDS = {"cat_id", "fx_name", "creator_id", "source_id", "user_category"}


def _maybe_regen_filename(row: dict, changes: dict) -> None:
    """Regenerate suggested_filename when filename-constituent fields change."""
    if not (_FILENAME_FIELDS & set(changes.keys())):
        return
    merged = {**row, **changes}
    cat_id = merged.get("cat_id")
    if not cat_id:
        return
    from app.ucs.filename import generate_filename

    result = generate_filename(
        cat_id=cat_id,
        fx_name=merged.get("fx_name"),
        creator_id=merged.get("creator_id"),
        source_id=merged.get("source_id"),
        user_category=merged.get("user_category"),
    )
    changes["suggested_filename"] = result.filename


async def _save_as_copy(row: dict, body: SaveRequest, old_path: str) -> SaveResponse:
    """Copy original file to user-chosen path and write metadata to the copy."""
    if not body.copy_path:
        raise AppError(VALIDATION_ERROR, 422, "copy_path required when copy=true")

    dest = Path(body.copy_path)
    if not dest.parent.is_dir():
        raise AppError(
            VALIDATION_ERROR, 422, f"Parent directory does not exist: {dest.parent}"
        )

    try:
        shutil.copy2(old_path, str(dest))

        metadata = {k: row[k] for k in _META_KEYS if row.get(k) is not None}
        if row.get("custom_fields"):
            metadata["custom_fields"] = row["custom_fields"]

        write_metadata(str(dest), metadata)

        result = verify_write(str(dest), metadata)
        if not result["ok"]:
            dest.unlink(missing_ok=True)
            raise AppError(
                "WRITE_FAILED", 500, f"Copy verification failed: {result['errors']}"
            )
    except AppError:
        raise
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise AppError("WRITE_FAILED", 500, f"Save as copy failed: {e}")

    return SaveResponse(
        success=True,
        file=dict_to_file_record(row),
        old_path=old_path,
        new_path=old_path,
        renamed=False,
        copied=True,
        copy_path=str(dest),
    )


def _check_rename(body: SaveRequest, row: dict) -> tuple[bool, Path | None]:
    """Determine if a rename is needed and validate the target path.

    Returns (will_rename, target_path). Raises 409 if target exists.
    """
    suggested = row.get("suggested_filename")
    if not body.rename or not suggested or suggested == row["filename"]:
        return False, None

    target = Path(row["directory"]) / suggested
    if target.exists():
        raise AppError(RENAME_CONFLICT, 409, "Rename conflict: target exists")
    return True, target


async def _finalize_save(
    file_id: str, old_path: str, target_path: Path | None, will_rename: bool
) -> SaveResponse:
    """Rename (if needed), update DB, and build the SaveResponse."""
    if will_rename:
        os.replace(old_path, str(target_path))
        new_path = str(target_path)
        new_hash = compute_file_hash(new_path)
        await update_file(
            file_id,
            {
                "path": new_path,
                "filename": target_path.name,
                "directory": str(target_path.parent),
                "status": "saved",
                "changed_fields": [],
                "file_hash": new_hash,
            },
        )
    else:
        new_path = old_path
        new_hash = compute_file_hash(old_path)
        await update_file(
            file_id,
            {"status": "saved", "changed_fields": [], "file_hash": new_hash},
        )

    updated = await get_file(file_id)
    return SaveResponse(
        success=True,
        file=dict_to_file_record(updated),
        old_path=old_path,
        new_path=new_path,
        renamed=will_rename,
    )


async def _import_single_file(wav_path: Path, abs_path: str) -> FileRecord:
    """Read or cache a single WAV file and return a FileRecord."""
    file_hash = compute_file_hash(abs_path)

    # Check DB cache — file already imported with same hash
    existing = await get_file_by_path(abs_path)
    if existing is not None and existing.get("file_hash") == file_hash:
        return hydrate_suggestions(dict_to_file_record(existing))

    # Read fresh metadata and apply import-time fallbacks
    meta = read_metadata(abs_path)
    meta = _apply_import_fallbacks(meta)
    db_record = {
        "path": abs_path,
        "filename": wav_path.name,
        "directory": str(wav_path.parent.resolve()),
        "status": "unmodified",
        "file_hash": file_hash,
        **{k: meta.get(k) for k in _META_KEYS},
        "technical": meta["technical"],
        "bext": meta.get("bext"),
        "info": meta.get("info"),
        "custom_fields": meta.get("custom_fields"),
    }

    # Pre-populate analysis from cache if previously analyzed
    cached = await get_cached_analysis(file_hash)
    if cached is not None:
        _inject_cached_analysis(db_record, cached, wav_path.name)

    file_id = await upsert_file(db_record)
    db_record["id"] = file_id
    return hydrate_suggestions(dict_to_file_record(db_record))


def _inject_cached_analysis(db_record: dict, cached: dict, filename: str) -> None:
    """Inject cached analysis results into a new file record (mutates db_record)."""
    classification = [
        ClassificationMatch(**m) for m in json.loads(cached["classification"])
    ]
    boosted = apply_filename_boost(classification, filename)
    caption = cached.get("caption")
    analysis = AnalysisResult(
        classification=boosted,
        caption=caption,
        model_version=cached.get("model_version", "2023"),
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )
    db_record["analysis"] = json.loads(analysis.model_dump_json())


async def _remove_stale_records(directory: str, seen_paths: set[str]) -> None:
    """Delete DB records for files no longer on disk in this directory."""
    all_records = await get_all_files(limit=100000)
    stale = [
        r["path"]
        for r in all_records
        if r["path"].startswith(directory + os.sep) and r["path"] not in seen_paths
    ]
    if stale:
        await delete_files_by_paths(stale)


def _apply_import_fallbacks(meta: dict) -> dict:
    """Merge BEXT/INFO values into empty iXML fields per 08-metadata-schema.md S5a."""
    bext = meta.get("bext") or {}
    info = meta.get("info") or {}

    # description: BEXT description → iXML
    if not meta.get("description") and bext.get("description"):
        meta["description"] = bext["description"]

    # designer: BEXT originator (priority) → INFO artist (fallback)
    if not meta.get("designer"):
        if bext.get("originator"):
            meta["designer"] = bext["originator"]
        elif info.get("artist"):
            meta["designer"] = info["artist"]

    # fx_name: INFO title → iXML
    if not meta.get("fx_name") and info.get("title"):
        meta["fx_name"] = info["title"]

    # category: INFO genre → iXML
    if not meta.get("category") and info.get("genre"):
        meta["category"] = info["genre"]

    # notes: INFO comment → iXML
    if not meta.get("notes") and info.get("comment"):
        meta["notes"] = info["comment"]

    # library: INFO product → iXML
    if not meta.get("library") and info.get("product"):
        meta["library"] = info["product"]

    # keywords: INFO keywords → iXML
    if not meta.get("keywords") and info.get("keywords"):
        meta["keywords"] = info["keywords"]

    return meta


# All 22 nullable metadata field keys
_META_KEYS = [
    "category",
    "subcategory",
    "cat_id",
    "category_full",
    "user_category",
    "fx_name",
    "description",
    "keywords",
    "notes",
    "designer",
    "library",
    "project",
    "microphone",
    "mic_perspective",
    "rec_medium",
    "release_date",
    "rating",
    "is_designed",
    "manufacturer",
    "rec_type",
    "creator_id",
    "source_id",
]
