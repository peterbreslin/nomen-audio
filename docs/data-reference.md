# Nomen Audio — Data & File Reference

> **Purpose:** A complete inventory of every data file, reference specification, and generated dataset required to build and run Nomen Audio — excluding user-provided WAV files. For each item: what it is, where it comes from, what format it's in, what information we extract from it, and how it's used in the pipeline.

---

## 1. UCS 8.2.1 Spreadsheet

### What It Is

The official Universal Category System data file. A single Excel workbook containing the complete taxonomy of sound effect categories, their abbreviated codes, descriptions, synonyms, and translations.

### Source

Downloaded from the UCS Dropbox repository linked at [universalcategorysystem.com](https://universalcategorysystem.com/). The file is publicly available (public domain). UCS 8.2.1 is the declared final version — it will not be updated.

### Format

`.xlsx` (Excel workbook), approximately 2MB. Contains multiple sheets.

### Key Sheets and Columns

**Main category sheet** (typically named "UCS v8.2" or similar):

| Column (expected) | Content                                               | Example                                                                        |
| ----------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------ |
| Category          | Top-level category name (ALL CAPS)                    | `DOORS`                                                                        |
| SubCategory       | Second-level category name (ALL CAPS)                 | `WOOD`                                                                         |
| CatID             | Abbreviated code for Category + SubCategory           | `DOORWood`                                                                     |
| CatShort          | Abbreviated code for Category only                    | `DOOR`                                                                         |
| CategoryFull      | `CATEGORY-SUBCATEGORY` combined                       | `DOORS-WOOD`                                                                   |
| Explanation       | Description of what sounds belong in this subcategory | `Wooden doors of all types, including cabinet doors, screen doors, barn doors` |
| Synonyms          | Comma-separated list of related terms                 | `timber, plank, panel, lumber, oak, pine`                                      |

**Translations sheet** (typically named "Translations" or "Full Translations"):

Contains the Category and SubCategory names translated into 20 languages. Not critical for MVP but available for future internationalization.

### What We Extract at Startup

The UCS spreadsheet is parsed once when the Python backend starts. The following data structures are built in memory:

1. **Category list:** A flat list of all 82 top-level categories. Used to populate the Category dropdown in the UI.

2. **SubCategory lookup:** A dictionary mapping each Category to its list of valid SubCategories. Used to populate the filtered SubCategory dropdown.

3. **CatID lookup:** A bidirectional mapping: CatID → (Category, SubCategory, CategoryFull) and (Category, SubCategory) → CatID. Used for auto-computing the CatID field, for validating CatIDs parsed from filenames, and for mapping CLAP classification results to UCS categories.

4. **Synonym lookup:** A dictionary mapping each CatID to its list of synonyms. Used for keyword generation (when a sound is classified as `DOORWood`, the synonyms become suggested keywords) and for fuzzy filename matching (if a file is named `timber_door_creak.wav`, the word "timber" matches a synonym for DOORS-WOOD).

5. **Explanation lookup:** A dictionary mapping each CatID to its explanation text. Used as the basis for generating CLAP text labels (see §2).

### Bundling

The `.xlsx` file is included directly in the application package (inside the PyInstaller binary's bundled data, or as a resource file alongside it). It is never modified by the application.

### Parsing Library

`openpyxl` reads the `.xlsx` file. The parsing code should be tolerant of minor formatting differences (whitespace in headers, sheet name variations) since we can't guarantee the exact internal layout won't have trivial differences across copies.

### Important Note

Before writing the parser, the actual downloaded spreadsheet must be inspected to confirm the exact sheet names, column headers, and row layout. The column names listed above are based on documented UCS conventions but may differ slightly in the actual file (e.g., the column might be labeled "Cat ID" with a space, or "CATId"). The parser should be written against the real file, not assumptions.

---

## 2. CLAP Text Label Set

### What It Is

A JSON file containing the set of natural-language phrases that the CLAP model compares audio against during zero-shot classification. Each phrase describes a type of sound. CLAP computes the similarity between an audio file's embedding and each phrase's embedding to determine which sounds the audio most closely matches.

### Source

**Generated by us** — not downloaded from an external source. The generation is automated via a Python script that reads the UCS spreadsheet and produces the label set.

### Format

`.json` file, approximately 200-500KB. Structure:

```json
{
  "labels": [
    {
      "catid": "DOORWood",
      "category": "DOORS",
      "subcategory": "WOOD",
      "phrases": [
        "This is a sound of a wooden door",
        "This is a sound of a wooden door opening",
        "This is a sound of a wooden door closing",
        "This is a sound of a wooden door slamming shut",
        "This is a sound of a creaky wood door"
      ]
    },
    {
      "catid": "DOORMetl",
      "category": "DOORS",
      "subcategory": "METAL",
      "phrases": [
        "This is a sound of a metal door",
        "This is a sound of a heavy metal door closing",
        "This is a sound of a steel door slamming"
      ]
    }
  ]
}
```

### How It's Generated

The generation script performs three steps:

**Step 1 — Base phrases (automated):**
For each of the 753 UCS subcategories, read the `Explanation` field from the spreadsheet and produce: `"This is a sound of {explanation text}"`. This is a one-liner per subcategory. Produces 753 base phrases.

**Step 2 — Synonym expansion (automated):**
For each subcategory, read its `Synonyms` column. For each synonym (or small synonym group), produce an additional phrase: `"This is a sound of {synonym}"` or `"This is a sound of {category} {synonym}"`. This produces 2-5 additional phrases per subcategory, depending on how many synonyms exist. Total: roughly 2,000-4,000 phrases.

**Step 3 — Optional quality tuning (manual, optional):**
After testing CLAP against sample audio files, specific phrases that perform poorly can be reworded. For example, if `"This is a sound of geothermal"` doesn't match well with geyser recordings, it could be changed to `"This is a sound of a geyser erupting"`. This step is entirely optional and only needed if classification accuracy on specific categories is noticeably poor.

### How It's Used at Runtime

When the Python backend starts:

1. Load the label JSON file.
2. Extract all phrase strings into a flat list.
3. Run each phrase through CLAP's text encoder to produce a 512-dimensional text embedding.
4. Store all text embeddings in a NumPy array (shape: `[num_phrases, 512]`), along with a mapping from each embedding index back to its CatID.

When a WAV file is analyzed:

1. Run the audio through CLAP's audio encoder to produce a 512-dimensional audio embedding.
2. Compute cosine similarity between the audio embedding and every text embedding.
3. The highest-scoring phrases indicate which UCS subcategories the audio most closely matches.
4. Group scores by CatID (since each CatID has multiple phrases), take the max score per CatID, and return the top-N CatIDs as classification results.

### Bundling

The JSON file is bundled with the application. The generation script is a development-time tool (run once to produce the JSON, then the JSON is included in the build). The script should also be kept in the repo so the label set can be regenerated if the phrasing strategy changes.

### Startup Cost

Computing text embeddings for 2,000-4,000 phrases takes approximately 30-60 seconds on CPU. This happens once per app launch. The frontend should show a loading indicator during this time ("Preparing ML models…"). The computed embeddings could optionally be cached to disk (as a `.npy` file) to skip this step on subsequent launches, but this is a nice-to-have optimization.

---

## 3. MS-CLAP 2023 Model Weights

### What It Is

The pre-trained weights for the MS-CLAP 2023 model. This is the core ML model that produces audio and text embeddings for classification and similarity search.

### Source

Zenodo — auto-downloaded by the `msclap` package on first use. No manual download or HuggingFace cache configuration needed; `msclap` manages its own model cache.

### Format

Multiple files totaling approximately 690MB (model weights + configuration).

### How It's Used

Loaded once at startup (after download). API: `CLAP(version='2023', use_cuda=False)`. Two operations:

1. **Text encoding:** `get_text_embeddings(prompts)` — takes a list of text strings → returns text embedding matrix.
2. **Audio encoding:** `get_audio_embeddings(file_paths)` — takes a list of WAV file paths → returns audio embedding matrix.

These two types of embeddings live in the same vector space, so cosine similarity between them is meaningful (via `compute_similarity()`).

### Bundling

**Not bundled.** Downloaded on first launch. The application checks if the model files exist; if not, it triggers a download with a progress indicator in the UI.

---

## 4. Microsoft CLAP / clapcap Model Weights

### What It Is

Microsoft's CLAP model in its `clapcap` configuration — an audio captioning model that generates natural-language descriptions of audio content. Unlike MS-CLAP 2023 (which produces embeddings for comparison), clapcap produces text output. Both models share the same HTSAT-base audio encoder, so they operate in the same embedding space.

### Source

Downloaded automatically by the `msclap` Python package when `CLAP(version='clapcap')` is called for the first time. Weights are hosted on Zenodo and/or HuggingFace.

### Format

Multiple files totaling approximately 200-400MB (exact size depends on the checkpoint version). Includes model weights and configuration files.

### How It's Used

Loaded on demand (not at startup — only when the user first triggers analysis, to keep startup time reasonable). Given a WAV file, produces a text caption:

```python
from msclap import CLAP
clap_model = CLAP(version='clapcap', use_cuda=False)
captions = clap_model.generate_caption(file_paths=["door_creak.wav"])
# Returns: ["a wooden door creaking open and closing"]
```

The raw caption text is then:

1. Cleaned with heuristic rules (capitalize first word, remove trailing periods, trim whitespace).
2. Used as the suggested **Description** field.
3. Parsed for key noun/verb phrases to help construct the suggested **FXName** field.

### Bundling

**Not bundled.** Downloaded on first demand. Can share the download progress indicator with the MS-CLAP 2023 model download, or be triggered separately.

### Note on Compatibility

Both models use the same `msclap` package. No cross-package version conflicts.

---

## 5. iXML Specification Reference

### What It Is

The technical specification for the iXML metadata format — the XML schema that defines what tags are valid inside an iXML RIFF chunk, their nesting structure, and their semantics.

### Source

The specification is maintained by Gallery UK and published at:

- Main spec: `http://www.gallery.co.uk/ixml/`
- Object details: `http://www.gallery.co.uk/ixml/object_Details.html`
- Usage guidelines: `http://www.gallery.co.uk/ixml/usage_guidelines.html`

### Format

This is reference documentation, not a data file. The relevant information is encoded directly into the RIFF writer source code.

### Key Information for the Writer

**XML structure of a minimal iXML chunk:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<BWFXML>
  <IXML_VERSION>1.61</IXML_VERSION>
  <PROJECT>My Game</PROJECT>
  <SCENE>LVL01</SCENE>
  <TAKE>1</TAKE>
  <TAPE>SESSION_A</TAPE>
  <NOTE>Wooden door in old cabin, close perspective</NOTE>
  <CIRCLED>FALSE</CIRCLED>
  <FILE_UID>ABCD1234-5678-EF90</FILE_UID>
  <TRACK_LIST>
    <TRACK_COUNT>1</TRACK_COUNT>
    <TRACK>
      <CHANNEL_INDEX>1</CHANNEL_INDEX>
      <INTERLEAVE_INDEX>1</INTERLEAVE_INDEX>
      <NAME>Mono</NAME>
      <FUNCTION>LEFT</FUNCTION>
    </TRACK>
  </TRACK_LIST>
  <SPEED>
    <AUDIO_BIT_DEPTH>24</AUDIO_BIT_DEPTH>
    <FILE_SAMPLE_RATE>48000</FILE_SAMPLE_RATE>
  </SPEED>
  <USER>Additional free-text user data</USER>
</BWFXML>
```

**Critical rules:**

- Root element is `<BWFXML>` (not `<iXML>` — this is a common mistake).
- All fields are optional. Writers should only include fields that have values.
- Readers must not assume any field is present.
- The iXML chunk ID in the RIFF file is the 4 ASCII bytes: `i`, `X`, `M`, `L`.
- Encoding is UTF-8. Special characters (`<`, `>`, `&`) must be XML-escaped in field values.
- If the iXML chunk byte count is odd, pad with one null byte to maintain even alignment.
- Writers should preserve any existing iXML fields they don't recognize (round-trip safety). Read the existing XML, modify only the fields being changed, and write the whole tree back.

**Fields we write:**
PROJECT, SCENE, TAKE, TAPE, NOTE, CIRCLED, USER, and any UCS-specific custom fields (which go in the USER block or as custom child elements, depending on convention). TRACK_LIST and SPEED are preserved from the original file if present but not generated by us.

### Not Bundled

This is reference knowledge built into the code, not a data file.

---

## 6. BEXT Specification Reference

### What It Is

The binary layout of the Broadcast Audio Extension (BEXT) chunk, defined by the European Broadcasting Union standard EBU Tech 3285.

### Source

EBU Tech 3285: `https://tech.ebu.ch/docs/tech/tech3285.pdf`

### Format

Reference documentation, encoded directly into the RIFF writer source code.

### Binary Layout

The BEXT chunk has the RIFF chunk ID `bext` (4 ASCII bytes: `b`, `e`, `x`, `t`). After the standard 8-byte RIFF chunk header (4-byte ID + 4-byte size), the data section has the following fixed layout:

| Field                | Offset (bytes) | Size (bytes) | Type               | Notes                                    |
| -------------------- | -------------- | ------------ | ------------------ | ---------------------------------------- |
| Description          | 0              | 256          | ASCII, null-padded | Free-text description                    |
| Originator           | 256            | 32           | ASCII, null-padded | Creator/organization name                |
| OriginatorReference  | 288            | 32           | ASCII, null-padded | Unique reference identifier              |
| OriginationDate      | 320            | 10           | ASCII              | `YYYY-MM-DD`                             |
| OriginationTime      | 330            | 8            | ASCII              | `HH:MM:SS`                               |
| TimeReference        | 338            | 8            | uint64 LE          | Sample count since midnight              |
| Version              | 346            | 2            | uint16 LE          | BWF version (0, 1, or 2)                 |
| UMID                 | 348            | 64           | bytes              | Unique Material Identifier               |
| LoudnessValue        | 412            | 2            | int16 LE           | Integrated loudness × 100                |
| LoudnessRange        | 414            | 2            | int16 LE           | Loudness range × 100                     |
| MaxTruePeakLevel     | 416            | 2            | int16 LE           | Max true peak × 100                      |
| MaxMomentaryLoudness | 418            | 2            | int16 LE           | Max momentary × 100                      |
| MaxShortTermLoudness | 420            | 2            | int16 LE           | Max short-term × 100                     |
| Reserved             | 422            | 180          | bytes              | Must be null bytes                       |
| CodingHistory        | 602            | variable     | ASCII              | Encoding chain history (to end of chunk) |

**Total fixed portion:** 602 bytes. CodingHistory extends from byte 602 to the end of the chunk data.

**Critical rules for the writer:**

- ASCII string fields must be null-padded to their full length if the content is shorter.
- If a field has no value, fill with null bytes (not spaces).
- TimeReference is a 64-bit unsigned integer in little-endian byte order.
- Version should be set to `2` if loudness fields are populated, `1` if only base fields are used, `0` for minimal BEXT.
- When modifying BEXT, preserve all existing field values that are not being changed. Read the existing BEXT chunk, unpack it, modify specific fields, repack, and write.
- The BEXT chunk, like all RIFF chunks, must be even-byte aligned. If the total data length (602 + CodingHistory length) is odd, pad with one null byte.

### Not Bundled

This is reference knowledge built into the code, not a data file.

---

## 7. RIFF/WAV Format Reference

### What It Is

The RIFF (Resource Interchange File Format) container format that WAV files use. Understanding this is necessary for the custom chunk writer.

### Source

Microsoft RIFF specification (original) and various well-documented references. The format is simple and thoroughly documented online.

### Structure Summary

A WAV file is a RIFF container:

```
Bytes 0-3:    "RIFF"              (4 bytes, ASCII)
Bytes 4-7:    File size - 8       (4 bytes, uint32 LE)
Bytes 8-11:   "WAVE"              (4 bytes, ASCII)
Bytes 12+:    Sequence of chunks
```

Each chunk:

```
Bytes 0-3:    Chunk ID            (4 bytes, ASCII, e.g., "fmt ", "data", "bext", "iXML")
Bytes 4-7:    Chunk data size     (4 bytes, uint32 LE — size of data only, not including ID and size fields)
Bytes 8+:     Chunk data          (variable length)
[Pad byte]:   If data size is odd, one null pad byte follows (not counted in the size field)
```

**Standard chunks in a WAV file:**

- `fmt ` — Audio format (sample rate, bit depth, channels, encoding). Always present.
- `data` — The raw audio samples. Always present. Often the largest chunk (can be gigabytes).
- `bext` — Broadcast Audio Extension metadata. Optional.
- `iXML` — iXML metadata. Optional.
- `LIST` — Container for INFO sub-chunks (INAM, IART, ICMT, etc.). Optional.
- `cue ` — Cue point markers. Optional.
- `smpl` — Sampler data (loops, MIDI note). Optional.
- `axml` — ADM (Audio Definition Model) metadata. Optional.

**Rules for the writer:**

- Chunks can appear in any order (except `RIFF` header must be first).
- The writer must iterate through all chunks, preserving those it doesn't modify and replacing those it does.
- The `data` chunk should never be read into memory entirely for large files. The writer should copy it byte-by-byte (or in large buffer chunks) from the source file to the temp output file.
- After writing all chunks, update the RIFF header's file size field (bytes 4-7) to reflect the new total size.
- Always write to a temporary file first, then replace the original only on success (atomic write pattern).

### Not Bundled

This is reference knowledge built into the code, not a data file.

---

## 8. Summary: Files to Acquire Before Development Starts

Before writing any application code, the following files should be downloaded and inspected:

| #   | File                              | Action Required                                                                                                                                                                                  | Blocking?                                                                             |
| --- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------- |
| 1   | UCS 8.2.1 spreadsheet             | Download from universalcategorysystem.com. Open in Excel or Python and document the exact sheet names, column headers, and data layout.                                                          | Yes — the UCS parser, the label generator, and the dropdown menus all depend on this. |
| 2   | Sample WAV files with iXML        | Obtain 5-10 WAV files that contain iXML metadata (from the audio designer or from freely available BWF sample files). These are needed to test the metadata reader and RIFF writer.              | Yes — the RIFF writer cannot be validated without real test files.                    |
| 3   | Sample WAV files without metadata | Obtain 5-10 WAV files with no metadata and uninformative names. These test the CLAP classification and metadata generation pipeline.                                                             | Helpful but not blocking — any WAV files will work.                                   |
| 4   | MS-CLAP 2023 model                | No pre-download needed. The `msclap` package downloads automatically from Zenodo on first use. But do trigger this download on the dev machine before Day 1 to avoid waiting during development. | Not blocking, but pre-download saves time.                                            |
| 5   | clapcap model                     | No pre-download needed. The `msclap` package downloads it on first use. Same advice: trigger the download early.                                                                                 | Not blocking.                                                                         |
