"""Async SQLite repository for file records."""

import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

from app.db.schema import init_db

logger = logging.getLogger(__name__)

_db: aiosqlite.Connection | None = None
_db_path: str = ""

# Columns that store JSON
_JSON_COLS = {
    "technical",
    "bext",
    "info",
    "changed_fields",
    "custom_fields",
    "analysis",
}

# All 22 nullable metadata field column names
_META_COLS = [
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

# All columns in insert order (excluding id, imported_at, modified_at)
_INSERT_COLS = [
    "path",
    "filename",
    "directory",
    "status",
    "changed_fields",
    "file_hash",
    *_META_COLS,
    "suggested_filename",
    "technical",
    "bext",
    "info",
    "custom_fields",
]

# Columns allowed in partial updates via update_file()
_UPDATABLE_COLS = {
    "path",
    "filename",
    "directory",
    "status",
    "changed_fields",
    "file_hash",
    *_META_COLS,
    "suggested_filename",
    "technical",
    "bext",
    "info",
    "custom_fields",
    "analysis",
}


async def connect(db_path: str) -> None:
    """Open DB connection and initialize schema."""
    global _db, _db_path
    _db_path = db_path
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row
    await init_db(_db)


def get_db_path() -> str:
    """Return the path used to open the current DB."""
    return _db_path


async def close() -> None:
    """Close DB connection."""
    global _db
    if _db is not None:
        await _db.close()
        _db = None


def get_db() -> aiosqlite.Connection:
    """Return the active DB connection. Raises if not connected."""
    if _db is None:
        raise RuntimeError("Database not connected. Call connect() first.")
    return _db


async def insert_file(record: dict) -> str:
    """Insert a new file record. Returns the generated UUID."""
    db = get_db()
    file_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    values = [file_id]
    for col in _INSERT_COLS:
        values.append(_serialize(col, record.get(col)))
    values.extend([now, now])

    placeholders = ", ".join(["?"] * len(values))
    cols = "id, " + ", ".join(_INSERT_COLS) + ", imported_at, modified_at"

    await db.execute(f"INSERT INTO files ({cols}) VALUES ({placeholders})", values)
    await db.commit()
    return file_id


async def get_file(file_id: str) -> dict | None:
    """Get a file record by ID."""
    db = get_db()
    cursor = await db.execute("SELECT * FROM files WHERE id = ?", (file_id,))
    row = await cursor.fetchone()
    return _row_to_dict(row) if row else None


async def get_file_by_path(path: str) -> dict | None:
    """Get a file record by absolute path."""
    db = get_db()
    cursor = await db.execute("SELECT * FROM files WHERE path = ?", (path,))
    row = await cursor.fetchone()
    return _row_to_dict(row) if row else None


async def get_all_files(
    *,
    status: str | None = None,
    category: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 1000,
) -> list[dict]:
    """Query file records with optional filters."""
    db = get_db()
    where_clauses: list[str] = []
    params: list[str | int] = []

    if status is not None:
        where_clauses.append("status = ?")
        params.append(status)
    if category is not None:
        where_clauses.append("category = ?")
        params.append(category)
    if search is not None:
        like = f"%{search}%"
        where_clauses.append(
            "(filename LIKE ? OR fx_name LIKE ? OR description LIKE ? OR keywords LIKE ?)"
        )
        params.extend([like, like, like, like])

    sql = "SELECT * FROM files"
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY path"
    sql += f" LIMIT {limit} OFFSET {offset}"

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()
    return [_row_to_dict(row) for row in rows]


async def upsert_file(record: dict) -> str:
    """Insert or replace a file record (matched on path). Returns ID."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    # Check if record already exists
    existing = await get_file_by_path(record["path"])
    if existing is not None:
        file_id = existing["id"]
        sets = []
        values = []
        for col in _INSERT_COLS:
            if col == "path":
                continue  # path is the match key
            sets.append(f"{col} = ?")
            values.append(_serialize(col, record.get(col)))
        sets.append("modified_at = ?")
        values.append(now)
        values.append(file_id)

        await db.execute(f"UPDATE files SET {', '.join(sets)} WHERE id = ?", values)
        await db.commit()
        return file_id

    return await insert_file(record)


async def update_file(file_id: str, updates: dict) -> None:
    """Partial update of a file record by ID.

    Raises ValueError if any key not in _UPDATABLE_COLS.
    """
    bad_keys = set(updates) - _UPDATABLE_COLS
    if bad_keys:
        raise ValueError(f"Invalid columns for update: {bad_keys}")

    db = get_db()
    now = datetime.now(timezone.utc).isoformat()

    sets = []
    values = []
    for col, val in updates.items():
        sets.append(f"{col} = ?")
        values.append(_serialize(col, val))
    sets.append("modified_at = ?")
    values.append(now)
    values.append(file_id)

    await db.execute(f"UPDATE files SET {', '.join(sets)} WHERE id = ?", values)
    await db.commit()


async def delete_files_by_paths(paths: list[str]) -> None:
    """Delete records by path list."""
    if not paths:
        return
    db = get_db()
    placeholders = ", ".join(["?"] * len(paths))
    await db.execute(f"DELETE FROM files WHERE path IN ({placeholders})", paths)
    await db.commit()


async def count_files() -> int:
    """Return total number of file records."""
    db = get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM files")
    row = await cursor.fetchone()
    return row[0]


def _serialize(col: str, value) -> str | None:
    """Serialize a value for storage. JSON-encode dicts."""
    if col in _JSON_COLS and value is not None:
        return json.dumps(value)
    return value


def _row_to_dict(row: aiosqlite.Row) -> dict:
    """Convert an aiosqlite.Row to a plain dict, deserializing JSON columns."""
    d = dict(row)
    for col in _JSON_COLS:
        if d.get(col) is not None:
            d[col] = json.loads(d[col])
    return d


# ---------------------------------------------------------------------------
# Analysis cache
# ---------------------------------------------------------------------------


async def get_cached_analysis(file_hash: str) -> dict | None:
    """Get cached analysis result by file hash."""
    db = get_db()
    cursor = await db.execute(
        "SELECT * FROM analysis_cache WHERE file_hash = ?", (file_hash,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def store_cached_analysis(
    file_hash: str,
    classification: str,
    caption: str | None,
    model_version: str,
) -> None:
    """Store or replace cached analysis result."""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "INSERT OR REPLACE INTO analysis_cache "
        "(file_hash, classification, caption, model_version, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (file_hash, classification, caption, model_version, now),
    )
    await db.commit()


async def clear_analysis_cache() -> None:
    """Delete all cached analysis results."""
    db = get_db()
    await db.execute("DELETE FROM analysis_cache")
    await db.commit()
