"""Shared mappers for converting DB dicts to Pydantic models."""

from app.models import FileRecord


def dict_to_file_record(d: dict) -> FileRecord:
    """Convert a repository dict to a FileRecord model."""
    return FileRecord(
        id=d["id"],
        path=d["path"],
        filename=d["filename"],
        directory=d["directory"],
        status=d.get("status", "unmodified"),
        changed_fields=d.get("changed_fields") or [],
        technical=d["technical"],
        category=d.get("category"),
        subcategory=d.get("subcategory"),
        cat_id=d.get("cat_id"),
        category_full=d.get("category_full"),
        user_category=d.get("user_category"),
        fx_name=d.get("fx_name"),
        description=d.get("description"),
        keywords=d.get("keywords"),
        notes=d.get("notes"),
        designer=d.get("designer"),
        library=d.get("library"),
        project=d.get("project"),
        microphone=d.get("microphone"),
        mic_perspective=d.get("mic_perspective"),
        rec_medium=d.get("rec_medium"),
        release_date=d.get("release_date"),
        rating=d.get("rating"),
        is_designed=d.get("is_designed"),
        manufacturer=d.get("manufacturer"),
        rec_type=d.get("rec_type"),
        creator_id=d.get("creator_id"),
        source_id=d.get("source_id"),
        suggested_filename=d.get("suggested_filename"),
        custom_fields=d.get("custom_fields"),
        bext=d.get("bext"),
        info=d.get("info"),
        analysis=d.get("analysis"),
    )
