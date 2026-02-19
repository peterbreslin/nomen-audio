"""
NomenAudio RIFF Writer Module

Writes metadata to WAV files by rewriting the RIFF container with updated
iXML and BEXT chunks. All other chunks (including audio data) are preserved
byte-for-byte via stream copying.

Usage:
    from app.metadata.writer import write_metadata

    write_metadata("path/to/file.wav", {
        "category": "DOORS",
        "subcategory": "WOOD",
        "cat_id": "DOORWood",
        "category_full": "DOORS-WOOD",
        "fx_name": "Cabin Door Open Close",
        "description": "Old wooden cabin door opening with a long creak",
        "keywords": "door, wood, creak, cabin",
        "designer": "JDOE",
        "library": "MYGAME",
    })
"""

import os
import struct
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RIFF_HEADER = b"RIFF"
WAVE_ID = b"WAVE"
CHUNK_BEXT = b"bext"
CHUNK_IXML = b"iXML"
CHUNK_LIST = b"LIST"
LIST_TYPE_INFO = b"INFO"
BUFFER_SIZE = 1_048_576  # 1 MB for stream copying

IXML_VERSION = "1.61"
EMBEDDER_NAME = "NomenAudio"

# USER field tag names (ALL CAPS, Soundminer/BaseHead convention)
USER_FIELDS = [
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
    "MANUFACTURER",
    "RECTYPE",
    "CREATORID",
    "SOURCEID",
    "EMBEDDER",
]

# Mapping: metadata_dict key → USER XML tag
USER_KEY_MAP = {
    "category": "CATEGORY",
    "subcategory": "SUBCATEGORY",
    "cat_id": "CATID",
    "category_full": "CATEGORYFULL",
    "fx_name": "FXNAME",
    "description": "DESCRIPTION",
    "keywords": "KEYWORDS",
    "notes": "NOTES",
    "designer": "DESIGNER",
    "library": "LIBRARY",
    "user_category": "USERCATEGORY",
    "microphone": "MICROPHONE",
    "mic_perspective": "MICPERSPECTIVE",
    "rec_medium": "RECMEDIUM",
    "release_date": "RELEASEDATE",
    "rating": "RATING",
    "manufacturer": "MANUFACTURER",
    "rec_type": "RECTYPE",
    "creator_id": "CREATORID",
    "source_id": "SOURCEID",
}

# Mapping: metadata_dict key → ASWG XML tag (camelCase)
ASWG_KEY_MAP = {
    "category": "category",
    "subcategory": "subCategory",
    "cat_id": "catId",
    "user_category": "userCategory",
    "fx_name": "fxName",
    "library": "library",
    "notes": "notes",
    "project": "project",
    "microphone": "micType",
    "is_designed": "isDesigned",
    "manufacturer": "manufacturer",
    "rec_type": "recType",
    "creator_id": "creatorId",
    "source_id": "sourceId",
}

# ASWG fields that derive from metadata_dict but with different key mappings
ASWG_EXTRA_MAPPINGS = {
    "originator": "designer",  # ASWG <originator> ← metadata["designer"]
}

# Mapping: metadata_dict key → INFO sub-chunk tag
INFO_KEY_MAP = {
    "fx_name": b"INAM",
    "designer": b"IART",
    "category": b"IGNR",
    "notes": b"ICMT",
    "library": b"IPRD",
    "keywords": b"IKEY",
}

# BEXT binary layout constants
BEXT_DESCRIPTION_SIZE = 256
BEXT_ORIGINATOR_SIZE = 32
BEXT_ORIGINATOR_REF_SIZE = 32
BEXT_DATE_SIZE = 10
BEXT_TIME_SIZE = 8
BEXT_FIXED_SIZE = 602  # Everything before CodingHistory


# ---------------------------------------------------------------------------
# BEXT Chunk Handling
# ---------------------------------------------------------------------------


def _unpack_bext(data: bytes) -> dict:
    """Unpacks raw BEXT chunk data into a dictionary of fields."""
    # Pad if shorter than expected (some writers produce short BEXT)
    if len(data) < BEXT_FIXED_SIZE:
        data = data + b"\x00" * (BEXT_FIXED_SIZE - len(data))

    return {
        "description": data[0:256],
        "originator": data[256:288],
        "originator_ref": data[288:320],
        "origination_date": data[320:330],
        "origination_time": data[330:338],
        "time_ref_low": struct.unpack("<I", data[338:342])[0],
        "time_ref_high": struct.unpack("<I", data[342:346])[0],
        "version": struct.unpack("<H", data[346:348])[0],
        "umid": data[348:412],
        "loudness_value": struct.unpack("<h", data[412:414])[0],
        "loudness_range": struct.unpack("<h", data[414:416])[0],
        "max_true_peak": struct.unpack("<h", data[416:418])[0],
        "max_momentary": struct.unpack("<h", data[418:420])[0],
        "max_shortterm": struct.unpack("<h", data[420:422])[0],
        "reserved": data[422:602],
        "coding_history": data[602:],
    }


def _pack_bext(fields: dict) -> bytes:
    """Packs a BEXT fields dictionary back into raw binary chunk data."""
    data = bytearray()
    data += _pad_bytes(fields["description"], 256)
    data += _pad_bytes(fields["originator"], 32)
    data += _pad_bytes(fields["originator_ref"], 32)
    data += _pad_bytes(fields["origination_date"], 10)
    data += _pad_bytes(fields["origination_time"], 8)
    data += struct.pack("<I", fields["time_ref_low"])
    data += struct.pack("<I", fields["time_ref_high"])
    data += struct.pack("<H", fields["version"])
    data += _pad_bytes(fields["umid"], 64)
    data += struct.pack("<h", fields["loudness_value"])
    data += struct.pack("<h", fields["loudness_range"])
    data += struct.pack("<h", fields["max_true_peak"])
    data += struct.pack("<h", fields["max_momentary"])
    data += struct.pack("<h", fields["max_shortterm"])
    data += _pad_bytes(fields["reserved"], 180)
    data += (
        fields["coding_history"]
        if isinstance(fields["coding_history"], bytes)
        else fields["coding_history"].encode("ascii", errors="replace")
    )
    return bytes(data)


def _create_default_bext(metadata: dict) -> dict:
    """Creates a new BEXT fields dictionary with sensible defaults."""
    now = datetime.now()
    return {
        "description": metadata.get("description", ""),
        "originator": metadata.get("designer", ""),
        "originator_ref": b"",
        "origination_date": now.strftime("%Y-%m-%d"),
        "origination_time": now.strftime("%H:%M:%S"),
        "time_ref_low": 0,
        "time_ref_high": 0,
        "version": 1,
        "umid": b"\x00" * 64,
        "loudness_value": 0,
        "loudness_range": 0,
        "max_true_peak": 0,
        "max_momentary": 0,
        "max_shortterm": 0,
        "reserved": b"\x00" * 180,
        "coding_history": b"",
    }


def _update_bext(existing_data: bytes, metadata: dict) -> bytes:
    """Updates an existing BEXT chunk with new metadata values."""
    fields = _unpack_bext(existing_data)

    if "description" in metadata:
        fields["description"] = metadata["description"]
    if "designer" in metadata:
        fields["originator"] = metadata["designer"]

    return _pack_bext(fields)


def _build_new_bext(metadata: dict) -> bytes:
    """Creates a brand new BEXT chunk from metadata."""
    fields = _create_default_bext(metadata)
    return _pack_bext(fields)


def _pad_bytes(value, length: int) -> bytes:
    """Converts a value to bytes, truncates or null-pads to exact length."""
    if isinstance(value, str):
        raw = value.encode("ascii", errors="replace")
    elif isinstance(value, bytes):
        raw = value
    elif isinstance(value, bytearray):
        raw = bytes(value)
    else:
        raw = str(value).encode("ascii", errors="replace")
    return raw[:length].ljust(length, b"\x00")


# ---------------------------------------------------------------------------
# iXML Chunk Handling
# ---------------------------------------------------------------------------


def _decode_ixml_bytes(raw: bytes) -> str:
    """Decodes iXML bytes, detecting UTF-16 BOM and falling back to Latin-1."""
    if raw[:2] == b"\xff\xfe":
        return raw[2:].decode("utf-16-le", errors="replace")
    if raw[:2] == b"\xfe\xff":
        return raw[2:].decode("utf-16-be", errors="replace")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def _update_ixml(existing_xml_bytes: bytes, metadata: dict) -> bytes:
    """Parses existing iXML, updates USER and ASWG fields, returns new XML bytes."""
    xml_str = _decode_ixml_bytes(existing_xml_bytes)

    # Strip null bytes that some writers leave at the end
    xml_str = xml_str.rstrip("\x00").strip()

    # Attempt to parse
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        # If existing XML is unparseable, create fresh
        return _build_new_ixml(metadata)

    # Verify root tag is BWFXML
    if root.tag != "BWFXML":
        # Wrap or discard — safest to create fresh
        return _build_new_ixml(metadata)

    # Update <USER> block
    _update_xml_block(
        root,
        "USER",
        USER_KEY_MAP,
        metadata,
        extra_fields={
            "EMBEDDER": EMBEDDER_NAME,
        },
    )

    # Update <ASWG> block
    aswg_fields = {}
    for dict_key, xml_tag in ASWG_KEY_MAP.items():
        if dict_key in metadata:
            aswg_fields[xml_tag] = metadata[dict_key]

    # Extra ASWG mappings (different source key than the xml tag name implies)
    for xml_tag, source_key in ASWG_EXTRA_MAPPINGS.items():
        if source_key in metadata:
            aswg_fields[xml_tag] = metadata[source_key]

    # Always set contentType for ASWG
    aswg_fields["contentType"] = "sfx"

    _set_xml_children(root, "ASWG", aswg_fields)

    # Serialize back to UTF-8
    return _serialize_xml(root)


def _build_new_ixml(metadata: dict) -> bytes:
    """Creates a brand new iXML XML document from metadata."""
    root = ET.Element("BWFXML")
    ver = ET.SubElement(root, "IXML_VERSION")
    ver.text = IXML_VERSION

    # Build USER block
    user_fields = {}
    for dict_key, xml_tag in USER_KEY_MAP.items():
        if dict_key in metadata:
            user_fields[xml_tag] = metadata[dict_key]

    user_fields["EMBEDDER"] = EMBEDDER_NAME

    # Add custom fields
    custom = metadata.get("custom_fields")
    if custom:
        for tag, value in custom.items():
            if tag not in user_fields:
                user_fields[tag] = value

    _set_xml_children(root, "USER", user_fields)

    # Build ASWG block
    aswg_fields = {}
    for dict_key, xml_tag in ASWG_KEY_MAP.items():
        if dict_key in metadata:
            aswg_fields[xml_tag] = metadata[dict_key]

    for xml_tag, source_key in ASWG_EXTRA_MAPPINGS.items():
        if source_key in metadata:
            aswg_fields[xml_tag] = metadata[source_key]

    aswg_fields["contentType"] = "sfx"

    _set_xml_children(root, "ASWG", aswg_fields)

    return _serialize_xml(root)


def _update_xml_block(
    root: ET.Element,
    block_tag: str,
    key_map: dict,
    metadata: dict,
    extra_fields: dict | None = None,
):
    """Finds or creates a child block, then updates specific child elements."""
    fields = {}
    for dict_key, xml_tag in key_map.items():
        if dict_key in metadata:
            fields[xml_tag] = metadata[dict_key]

    if extra_fields:
        fields.update(extra_fields)

    # For USER block, also include custom_fields
    if block_tag == "USER":
        custom = metadata.get("custom_fields")
        if custom:
            known_tags = set(key_map.values())
            for tag, value in custom.items():
                if tag not in known_tags:
                    fields[tag] = value

    _set_xml_children(root, block_tag, fields)


def _set_xml_children(root: ET.Element, block_tag: str, fields: dict):
    """Finds or creates block_tag under root, sets child elements from fields dict.

    Existing children of block_tag that are NOT in fields are left untouched.
    """
    block = root.find(block_tag)
    if block is None:
        block = ET.SubElement(root, block_tag)

    for tag, value in fields.items():
        child = block.find(tag)
        if child is None:
            child = ET.SubElement(block, tag)
        child.text = str(value) if value is not None else ""


def _serialize_xml(root: ET.Element) -> bytes:
    """Serializes an ElementTree root to UTF-8 bytes with XML declaration."""
    # Use indent for readability (Python 3.9+)
    try:
        ET.indent(root, space="  ")
    except AttributeError:
        pass  # Python < 3.9, skip pretty-printing

    tree = ET.ElementTree(root)
    buf = BytesIO()
    tree.write(buf, encoding="UTF-8", xml_declaration=True)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# LIST-INFO Chunk Handling
# ---------------------------------------------------------------------------


def _build_info_sub_chunk(tag_bytes: bytes, value: str) -> bytes:
    """Build a single INFO sub-chunk: 4-byte tag + 4-byte size + null-terminated string + pad."""
    encoded = value.encode("ascii", errors="replace") + b"\x00"
    size = len(encoded)
    data = tag_bytes + struct.pack("<I", size) + encoded
    if size % 2 != 0:
        data += b"\x00"
    return data


def _parse_info_sub_chunks(data: bytes) -> dict[bytes, bytes]:
    """Parse LIST-INFO data (after type word) into tag→value map."""
    result: dict[bytes, bytes] = {}
    pos = 0
    while pos + 8 <= len(data):
        tag = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        value = data[pos + 8 : pos + 8 + size]
        result[tag] = value
        pos += 8 + size
        if size % 2 != 0:
            pos += 1
    return result


def _build_list_info(metadata: dict, existing_data: bytes | None = None) -> bytes:
    """Build complete LIST-INFO chunk data (INFO type + sub-chunks).

    Merges new fields into existing (preserves unknown sub-chunks).
    Only fills gaps — never overwrites existing INFO values.
    """
    existing: dict[bytes, bytes] = {}
    if existing_data:
        existing = _parse_info_sub_chunks(existing_data)

    # Add new sub-chunks from metadata (fill gaps only)
    for meta_key, info_tag in INFO_KEY_MAP.items():
        value = metadata.get(meta_key)
        if value and info_tag not in existing:
            existing[info_tag] = value.encode("ascii", errors="replace") + b"\x00"

    # Rebuild the chunk data
    chunk_data = bytearray(LIST_TYPE_INFO)
    for tag, raw_value in existing.items():
        chunk_data += tag
        chunk_data += struct.pack("<I", len(raw_value))
        chunk_data += raw_value
        if len(raw_value) % 2 != 0:
            chunk_data += b"\x00"

    return bytes(chunk_data)


def _has_info_fields(metadata: dict) -> bool:
    """Check if metadata has any fields mappable to INFO sub-chunks."""
    return any(metadata.get(k) for k in INFO_KEY_MAP)


# ---------------------------------------------------------------------------
# Chunk I/O Helpers
# ---------------------------------------------------------------------------


def _write_chunk(out, chunk_id: bytes, chunk_data: bytes):
    """Writes a complete RIFF chunk: 4-byte ID + 4-byte size + data + pad."""
    out.write(chunk_id)
    out.write(struct.pack("<I", len(chunk_data)))
    out.write(chunk_data)
    if len(chunk_data) % 2 != 0:
        out.write(b"\x00")


def _stream_copy(src, dst, size: int):
    """Copies exactly `size` bytes from src to dst in buffered chunks."""
    remaining = size
    while remaining > 0:
        read_size = min(BUFFER_SIZE, remaining)
        buf = src.read(read_size)
        if not buf:
            raise IOError(f"Unexpected end of file: expected {remaining} more bytes")
        dst.write(buf)
        remaining -= len(buf)


def _stream_copy_chunk(src, dst, chunk_id: bytes, data_size: int):
    """Writes chunk header, stream-copies data from src, adds pad byte."""
    dst.write(chunk_id)
    dst.write(struct.pack("<I", data_size))
    _stream_copy(src, dst, data_size)
    if data_size % 2 != 0:
        dst.write(b"\x00")


# ---------------------------------------------------------------------------
# Core Rewrite Engine
# ---------------------------------------------------------------------------


def _validate_riff_header(src, src_path: str) -> int:
    """Validates RIFF/WAVE header and returns total file size."""
    header = src.read(12)
    if len(header) < 12:
        raise ValueError(f"File too small to be a WAV file: {src_path}")

    magic = header[0:4]
    if magic == b"RIFX":
        raise ValueError("Big-endian RIFX files are not supported")
    if magic == b"RF64":
        raise ValueError("RF64 files are not supported")
    if magic != RIFF_HEADER:
        raise ValueError(f"Not a valid WAV file (missing RIFF header): {src_path}")
    if header[8:12] != WAVE_ID:
        raise ValueError(f"Not a valid WAV file (missing WAVE identifier): {src_path}")

    src.seek(0, 2)
    file_size = src.tell()
    src.seek(12)
    return file_size


def _skip_src_pad(src, data_size: int) -> None:
    """Skips the pad byte in source if chunk data size is odd."""
    if data_size % 2 != 0:
        src.read(1)


def _process_list_chunk(src, dst, data_size, metadata, state):
    """Handle LIST chunks — update INFO, pass through others (e.g., adtl)."""
    if data_size < 4:
        # Malformed LIST, just copy raw
        raw = src.read(data_size)
        _write_chunk(dst, CHUNK_LIST, raw)
        return

    list_type = src.read(4)
    remaining = data_size - 4

    if list_type == LIST_TYPE_INFO:
        if state["info_handled"]:
            src.read(remaining)
            return
        existing_data = src.read(remaining) if remaining > 0 else b""
        info_data = _build_list_info(metadata, existing_data)
        _write_chunk(dst, CHUNK_LIST, info_data)
        state["info_handled"] = True
    else:
        # Non-INFO LIST (e.g., adtl) — write type back + stream-copy remaining
        chunk_data = list_type + src.read(remaining)
        _write_chunk(dst, CHUNK_LIST, chunk_data)


def _process_chunk(src, dst, chunk_id, data_size, metadata, state):
    """Dispatches a single chunk: update bext/iXML/LIST-INFO, skip duplicates, or copy."""
    if chunk_id == CHUNK_BEXT:
        if state["bext_handled"]:
            src.seek(data_size, 1)
        else:
            bext_data = src.read(data_size)
            _write_chunk(dst, CHUNK_BEXT, _update_bext(bext_data, metadata))
            state["bext_handled"] = True
    elif chunk_id == CHUNK_IXML:
        if state["ixml_handled"]:
            src.seek(data_size, 1)
        else:
            ixml_data = src.read(data_size)
            _write_chunk(dst, CHUNK_IXML, _update_ixml(ixml_data, metadata))
            state["ixml_handled"] = True
    elif chunk_id == CHUNK_LIST:
        _process_list_chunk(src, dst, data_size, metadata, state)
    else:
        _stream_copy_chunk(src, dst, chunk_id, data_size)
    _skip_src_pad(src, data_size)


def _append_missing_chunks(dst, metadata, state) -> None:
    """Creates bext/iXML/LIST-INFO chunks from scratch if not in source."""
    has_bext = any(k in metadata for k in ("description", "designer"))
    has_ixml = any(k in metadata for k in (*USER_KEY_MAP, *ASWG_KEY_MAP)) or bool(
        metadata.get("custom_fields")
    )

    if not state["bext_handled"] and has_bext:
        _write_chunk(dst, CHUNK_BEXT, _build_new_bext(metadata))
    if not state["ixml_handled"] and has_ixml:
        _write_chunk(dst, CHUNK_IXML, _build_new_ixml(metadata))
    if not state["info_handled"] and _has_info_fields(metadata):
        info_data = _build_list_info(metadata)
        _write_chunk(dst, CHUNK_LIST, info_data)


def _rewrite_wav(src_path: str, dst_file, metadata: dict):
    """Reads src_path, writes rewritten WAV to dst_file handle."""
    with open(src_path, "rb") as src:
        file_size = _validate_riff_header(src, src_path)

        dst_file.write(RIFF_HEADER)
        dst_file.write(b"\x00\x00\x00\x00")
        dst_file.write(WAVE_ID)

        state = {"bext_handled": False, "ixml_handled": False, "info_handled": False}

        while src.tell() < file_size:
            chunk_header = src.read(8)
            if len(chunk_header) < 8:
                break

            chunk_id = chunk_header[0:4]
            data_size = struct.unpack("<I", chunk_header[4:8])[0]
            data_offset = src.tell()

            if data_offset + data_size > file_size:
                data_size = file_size - data_offset

            _process_chunk(src, dst_file, chunk_id, data_size, metadata, state)

        _append_missing_chunks(dst_file, metadata, state)

        total_size = dst_file.tell()
        dst_file.seek(4)
        dst_file.write(struct.pack("<I", total_size - 8))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def write_metadata(file_path: str, metadata: dict) -> None:
    """
    Writes metadata to a WAV file's iXML and BEXT chunks.

    The file is rewritten atomically: a temp file is created alongside the
    original, the rewritten WAV is written to the temp file, and then the
    temp file replaces the original. If any error occurs, the original file
    is left untouched.

    Args:
        file_path: Path to the WAV file to update.
        metadata:  Dictionary of field values to write. Recognized keys:
                   category, subcategory, cat_id, category_full, fx_name,
                   description, keywords, notes, designer, library, project,
                   user_category, microphone, mic_perspective, rec_medium,
                   release_date, rating, is_designed.
                   Only keys present in the dict are written. Missing keys
                   leave existing values unchanged.

    Raises:
        ValueError: If the file is not a valid WAV file.
        OSError:    If the file cannot be read or written.
        PermissionError: If the file is read-only or locked.
    """
    file_path = os.path.abspath(file_path)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Cannot read file: {file_path}")

    if not os.access(file_path, os.W_OK):
        raise PermissionError(f"Cannot write to file (read-only): {file_path}")

    dir_name = os.path.dirname(file_path)
    fd, temp_path = tempfile.mkstemp(suffix=".wav.tmp", dir=dir_name)

    try:
        with os.fdopen(fd, "wb") as tmp:
            _rewrite_wav(file_path, tmp, metadata)

        # Atomic replace
        os.replace(temp_path, file_path)

    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Convenience: Read-back verification
# ---------------------------------------------------------------------------


def verify_write(file_path: str, metadata: dict) -> dict:
    """
    Reads back a WAV file after writing and checks that metadata was applied.
    Returns a dict with 'ok' (bool) and 'errors' (list of strings).

    Requires wavinfo to be installed.
    """
    try:
        from wavinfo import WavInfoReader
    except ImportError:
        return {"ok": False, "errors": ["wavinfo is not installed"]}

    try:
        info = WavInfoReader(file_path)
    except Exception as e:
        return {"ok": False, "errors": [f"Failed to read file: {e}"]}

    errors: list[str] = []
    _verify_bext(info, metadata, errors)
    ixml_root = _parse_ixml_for_verify(info)
    _verify_ixml(ixml_root, metadata, errors)
    _verify_aswg(ixml_root, metadata, errors)
    _verify_info(info, metadata, errors)
    return {"ok": len(errors) == 0, "errors": errors}


def _verify_bext(info, metadata: dict, errors: list[str]) -> None:
    """Checks BEXT description and originator against expected metadata."""
    if info.bext is None:
        return

    if "description" in metadata:
        bext_desc = info.bext.description
        if isinstance(bext_desc, bytes):
            bext_desc = bext_desc.rstrip(b"\x00").decode("ascii", errors="replace")
        expected = metadata["description"][:BEXT_DESCRIPTION_SIZE]
        if bext_desc.strip() != expected.strip():
            errors.append(
                f"BEXT description mismatch: expected '{expected}', got '{bext_desc}'"
            )

    if "designer" in metadata:
        bext_orig = info.bext.originator
        if isinstance(bext_orig, bytes):
            bext_orig = bext_orig.rstrip(b"\x00").decode("ascii", errors="replace")
        expected_orig = metadata["designer"][:BEXT_ORIGINATOR_SIZE]
        if bext_orig.strip() != expected_orig.strip():
            errors.append(
                f"BEXT originator mismatch: expected '{expected_orig}', got '{bext_orig}'"
            )


def _parse_ixml_for_verify(info) -> ET.Element | None:
    """Parse iXML source into an ElementTree root for verification."""
    if info.ixml is None or not info.ixml.source:
        return None

    xml_source = info.ixml.source
    if isinstance(xml_source, bytes):
        xml_source = xml_source.decode("utf-8", errors="replace")
    xml_source = xml_source.rstrip("\x00").strip()

    try:
        return ET.fromstring(xml_source)
    except ET.ParseError:
        return None


def _verify_ixml(root: ET.Element | None, metadata: dict, errors: list[str]) -> None:
    """Checks USER fields in iXML against expected metadata."""
    has_ixml_fields = any(k in metadata for k in USER_KEY_MAP) or bool(
        metadata.get("custom_fields")
    )
    if not has_ixml_fields:
        return

    if root is None:
        errors.append("No iXML chunk found in output file")
        return

    user = root.find("USER")
    if user is None:
        errors.append("No <USER> block found in iXML")
        return

    for dict_key, xml_tag in USER_KEY_MAP.items():
        if dict_key not in metadata:
            continue
        el = user.find(xml_tag)
        if el is None:
            errors.append(f"USER field <{xml_tag}> not found in iXML")
            continue
        actual = el.text or ""
        expected = str(metadata[dict_key])
        if actual != expected:
            errors.append(
                f"USER/<{xml_tag}> mismatch: expected '{expected}', got '{actual}'"
            )

    custom = metadata.get("custom_fields", {})
    for tag, expected in custom.items():
        el = user.find(tag) if user is not None else None
        actual = el.text if el is not None else None
        if actual != expected:
            errors.append(f"Custom field <{tag}>: expected '{expected}', got '{actual}'")


# Reverse of ASWG_KEY_MAP: ASWG tag → metadata dict key (for verify)
_ASWG_VERIFY_FIELDS: dict[str, str] = {
    "category": "category",
    "subCategory": "subcategory",
    "catId": "cat_id",
    "fxName": "fx_name",
    "creatorId": "creator_id",
    "sourceId": "source_id",
    "library": "library",
    "manufacturer": "manufacturer",
    "recType": "rec_type",
}


def _verify_aswg(root: ET.Element | None, metadata: dict, errors: list[str]) -> None:
    """Checks critical ASWG fields in iXML against expected metadata."""
    if root is None:
        return

    aswg = root.find("ASWG")
    if aswg is None:
        return

    for aswg_tag, dict_key in _ASWG_VERIFY_FIELDS.items():
        if dict_key not in metadata:
            continue
        el = aswg.find(aswg_tag)
        if el is None:
            continue
        actual = el.text or ""
        expected = str(metadata[dict_key])
        if actual != expected:
            errors.append(
                f"ASWG/<{aswg_tag}> mismatch: expected '{expected}', got '{actual}'"
            )


# Reverse of INFO_KEY_MAP: metadata key → (INFO tag bytes, wavinfo attr name)
_INFO_VERIFY_FIELDS: dict[str, tuple[str, str]] = {
    "fx_name": ("INAM", "title"),
    "designer": ("IART", "artist"),
    "category": ("IGNR", "genre"),
    "notes": ("ICMT", "comment"),
    "library": ("IPRD", "product"),
    "keywords": ("IKEY", "keywords"),
}


def _verify_info(info, metadata: dict, errors: list[str]) -> None:
    """Checks INFO sub-chunk fields against expected metadata."""
    if info.info is None:
        return

    for dict_key, (info_tag, attr) in _INFO_VERIFY_FIELDS.items():
        if dict_key not in metadata:
            continue
        actual = getattr(info.info, attr, None) or ""
        expected = metadata[dict_key]
        if actual.strip() != expected.strip():
            errors.append(
                f"INFO {info_tag} mismatch: expected '{expected}', got '{actual}'"
            )
