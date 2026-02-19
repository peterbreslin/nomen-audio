# Pipeline

High-level overview of what happens under the hood.

---

## Architecture

Two-process design: a Rust/Tauri shell owns the window and OS integration, a Python/FastAPI sidecar owns all file I/O and business logic. The Svelte frontend communicates with Python exclusively over HTTP/JSON on localhost — it never touches WAV files directly.

**Startup sequence:**

1. Tauri's `setup` hook calls `spawn_sidecar()`. In dev mode this runs `uv run -m app`; in production it launches the bundled `nomen-sidecar.exe` from the app's resource directory.
2. The Python process binds a random TCP port on `127.0.0.1`, prints `PORT=<n>` to stdout, then starts uvicorn. The `PORT=` line is the IPC contract.
3. Tauri reads stdout in a background thread, captures the port via an `mpsc` channel, and stores it in `SidecarState`. The frontend retrieves it via `invoke('get_sidecar_port')` and caches it — every subsequent API call is a plain HTTP request to `http://127.0.0.1:<port>` using the Tauri HTTP plugin (not browser `fetch`, which can't reach localhost in a webview).
4. On window close, Tauri calls `taskkill /F /T /PID` to kill the entire Python process tree.

**FastAPI lifespan** runs four steps in sequence: load UCS spreadsheets into memory, load settings from JSON, connect SQLite, start background ML model loading.

---

## Import

Triggered when the user picks a directory or drags files into the app. The frontend calls `POST /files/import`.

1. The directory is glob-scanned for `*.wav` files (optionally recursive).
2. For each WAV, a **fast file hash** is computed — SHA-256 of the first 4 KB + file size + mtime. This is a cache key, not a full-content hash.
3. If a DB record exists with an identical hash, the file hasn't changed — the cached record is returned immediately, skipping re-read.
4. Otherwise, `read_metadata()` extracts all metadata from the WAV file (see Metadata Reading below).
5. **Import fallbacks** bridge legacy metadata into iXML fields: BEXT `description` → `description`, BEXT `originator` → `designer`, INFO `INAM` → `fx_name`, INFO `IGNR` → `category`, etc. This is what makes the app useful for files that never had iXML.
6. If a cached analysis result exists for this file hash, the classification is deserialized and re-ranked with a fresh filename boost — so previously-analyzed files get their ML results instantly without re-running inference.
7. The record is upserted into SQLite. Stale records (files no longer on disk) are removed.

---

## Metadata Reading

`reader.py` uses the `wavinfo` library as its RIFF parser. It extracts four categories of metadata:

**Technical** (from `fmt` + `data` chunks): sample rate, bit depth, channels, duration, frame count, audio format, file size. Read-only — never written back.

**BEXT** (Broadcast Wave Extension): description (256 bytes), originator (32 bytes), origination date/time, time reference, coding history. Returns `None` if no `bext` chunk exists.

**RIFF INFO** (LIST-INFO sub-chunks): title (`INAM`), artist (`IART`), genre (`IGNR`), comment (`ICMT`), software, copyright, product (`IPRD`), keywords (`IKEY`). Returns `None` if absent.

**iXML** (the `iXML` chunk — case-sensitive ID): Where the real UCS metadata lives. Root must be `<BWFXML>`. Two sub-blocks are read:

- `<ASWG>` (Audio Semantic Working Group, camelCase tags) is read **first** — it's the lower-priority source. Tags like `category`, `subCategory`, `catId`, `fxName`, `creatorId`, `sourceId`, etc.
- `<USER>` (Soundminer/BaseHead convention, ALL CAPS tags) is read **second** and **overwrites** ASWG values for any overlapping fields. The USER block is considered authoritative. Tags: `CATEGORY`, `SUBCATEGORY`, `CATID`, `CATEGORYFULL`, `FXNAME`, `DESCRIPTION`, `KEYWORDS`, etc.
- **Custom fields**: Any `<USER>` child element whose tag is not in the known set (and not `EMBEDDER`) is collected into a `custom_fields` dict. This is how user-defined iXML tags round-trip through the system.

---

## UCS Engine

A pure in-memory lookup table loaded at startup from two Excel spreadsheets.

**Loading**: The main UCS spreadsheet (~753 rows) is parsed into `CatInfo` records keyed by CatID. A reverse index maps `(Category, Subcategory)` tuples to CatIDs. A second sheet provides category-level explanations.

**Synonym index**: Each CatID's comma-separated synonyms list is inverted into a lookup: lowercase synonym → list of CatIDs. An extras dict injects additional synonyms not in the official spreadsheet. This index is used by the ML filename boost and the fuzzy matcher.

**Public API**: `get_categories()` / `get_subcategories(cat)` for UI dropdowns, `lookup_catid(category, subcategory)` for canonical lookup, `get_catid_info(cat_id)` for full metadata. CatIDs are always looked up from the spreadsheet, never derived algorithmically.

---

## Filename Parsing & Generation

**Parsing** (`parse_filename`): Checks if the first underscore-separated block is a valid CatID. If yes, parses the UCS block structure: `{CatID[-UserCategory]}_{FXName}_{CreatorID}_{SourceID}[_{UserData}]`. Multi-word FXNames spanning multiple blocks are handled. If the first block is not a valid CatID, `fuzzy_match()` runs instead.

**Fuzzy matching**: Tokenizes the filename (splits on `_`, `-`, space, camelCase boundaries), lowercases, deduplicates, then scores each CatID by counting how many tokens appear in its synonym index or match its category/subcategory name (prefix-aware). Returns top-N matches by score.

**Generation** (`generate_filename`): Assembles `{CatID[-UserCategory]}_{FXName}_{CreatorID}_{SourceID}[_{UserData}].wav`. Missing `creator_id`/`source_id` fall back to global settings defaults. Missing `fx_name` defaults to `"Untitled"`. Illegal filesystem characters are stripped.

---

## Save

The most critical operation — writes bytes to disk and optionally renames the file.

1. **External-modification check**: The current file hash is compared against the stored hash. If they differ, a `409 FILE_CHANGED` error is raised — prevents silently overwriting someone else's changes.
2. **Rename pre-check**: If renaming is requested and the target path already exists, a `409 RENAME_CONFLICT` is raised **before writing anything**.
3. **Atomic write** (`write_metadata`):
   - Creates a temp file in the **same directory** as the original (critical for atomic `os.replace()` — same filesystem, no cross-device move).
   - Iterates every chunk in the source WAV:
     - `bext`: Unpacks existing binary, patches `description` and `originator`, repacks.
     - `iXML`: Parses existing XML, updates `<USER>` and `<ASWG>` blocks while **preserving all other XML elements byte-for-byte**.
     - `LIST-INFO`: Only **fills gaps** — existing INFO values are never overwritten.
     - All other chunks (including `data`, `fmt`, `smpl`): **Stream-copied** in 1 MB buffers. Audio data is never loaded into memory.
   - If the source had no bext/iXML/INFO chunks, they're appended from scratch.
   - RIFF size field is patched with the final file size.
   - On any exception, the temp file is deleted. The original is untouched.
   - `os.replace(temp_path, original_path)` atomically swaps in the new file.
4. **Verify**: Re-opens the written file with `wavinfo` and checks every field — BEXT description/originator, all USER tags, critical ASWG tags, INFO sub-chunks, custom fields. If any mismatch, a `500 WRITE_FAILED` is raised.
5. **Rename**: If requested, `os.replace(old_path, target_path)`. DB record updated with new path, fresh hash, status `"saved"`, `changed_fields` cleared.

---

## Machine Learning Components

CLAP tells you what category the sound belongs to. ClapCap tells you what the sound actually sounds like in plain English. Together they fill in the full metadata set — category, subcategory, filename, description, and keywords — from the audio alone.

### Classifier

Uses the pre-trained [MS-CLAP 2023](https://github.com/microsoft/CLAP) model to compare an asset to various audio embeddings against text embeddings for all 753 UCS subcategories. It's zero-shot and works to understand semantic relationship between sounds and text descriptions. The subcategories have been modified to include two text prompts (a curated acoustic description + the raw UCS explanation), and the scores from the model output are blended. The filename is also tokenized and keyword-matched against UCS synonyms, then combined with the CLAP score to produce a final ranking. Output: top-N subcategory matches with confidence scores, which map directly to UCS category, subcategory, CatID, and a suggested filename.

### Captioner

Uses MS-CLAP's clapcap variant, which pairs CLAP audio embeddings with a GPT-2 decoder to generate natural language captions (e.g. "a wooden door creaking open slowly with a long metallic squeak"). That caption populates the Description field; key terms are extracted for FX Name. The model is lazy-loaded on first use (~2.1 GB).

---

## Analysis & Suggestions

**Triggering analysis** (`POST /files/{id}/analyze`):

1. Models must be loaded (returns `503` otherwise). Cache is checked by file hash — on hit with `force=false`, cached results are re-ranked with a fresh filename boost (so results reflect the current filename even after renames).
2. On cache miss, CLAP runs in a thread pool (`asyncio.to_thread`). If Tier 2 is requested, the captioner runs next. Raw results (pre-filename-boost) are cached in SQLite keyed by file hash.
3. **Filename boost**: `fuzzy_match()` runs on the filename, then blends CLAP confidence with keyword match score using log-space softmax. The weight (`alpha=10.0`) is high enough that strong keyword matches dominate over acoustic confidence — useful for files with descriptive names.

**Suggestion generation**: The top CLAP match is mapped to category, subcategory, cat_id, category_full. Keywords are pulled from the UCS synonym list for that CatID (up to 10). A suggested filename is assembled from `generate_filename()` using settings defaults. If captioning ran (Tier 2), the raw caption becomes the `description` suggestion and key terms are extracted for `fx_name`.

**Suggestions are not persisted.** They are recomputed from stored analysis data on every read (in `list_files` and `get_file`). This ensures suggestions always reflect current settings (e.g., if the user changes their `creator_id`, all filenames update).

**The user decision boundary:** Suggestions appear as proposals in the UI. The user accepts them individually (optimistic local update + `PUT /metadata`) or dismisses them (frontend-only state). Nothing reaches disk until an explicit save action.

---

## Frontend State

**`FileStore`** (Svelte 5 `$state` runes): Single source of truth for all file state.

- `files: Map<string, FileRecord>` — all imported files.
- `selectedFileIds: Set<string>` — supports single, ctrl-click, and shift-range selection.
- `activeFileId` — file loaded in waveform player (decoupled from selection).
- `aiGeneratedFields` / `manualEditedFields` — per-file, per-field tracking for the dot badge indicators (cyan = AI-filled, gold = manually edited).
- `updateFieldLocally()` is an **optimistic update** — immediately patches the in-memory record and marks the field in `changed_fields` before the API round-trip completes.
- `visibleFiles` applies status/text filters and folder expansion state.

**Other stores**: `UIStore` (sidebar, column expansion, cell editing), `UCSStore` (category tree for dropdowns), `SettingsStore` (settings singleton), `ModelsStore` (ML model loading status, polled).

---

## Settings & Custom Fields

`settings.py` is a JSON-persisted singleton with atomic writes. Key fields: `creator_id` and `source_id` (default identifiers stamped on generated filenames), `library_template` (format string for the library field), `rename_on_save_default`, and `custom_fields`.

**Custom fields flow**: User defines a field in Settings (e.g., tag: `PROJECTCODE`, label: "Project Code"). Tags must match `[A-Z0-9_]+`, max 32 chars, and cannot collide with the 20 built-in USER tags. On read, any unknown `<USER>` element lands in the `custom_fields` dict. On write, custom fields are appended to `<USER>` alongside standard fields. In the sheet view, custom fields appear as a dynamic "CUSTOM" column group derived reactively from the settings store.
