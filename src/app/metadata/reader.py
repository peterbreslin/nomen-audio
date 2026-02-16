"""Metadata reader — extracts WAV metadata into a flat dict via wavinfo."""

import hashlib
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any

from wavinfo import WavInfoReader

logger = logging.getLogger(__name__)

# Inverse of writer.USER_KEY_MAP: XML tag → dict key
_USER_TAG_TO_KEY: dict[str, str] = {
    "CATEGORY": "category",
    "SUBCATEGORY": "subcategory",
    "CATID": "cat_id",
    "CATEGORYFULL": "category_full",
    "FXNAME": "fx_name",
    "DESCRIPTION": "description",
    "KEYWORDS": "keywords",
    "NOTES": "notes",
    "DESIGNER": "designer",
    "LIBRARY": "library",
    "USERCATEGORY": "user_category",
    "MICROPHONE": "microphone",
    "MICPERSPECTIVE": "mic_perspective",
    "RECMEDIUM": "rec_medium",
    "RELEASEDATE": "release_date",
    "RATING": "rating",
    "MANUFACTURER": "manufacturer",
    "RECTYPE": "rec_type",
    "CREATORID": "creator_id",
    "SOURCEID": "source_id",
}

# Inverse of writer.ASWG_KEY_MAP: XML tag → dict key
_ASWG_TAG_TO_KEY: dict[str, str] = {
    # Fallbacks first — primary mappings below overwrite these
    "originator": "designer",
    # Primary mappings
    "category": "category",
    "subCategory": "subcategory",
    "catId": "cat_id",
    "userCategory": "user_category",
    "fxName": "fx_name",
    "library": "library",
    "creatorId": "creator_id",
    "sourceId": "source_id",
    "notes": "notes",
    "project": "project",
    "micType": "microphone",
    "isDesigned": "is_designed",
    "manufacturer": "manufacturer",
    "recType": "rec_type",
}

# All 22 nullable metadata field keys
METADATA_KEYS: list[str] = [
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

_HASH_READ_SIZE = 4096


def read_metadata(path: str) -> dict[str, Any]:
    """Read all metadata from a WAV file into a flat dict.

    Returns dict with keys: technical, bext, info, + all 18 nullable metadata fields.
    """
    info = WavInfoReader(path)

    result: dict[str, Any] = {key: None for key in METADATA_KEYS}
    result["technical"] = _extract_technical(info, path)
    result["bext"] = _extract_bext(info)
    result["info"] = _extract_info(info)

    ixml_fields = _extract_ixml_fields(info)
    for key, value in ixml_fields.items():
        result[key] = value

    # custom_fields is separate from the 18 metadata fields
    if "custom_fields" in ixml_fields:
        result["custom_fields"] = ixml_fields["custom_fields"]

    return result


def compute_file_hash(path: str) -> str:
    """SHA-256 of first 4KB + file_size + mtime — fast cache key."""
    stat = os.stat(path)
    hasher = hashlib.sha256()

    with open(path, "rb") as f:
        hasher.update(f.read(_HASH_READ_SIZE))

    hasher.update(str(stat.st_size).encode())
    hasher.update(str(stat.st_mtime).encode())
    return hasher.hexdigest()


def _extract_technical(info: WavInfoReader, path: str) -> dict[str, Any]:
    """Extract technical fields from fmt + data chunks."""
    fmt = info.fmt
    data = info.data

    sample_rate = fmt.sample_rate
    channels = fmt.channel_count
    bit_depth = fmt.bits_per_sample
    frame_count = data.frame_count
    duration = frame_count / sample_rate if sample_rate > 0 else 0.0

    audio_format_code = fmt.audio_format
    audio_format = "PCM" if audio_format_code == 1 else f"0x{audio_format_code:04X}"

    return {
        "sample_rate": sample_rate,
        "bit_depth": bit_depth,
        "channels": channels,
        "duration_seconds": round(duration, 6),
        "frame_count": frame_count,
        "audio_format": audio_format,
        "file_size_bytes": os.path.getsize(path),
    }


def _extract_bext(info: WavInfoReader) -> dict[str, Any] | None:
    """Extract BEXT fields. Returns None if no bext chunk."""
    bext = info.bext
    if bext is None:
        return None

    return {
        "description": _clean_str(getattr(bext, "description", None)),
        "originator": _clean_str(getattr(bext, "originator", None)),
        "originator_date": _clean_str(getattr(bext, "originator_date", None)),
        "originator_time": _clean_str(getattr(bext, "originator_time", None)),
        "time_reference": getattr(bext, "time_reference", None),
        "coding_history": _clean_str(getattr(bext, "coding_history", None)),
    }


def _extract_info(info: WavInfoReader) -> dict[str, Any] | None:
    """Extract RIFF INFO fields. Returns None if no INFO chunk."""
    riff_info = info.info
    if riff_info is None:
        return None

    fields = {
        "title": getattr(riff_info, "title", None),
        "artist": getattr(riff_info, "artist", None),
        "genre": getattr(riff_info, "genre", None),
        "comment": getattr(riff_info, "comment", None),
        "created_date": getattr(riff_info, "created_date", None),
        "software": getattr(riff_info, "software", None),
        "copyright": getattr(riff_info, "copyright", None),
        "product": getattr(riff_info, "product", None),
        "keywords": getattr(riff_info, "keywords", None),
    }

    # If all fields are None, treat as no INFO chunk
    if all(v is None for v in fields.values()):
        return None

    return fields


def _extract_ixml_fields(info: WavInfoReader) -> dict[str, str]:
    """Parse iXML source XML; extract USER then ASWG fields.

    USER fields override ASWG (Soundminer convention: USER is authoritative).
    """
    root = _parse_ixml(info)
    if root is None:
        return {}

    fields: dict[str, str] = {}

    # ASWG first (lower priority)
    aswg_el = root.find("ASWG")
    if aswg_el is not None:
        for xml_tag, dict_key in _ASWG_TAG_TO_KEY.items():
            el = aswg_el.find(xml_tag)
            if el is not None and el.text:
                fields[dict_key] = el.text

    # USER second (higher priority — overwrites ASWG)
    user_el = root.find("USER")
    if user_el is not None:
        for xml_tag, dict_key in _USER_TAG_TO_KEY.items():
            el = user_el.find(xml_tag)
            if el is not None and el.text:
                fields[dict_key] = el.text

        # Collect unknown USER tags into custom_fields
        known_tags = set(_USER_TAG_TO_KEY.keys()) | {"EMBEDDER"}
        custom: dict[str, str] = {}
        for child in user_el:
            if child.tag not in known_tags and child.text:
                custom[child.tag] = child.text
        if custom:
            fields["custom_fields"] = custom

    return fields


def _parse_ixml(info: WavInfoReader) -> ET.Element | None:
    """Parse the raw iXML source string into an ElementTree root."""
    if info.ixml is None:
        return None

    source = getattr(info.ixml, "source", None)
    if not source:
        return None

    if isinstance(source, bytes):
        source = source.decode("utf-8", errors="replace")

    source = source.rstrip("\x00").strip()
    try:
        return ET.fromstring(source)
    except ET.ParseError:
        logger.warning("Failed to parse iXML source")
        return None


def _clean_str(value: Any) -> str | None:
    """Strip null bytes and whitespace from a string value."""
    if value is None:
        return None
    s = str(value).rstrip("\x00").strip()
    return s if s else None
