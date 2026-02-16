"""Settings API endpoints."""

import os

from fastapi import APIRouter

from app.db import repository
from app.errors import AppError, VALIDATION_ERROR
from app.services.settings import SettingsUpdate, get_settings, update_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def read_settings() -> dict:
    """Return current settings with API key masked."""
    s = get_settings()
    data = s.model_dump()
    # Mask API key
    if data.get("llm_api_key"):
        data["llm_api_key"] = "configured"
    return data


@router.post("/reset-db")
async def reset_database() -> dict:
    """Close DB, delete the file, and reconnect (re-creates schema)."""
    db_path = repository.get_db_path()
    await repository.close()
    if os.path.exists(db_path):
        os.remove(db_path)
    await repository.connect(db_path)
    return {"status": "ok"}


@router.put("")
def write_settings(body: SettingsUpdate) -> dict:
    """Partial update of settings. Returns full updated settings."""
    try:
        s = update_settings(body.model_dump(exclude_unset=True))
    except ValueError as e:
        raise AppError(VALIDATION_ERROR, 422, str(e))
    data = s.model_dump()
    if data.get("llm_api_key"):
        data["llm_api_key"] = "configured"
    return data
