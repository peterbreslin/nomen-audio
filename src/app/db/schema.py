"""SQLite schema for NomenAudio file records."""

import aiosqlite

FILES_DDL = """
CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    filename TEXT NOT NULL,
    directory TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unmodified',
    changed_fields TEXT DEFAULT '[]',
    file_hash TEXT NOT NULL,

    -- 18 nullable metadata fields
    category TEXT,
    subcategory TEXT,
    cat_id TEXT,
    category_full TEXT,
    user_category TEXT,
    fx_name TEXT,
    description TEXT,
    keywords TEXT,
    notes TEXT,
    designer TEXT,
    library TEXT,
    project TEXT,
    microphone TEXT,
    mic_perspective TEXT,
    rec_medium TEXT,
    release_date TEXT,
    rating TEXT,
    is_designed TEXT,
    suggested_filename TEXT,

    -- JSON columns
    technical TEXT NOT NULL,
    bext TEXT,
    info TEXT,
    custom_fields TEXT,
    analysis TEXT,

    -- Timestamps
    imported_at TEXT,
    modified_at TEXT
);
"""

FILES_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_files_path ON files (path);"

ANALYSIS_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS analysis_cache (
    file_hash TEXT PRIMARY KEY,
    classification TEXT NOT NULL,
    caption TEXT,
    model_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    """Create tables and indexes, then run migrations."""
    await db.executescript(FILES_DDL + FILES_INDEX_DDL + ANALYSIS_CACHE_DDL)
    await db.commit()
    await _migrate_custom_fields(db)
    await _migrate_analysis_column(db)
    await _migrate_aswg_extended_fields(db)


async def _migrate_custom_fields(db: aiosqlite.Connection) -> None:
    """Add custom_fields column if missing (migration from pre-2C schema)."""
    cursor = await db.execute("PRAGMA table_info(files)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "custom_fields" not in columns:
        await db.execute("ALTER TABLE files ADD COLUMN custom_fields TEXT")
        await db.commit()


async def _migrate_analysis_column(db: aiosqlite.Connection) -> None:
    """Add analysis column if missing (migration from pre-Phase 4 schema)."""
    cursor = await db.execute("PRAGMA table_info(files)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "analysis" not in columns:
        await db.execute("ALTER TABLE files ADD COLUMN analysis TEXT")
        await db.commit()


_ASWG_EXTENDED_COLUMNS = ["manufacturer", "rec_type", "creator_id", "source_id"]


async def _migrate_aswg_extended_fields(db: aiosqlite.Connection) -> None:
    """Add manufacturer, rec_type, creator_id, source_id columns if missing."""
    cursor = await db.execute("PRAGMA table_info(files)")
    columns = {row[1] for row in await cursor.fetchall()}
    for col in _ASWG_EXTENDED_COLUMNS:
        if col not in columns:
            await db.execute(f"ALTER TABLE files ADD COLUMN {col} TEXT")
    await db.commit()
