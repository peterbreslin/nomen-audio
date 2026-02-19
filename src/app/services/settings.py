"""Settings service — JSON-persisted application configuration."""

import json
import os
import re
import tempfile

from pydantic import BaseModel

from app import paths

# Built-in USER tags that cannot be used as custom field tags
_BUILTIN_USER_TAGS = frozenset(
    {
        "CATEGORY",
        "SUBCATEGORY",
        "CATID",
        "CATEGORYFULL",
        "FXNAME",
        "DESCRIPTION",
        "KEYWORDS",
        "NOTES",
        "DESIGNER",
        "LIBRARY",
        "USERCATEGORY",
        "MICROPHONE",
        "MICPERSPECTIVE",
        "RECMEDIUM",
        "RELEASEDATE",
        "RATING",
        "EMBEDDER",
        "MANUFACTURER",
        "RECTYPE",
        "CREATORID",
        "SOURCEID",
    }
)

_TAG_RE = re.compile(r"^[A-Z0-9_]+$")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CustomFieldDef(BaseModel):
    """Definition of a user-defined iXML USER tag."""

    tag: str
    label: str


class AppSettings(BaseModel):
    """Application-wide settings with sensible defaults."""

    version: int = 1
    creator_id: str = ""
    source_id: str = ""
    library_name: str = ""
    library_template: str = "{source_id} {library_name}"
    rename_on_save_default: bool = True
    custom_fields: list[CustomFieldDef] = []
    llm_provider: str | None = None
    llm_api_key: str | None = None
    model_directory: str = "data/models"


class SettingsUpdate(BaseModel):
    """Partial settings update — all fields optional."""

    model_config = {"extra": "ignore"}

    creator_id: str | None = None
    source_id: str | None = None
    library_name: str | None = None
    library_template: str | None = None
    rename_on_save_default: bool | None = None
    custom_fields: list[CustomFieldDef] | None = None
    llm_provider: str | None = None
    llm_api_key: str | None = None
    model_directory: str | None = None


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_settings: AppSettings = AppSettings()
_settings_path: str | None = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_settings(path: str | None = None) -> None:
    """Load settings from JSON file, falling back to defaults."""
    global _settings, _settings_path
    if path is not None:
        _settings_path = path
    else:
        _settings_path = paths.get_settings_path()

    if os.path.isfile(_settings_path):
        with open(_settings_path, encoding="utf-8") as f:
            data = json.load(f)
        _settings = AppSettings(**data)
    else:
        _settings = AppSettings()


def save_settings() -> None:
    """Persist current settings to disk atomically."""
    os.makedirs(os.path.dirname(os.path.abspath(_settings_path)), exist_ok=True)
    dir_name = os.path.dirname(os.path.abspath(_settings_path))
    fd, temp_path = tempfile.mkstemp(suffix=".json.tmp", dir=dir_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(_settings.model_dump(), f, indent=2)
        os.replace(temp_path, os.path.abspath(_settings_path))
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def get_settings() -> AppSettings:
    return _settings


def update_settings(updates: dict) -> AppSettings:
    """Merge partial updates into current settings, validate, and save."""
    global _settings
    current = _settings.model_dump()
    current.update(updates)
    new_settings = AppSettings(**current)

    if new_settings.custom_fields:
        validate_custom_field_tags(new_settings.custom_fields)

    _settings = new_settings
    save_settings()
    return _settings


def validate_custom_field_tags(fields: list[CustomFieldDef]) -> None:
    """Validate custom field tags: uppercase + digits + underscore, max 32, no clashes."""
    for field in fields:
        tag = field.tag
        if not _TAG_RE.match(tag):
            raise ValueError(f"Invalid tag '{tag}': must match [A-Z0-9_]+")
        if len(tag) > 32:
            raise ValueError(f"Tag '{tag}' too long ({len(tag)} chars, max 32)")
        if tag in _BUILTIN_USER_TAGS:
            raise ValueError(f"Tag '{tag}' clashes with built-in USER tag")
