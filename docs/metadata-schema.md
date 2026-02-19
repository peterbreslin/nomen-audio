# WAV Metadata Schema Documentation

This document provides a comprehensive breakdown of the metadata structures found in professional WAV files as parsed by the `wavinfo` library. It categorizes data into **Core Descriptive Metadata** (used for searching and organization) and **Technical Metadata** (used for physical file description).

---

## 1. Core Descriptive Metadata

These sections contain human-readable information used by Sound Designers and Librarians to identify, categorize, and credit audio assets.

### RIFF INFO (`info`)

The most widely compatible metadata standard. Visible in standard operating system file explorers.

| Field               | Description                         | Example                        |
| :------------------ | :---------------------------------- | :----------------------------- |
| `title`             | The formal name of the sound.       | Chaos Morph Sweep 01           |
| `artist`            | The creator or recordist.           | John Doe                       |
| `genre`             | High-level category.                | DESIGNED                       |
| `comment`           | A general description of the sound. | Granular processed synth sweep |
| `created_date`      | The date the file was finalized.    | 2025-01-17                     |
| `software`          | The tool used to inject metadata.   | Soundminer                     |
| `archival_location` | Often used to show the source DAW.  | REAPER                         |
| `copyright`         | Legal ownership information.        | 2025 (IG Cybernetics)          |

### BEXT (Broadcast Wave Extension)

The professional broadcast standard. Essential for workflow synchronization.

| Field             | Description                                                                 | Example                         |
| :---------------- | :-------------------------------------------------------------------------- | :------------------------------ |
| `description`     | Primary text description of the file.                                       | Cybernetics Texture Abstract... |
| `originator`      | The application that created the WAV.                                       | REAPER                          |
| `originator_date` | Creation date (BEXT specific).                                              | 2025-01-17                      |
| `time_reference`  | **Timeline Timestamp.** Location in samples from midnight or project start. | 35450002                        |
| `umid`            | Unique Material Identifier (usually null/zeros in SFX).                     | `b'\x00...'`                    |

### iXML (Production Metadata)

An XML-based container inside the `iXML` RIFF chunk (case-sensitive ID). Root element is `<BWFXML>`. Contains top-level fields (project, scene, take, tape, track_list) and two sub-blocks that NomenAudio reads and writes:

#### `<USER>` Block (Authoritative)

Soundminer/BaseHead convention. ALL CAPS tag names. **Read second during import — overwrites ASWG values for overlapping fields.**

| Tag              | Metadata Key      | Description                    |
| :--------------- | :---------------- | :----------------------------- |
| `CATEGORY`       | `category`        | UCS top-level category         |
| `SUBCATEGORY`    | `subcategory`     | UCS subcategory                |
| `CATID`          | `cat_id`          | UCS CatID code                 |
| `CATEGORYFULL`   | `category_full`   | `CATEGORY-SUBCATEGORY`         |
| `FXNAME`         | `fx_name`         | Short descriptive title        |
| `DESCRIPTION`    | `description`     | Detailed description           |
| `KEYWORDS`       | `keywords`        | Comma-separated search terms   |
| `NOTES`          | `notes`           | Additional notes               |
| `DESIGNER`       | `designer`        | Creator/recordist              |
| `LIBRARY`        | `library`         | Library name                   |
| `USERCATEGORY`   | `user_category`   | User-defined category          |
| `MICROPHONE`     | `microphone`      | Mic model                      |
| `MICPERSPECTIVE` | `mic_perspective` | Mic perspective (close/far)    |
| `RECMEDIUM`      | `rec_medium`      | Recording medium               |
| `RELEASEDATE`    | `release_date`    | Release date                   |
| `RATING`         | `rating`          | Quality rating                 |
| `MANUFACTURER`   | `manufacturer`    | Equipment/content manufacturer |
| `RECTYPE`        | `rec_type`        | Recording type                 |
| `CREATORID`      | `creator_id`      | Creator identifier             |
| `SOURCEID`       | `source_id`       | Source identifier              |
| `EMBEDDER`       | _(written only)_  | Always set to `"NomenAudio"`   |

Any `<USER>` child element whose tag is not in the above list (and not `EMBEDDER`) is collected into `custom_fields` — a `dict[str, str]` keyed by the raw XML tag name. This is how user-defined iXML tags round-trip through the system.

#### `<ASWG>` Block (Secondary)

Audio Semantic Working Group standard. camelCase tag names. **Read first during import — USER values take precedence for overlapping fields.**

| Tag            | Metadata Key     | Description                    |
| :------------- | :--------------- | :----------------------------- |
| `category`     | `category`       | UCS category                   |
| `subCategory`  | `subcategory`    | UCS subcategory                |
| `catId`        | `cat_id`         | UCS CatID                      |
| `userCategory` | `user_category`  | User-defined category          |
| `fxName`       | `fx_name`        | Short descriptive title        |
| `library`      | `library`        | Library name                   |
| `notes`        | `notes`          | Notes                          |
| `project`      | `project`        | Project name                   |
| `micType`      | `microphone`     | Microphone type                |
| `isDesigned`   | `is_designed`    | Designed vs. raw recording     |
| `manufacturer` | `manufacturer`   | Manufacturer                   |
| `recType`      | `rec_type`       | Recording type                 |
| `creatorId`    | `creator_id`     | Creator identifier             |
| `sourceId`     | `source_id`      | Source identifier              |
| `originator`   | `designer`       | _(extra mapping)_ Creator name |
| `contentType`  | _(written only)_ | Always set to `"sfx"`          |

#### Custom Fields

User-defined `<USER>` tags configured in Settings. Each has a `tag` (must match `[A-Z0-9_]+`, max 32 chars, no collision with built-in tags) and a `label` (display name for the UI). Custom fields are stored as a JSON dict in the database and appear as editable columns in the sheet view.

#### Other iXML Elements

Top-level iXML fields (`project`, `scene`, `take`, `tape`, `track_list`) and vendor blocks (e.g., `steinberg`) are **preserved byte-for-byte** during writes — NomenAudio does not modify or delete any iXML element it doesn't own.

---

## 2. Timeline & Navigation

Metadata that describes points of interest _within_ the audio duration.

### CUES (`cues`)

A dictionary of markers embedded in the file.

- **ID (1, 2, 3...):** The marker number.
- **frame:** The exact sample position of the marker.
- **label:** The name of the marker (e.g., "Impact Start"). Note: Labels are often stored in a separate `ADTL` chunk but linked to these IDs.

---

## 3. Technical & Verbose Metadata

This data describes the "physical" properties of the file container and the encoding methods.

### FMT (Audio Format)

| Field             | Description                       |
| :---------------- | :-------------------------------- |
| `audio_format`    | 1 = PCM (Uncompressed).           |
| `channel_count`   | 1 = Mono, 2 = Stereo, etc.        |
| `sample_rate`     | Frequency in Hz (e.g., 96000).    |
| `bits_per_sample` | Resolution (e.g., 24-bit).        |
| `block_align`     | Number of bytes per sample frame. |

### DATA (Payload Descriptor)

| Field         | Description                                                       |
| :------------ | :---------------------------------------------------------------- |
| `byte_count`  | Total size of the raw audio data (excluding metadata).            |
| `frame_count` | Total number of samples (Length = `frame_count` / `sample_rate`). |

### MAIN_LIST (File DNA)

This is a map of the WAV file's physical structure. It lists every **Chunk Descriptor** found in the file:

- **ident:** The 4-character ID of the chunk (e.g., `fmt`, `data`, `iXML`, `SMED`).
- **start:** The byte offset where that chunk begins in the file.
- **length:** The size of that specific chunk in bytes.

### Encoding & Pathing

- **`info_encoding`:** Character set for RIFF tags (usually `latin_1`).
- **`bext_encoding`:** Character set for BEXT tags (usually `ascii`).
- **`path`:** The absolute local directory path where the file was analyzed.
- **`url`:** The RFC 3986 compliant file URL.

---

## 4. Specialty & Proprietary Chunks

Additional chunks found in high-end sound effects libraries.

- **SMED:** Soundminer Extended Data. Proprietary chunk containing Soundminer’s internal database info, pitch offsets, and thesaurus keywords.
- **ID3:** An embedded MP3-style tag chunk within the WAV, used for compatibility with consumer players like iTunes.
- **\_PMX:** Adobe XMP Metadata. Contains history and synchronization data for Adobe Premiere and Audition.
- **SMPL:** Sampler chunk. Contains MIDI unity note and loop points for use in virtual instruments (e.g., Kontakt, Halion).
- **ADM / DOLBY:** Metadata for Object-based spatial audio (Dolby Atmos). Defines 3D coordinates for sound objects.

---

## 5. Metadata Fallback Rules

iXML is the source of truth after import. BEXT and INFO carry overlapping data that should be merged at import time and flowed back at save time.

### 5a. Import-time merge (BEXT/INFO → iXML)

When importing a file, if an iXML field is empty but the mapped BEXT or INFO field has a value, copy it into the iXML field. This ensures the user sees the best available data in the editing UI.

| iXML target   | BEXT source        | INFO source            |
| :------------ | :----------------- | :--------------------- |
| `description` | BEXT `description` | —                      |
| `designer`    | BEXT `originator`  | INFO `artist` (IART)   |
| `fx_name`     | —                  | INFO `title` (INAM)    |
| `category`    | —                  | INFO `genre` (IGNR)    |
| `notes`       | —                  | INFO `comment` (ICMT)  |
| `library`     | —                  | INFO `product` (IPRD)  |
| `keywords`    | —                  | INFO `keywords` (IKEY) |

**Precedence:** BEXT overrides INFO for overlapping fields. BEXT is more authoritative in broadcast contexts (e.g., `designer` prefers BEXT `originator` over INFO `artist`).

### 5b. Save-time fallback (iXML → BEXT/INFO)

When saving, if a BEXT or INFO field is empty, populate it from the iXML equivalent (reverse of the table above). Never overwrite existing BEXT/INFO values — only fill gaps.

This requires a LIST-INFO chunk writer (Phase 2C.9) for writing INFO sub-chunks (INAM, IART, IGNR, ICMT, IPRD, IKEY). The BEXT writer already exists.
