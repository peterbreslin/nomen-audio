"""Synthetic WAV fixture factory for RIFF writer tests.

Builds minimal valid WAV files in memory — no external file dependencies.
"""

import struct
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants — reusable XML templates
# ---------------------------------------------------------------------------

MINIMAL_IXML = '<?xml version="1.0" encoding="UTF-8"?><BWFXML><IXML_VERSION>1.61</IXML_VERSION></BWFXML>'

IXML_WITH_USER = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<BWFXML>"
    "<IXML_VERSION>1.61</IXML_VERSION>"
    "<USER>"
    "<CATEGORY>AMBIENCE</CATEGORY>"
    "<FXNAME>Forest Birds</FXNAME>"
    "<EMBEDDER>OtherTool</EMBEDDER>"
    "<MICROPHONE>MKH416</MICROPHONE>"
    "</USER>"
    "</BWFXML>"
)

IXML_WITH_VENDOR = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<BWFXML>"
    "<IXML_VERSION>1.61</IXML_VERSION>"
    "<STEINBERG><PRODUCT>Nuendo</PRODUCT></STEINBERG>"
    "<USER>"
    "<CATEGORY>AMBIENCE</CATEGORY>"
    "<FXNAME>Forest Birds</FXNAME>"
    "<MICROPHONE>MKH416</MICROPHONE>"
    "</USER>"
    "<ASWG><category>AMBIENCE</category></ASWG>"
    "</BWFXML>"
)

TEST_METADATA = {
    "category": "WEATHER",
    "subcategory": "THUNDER",
    "cat_id": "WTHRThun",
    "category_full": "WEATHER-THUNDER",
    "fx_name": "Thunder Rumble Low",
    "description": "Deep rolling thunder rumble with distant crack",
    "keywords": "thunder, rumble, storm, weather, rolling, distant",
    "notes": "Test write from NomenAudio",
    "designer": "TESTUSER",
    "library": "TESTLIB",
}

# ---------------------------------------------------------------------------
# BEXT builder
# ---------------------------------------------------------------------------

BEXT_FIXED_SIZE = 602


def build_bext_data(description: str = "", originator: str = "") -> bytes:
    """Builds a 602-byte BEXT block with optional description/originator."""
    data = bytearray(BEXT_FIXED_SIZE)
    desc_bytes = description.encode("ascii", errors="replace")[:256]
    data[0 : len(desc_bytes)] = desc_bytes
    orig_bytes = originator.encode("ascii", errors="replace")[:32]
    data[256 : 256 + len(orig_bytes)] = orig_bytes
    # origination_date at offset 320 (10 bytes)
    date_str = b"2024-01-01"
    data[320 : 320 + len(date_str)] = date_str
    # version at offset 346 (uint16 LE) = 1
    struct.pack_into("<H", data, 346, 1)
    return bytes(data)


# ---------------------------------------------------------------------------
# WAV builder
# ---------------------------------------------------------------------------


def build_wav(
    *,
    num_samples: int = 100,
    sample_rate: int = 44100,
    channels: int = 1,
    bits_per_sample: int = 16,
    bext_data: bytes | None = None,
    ixml_xml: str | None = None,
    ixml_raw_bytes: bytes | None = None,
    extra_chunks: list[tuple[bytes, bytes]] | None = None,
) -> bytes:
    """Builds a minimal valid WAV file in memory.

    Args:
        num_samples: Number of audio samples per channel.
        sample_rate: Sample rate in Hz.
        channels: Number of audio channels.
        bits_per_sample: Bits per sample (8 or 16).
        bext_data: Raw BEXT chunk data (602+ bytes). Added as bext chunk.
        ixml_xml: XML string for iXML chunk (UTF-8 encoded).
        ixml_raw_bytes: Raw bytes for iXML chunk (mutually exclusive with ixml_xml).
        extra_chunks: List of (chunk_id_4bytes, chunk_data) to append.

    Returns:
        Complete WAV file as bytes.
    """
    if ixml_xml is not None and ixml_raw_bytes is not None:
        raise ValueError("ixml_xml and ixml_raw_bytes are mutually exclusive")

    buf = bytearray()

    # --- RIFF header placeholder ---
    buf += b"RIFF"
    buf += b"\x00\x00\x00\x00"  # placeholder
    buf += b"WAVE"

    # --- fmt chunk ---
    byte_rate = sample_rate * channels * (bits_per_sample // 8)
    block_align = channels * (bits_per_sample // 8)
    fmt_data = struct.pack(
        "<HHIIHH",
        1,  # PCM
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
    )
    _append_chunk(buf, b"fmt ", fmt_data)

    # --- bext chunk ---
    if bext_data is not None:
        _append_chunk(buf, b"bext", bext_data)

    # --- data chunk ---
    bytes_per_sample = bits_per_sample // 8
    data_size = num_samples * channels * bytes_per_sample
    # Generate simple ascending samples
    audio = bytearray(data_size)
    for i in range(num_samples * channels):
        if bits_per_sample == 16:
            val = (i % 256) - 128  # -128..127 range
            struct.pack_into("<h", audio, i * 2, val)
        else:
            audio[i] = i % 256
    _append_chunk(buf, b"data", bytes(audio))

    # --- iXML chunk ---
    if ixml_xml is not None:
        ixml_bytes = ixml_xml.encode("utf-8")
        _append_chunk(buf, b"iXML", ixml_bytes)
    elif ixml_raw_bytes is not None:
        _append_chunk(buf, b"iXML", ixml_raw_bytes)

    # --- extra chunks ---
    if extra_chunks:
        for chunk_id, chunk_data in extra_chunks:
            _append_chunk(buf, chunk_id, chunk_data)

    # --- Fix RIFF size ---
    struct.pack_into("<I", buf, 4, len(buf) - 8)

    return bytes(buf)


def _append_chunk(buf: bytearray, chunk_id: bytes, data: bytes) -> None:
    """Appends a RIFF chunk (id + size + data + pad) to buf."""
    buf += chunk_id
    buf += struct.pack("<I", len(data))
    buf += data
    if len(data) % 2 != 0:
        buf += b"\x00"


def build_info_chunk(fields: dict[bytes, str]) -> tuple[bytes, bytes]:
    """Build a LIST-INFO chunk for use with build_wav(extra_chunks=[...])."""
    data = bytearray(b"INFO")
    for tag, value in fields.items():
        encoded = value.encode("ascii") + b"\x00"
        data += tag
        data += struct.pack("<I", len(encoded))
        data += encoded
        if len(encoded) % 2 != 0:
            data += b"\x00"
    return (b"LIST", bytes(data))


def write_wav(tmp_path: Path, filename: str = "test.wav", **kwargs) -> Path:
    """Writes build_wav() output to a file, returns the path."""
    wav_bytes = build_wav(**kwargs)
    p = tmp_path / filename
    p.write_bytes(wav_bytes)
    return p


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def count_chunks(wav_bytes: bytes, target_id: bytes) -> int:
    """Counts occurrences of a chunk ID in raw WAV bytes."""
    count = 0
    pos = 12  # skip RIFF header
    while pos + 8 <= len(wav_bytes):
        chunk_id = wav_bytes[pos : pos + 4]
        data_size = struct.unpack_from("<I", wav_bytes, pos + 4)[0]
        if chunk_id == target_id:
            count += 1
        pos += 8 + data_size
        if data_size % 2 != 0:
            pos += 1  # pad byte
    return count


def parse_ixml_source(info) -> ET.Element | None:
    """Extracts and parses iXML from a WavInfoReader instance."""
    if info.ixml is None or not info.ixml.source:
        return None
    src = info.ixml.source
    if isinstance(src, bytes):
        src = src.decode("utf-8", errors="replace")
    src = src.rstrip("\x00").strip()
    try:
        return ET.fromstring(src)
    except ET.ParseError:
        return None


def get_user_field(root: ET.Element, tag: str) -> str | None:
    """Gets text of a field inside <USER>."""
    el = root.find(f"USER/{tag}")
    return el.text if el is not None else None


def get_aswg_field(root: ET.Element, tag: str) -> str | None:
    """Gets text of a field inside <ASWG>."""
    el = root.find(f"ASWG/{tag}")
    return el.text if el is not None else None
