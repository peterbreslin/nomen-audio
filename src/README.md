# Python Backend (`src/`)

FastAPI sidecar — all file I/O, metadata parsing, UCS lookups, and ML inference live here. The frontend never touches the filesystem directly.

## Entry Point

```pwsh
$env:PYTHONPATH="src"; uv run -m app
```

`src/app/__main__.py` binds to a random localhost port, prints `PORT=<n>` to stdout (read by Tauri), then starts uvicorn. Heavy imports (torch, msclap) happen _after_ the port is printed so Tauri can connect immediately.

## Module Map

| Package                    | Responsibility                                                              |
| -------------------------- | --------------------------------------------------------------------------- |
| `app/main.py`              | FastAPI app creation, router registration, lifespan                         |
| `app/models.py`            | Pydantic request/response schemas (FileRecord, etc.)                        |
| `app/errors.py`            | Shared exception types                                                      |
| `app/paths.py`             | Runtime path resolution — dev (`./data/`) vs prod (`%APPDATA%/NomenAudio/`) |
| `app/routers/files.py`     | Import, list, rename, save endpoints                                        |
| `app/routers/analysis.py`  | SSE batch-analysis streaming endpoint                                       |
| `app/routers/ucs.py`       | UCS categories / subcategories / CatID lookup                               |
| `app/routers/settings.py`  | User settings CRUD                                                          |
| `app/routers/models.py`    | Model download status and trigger                                           |
| `app/db/schema.py`         | SQLite DDL, migrations                                                      |
| `app/db/repository.py`     | All SQL queries — no SQL outside this module                                |
| `app/db/mappers.py`        | Row ↔ Pydantic model conversions                                            |
| `app/metadata/reader.py`   | RIFF/BEXT/iXML chunk parsing (read-only)                                    |
| `app/metadata/writer.py`   | Atomic RIFF writer — preserves unmodified chunks byte-for-byte              |
| `app/ucs/engine.py`        | UCS spreadsheet loader, category/subcategory/CatID resolution               |
| `app/ucs/filename.py`      | UCS filename parsing and generation                                         |
| `app/ml/classifier.py`     | MS-CLAP zero-shot classification → top-N UCS suggestions                    |
| `app/ml/captioner.py`      | ClapCap natural-language description generation                             |
| `app/ml/suggestions.py`    | Aggregates classifier + captioner output into FileRecord suggestions        |
| `app/ml/model_manager.py`  | Model download, caching, and load-on-demand                                 |
| `app/ml/label_builder.py`  | Builds CLAP label strings from UCS category data                            |
| `app/ml/clap_compat.py`    | Compatibility shim for msclap API differences                               |
| `app/services/settings.py` | Settings read/write business logic                                          |
| `app/services/flagging.py` | File-level flagging / review-state tracking                                 |

## Key Architectural Rules

- **Never** load the audio `data` chunk into memory — stream-copy in 1 MB buffers.
- **Always** use atomic writes (`temp file → os.replace()`). Original is untouched on error.
- **Always** preserve WAV chunks the writer doesn't modify, byte-for-byte.
- CatID is **looked up** from the UCS spreadsheet, never derived algorithmically.
- All ML suggestions are proposals — nothing written until the user explicitly saves.

## Data Directory

| Environment | Path                    |
| ----------- | ----------------------- |
| Development | `./data/` (repo root)   |
| Production  | `%APPDATA%\NomenAudio\` |

`app/paths.py` resolves the correct path at runtime.

## Tests

```pwsh
uv run pytest -q
```

Run from the repo root. The `PYTHONPATH` is set automatically via `pyproject.toml`.
