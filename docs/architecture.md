# Architecture

High-level architecture of Nomen Audio.

---

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Tauri v2 Shell (Rust)                │
│                                                         │
│  - Spawns Python sidecar on launch                      │
│  - Reads PORT from stdout, stores in SidecarState       │
│  - Kills process tree on window close                   │
│  - Provides: native dialogs, HTTP plugin, logging       │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │              Svelte Frontend (WebView)            │  │
│  │                                                   │  │
│  │  Stores ←→ API Client ──HTTP/JSON──→ localhost:N  │  │
│  │                                                   │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                            │
                    HTTP on 127.0.0.1
                            │
┌─────────────────────────────────────────────────────────┐
│                Python FastAPI Sidecar                   │
│                                                         │
│  Routers ──→ Services / ML ──→ Metadata Reader/Writer   │
│                    │                      │             │
│                 SQLite               WAV Files on Disk  │
└─────────────────────────────────────────────────────────┘
```

The frontend never touches files. All file I/O, metadata parsing, ML inference, and database access happen in Python. Communication is plain HTTP/JSON over localhost using the Tauri HTTP plugin (browser `fetch` cannot reach localhost from a webview).

---

## Process Lifecycle

```
Tauri launch
  │
  ├─ spawn_sidecar()
  │    ├─ Dev:  uv run -m app (PYTHONPATH=src)
  │    └─ Prod: resource_dir/sidecar/nomen-sidecar.exe
  │
  ├─ Background thread reads stdout
  │    └─ Captures "PORT=<n>" line via mpsc channel
  │
  ├─ Frontend calls invoke('get_sidecar_port')
  │    └─ Caches port, all API calls use it
  │
  ├─ Python lifespan startup:
  │    1. Load UCS spreadsheets into memory
  │    2. Load settings from JSON
  │    3. Connect SQLite (run migrations)
  │    4. Start background ML model loading
  │
  └─ On window close:
       └─ taskkill /F /T /PID (kills entire process tree)
```

The stdout pipe is drained continuously — this is critical on Windows, where PyTorch blocks if the pipe read end closes.

---

## Frontend Architecture

### App Shell

```
+layout.svelte
  └─ Blocks render until backend reachable + stores loaded
     └─ <TooltipProvider> + <Toaster>

+page.svelte (3-row grid: auto / 1fr / 24px)
  ├─ <Toolbar>             ─── import, save-all, generate-all, settings, expand-all
  ├─ <main>                ─── horizontal split
  │   ├─ <Sidebar>         ─── file tree browser, folder navigation, search
  │   └─ <div>             ─── vertical split
  │       ├─ <Sheet>       ─── spreadsheet metadata editor (bulk of the UI)
  │       └─ <WaveformPanel> ─ waveform display, old→new filename preview
  └─ <StatusBar>           ─── file count, selected count, ML analysis count
```

Keyboard shortcuts are handled at the page level: `Ctrl+S` (save), `Space` (play/pause), `Ctrl+H` (find/replace), `Escape` (close overlays). Window-close is intercepted to warn about unsaved changes.

### Stores (Svelte 5 Runes)

```
┌──────────────┐   ┌──────────┐   ┌──────────┐
│  FileStore   │   │ UIStore  │   │ UCSStore │
│              │   │          │   │          │
│ files (Map)  │   │ sidebar  │   │ category │
│ selection    │   │ columns  │   │ tree     │
│ activeFile   │   │ editing  │   │          │
│ ML badges    │   │ health   │   └──────────┘
│ dirty state  │   └──────────┘
└──────────────┘
       │            ┌──────────────┐   ┌───────────────┐
       │            │ ModelsStore  │   │ SettingsStore │
       │            │              │   │               │
       │            │ clap status  │   │ settings JSON │
       │            │ poll loop    │   │               │
       │            └──────────────┘   └───────────────┘
       │
       ▼
  API Client (client.ts)
       │
       ▼
  sidecarFetch() ── Tauri HTTP plugin ──→ 127.0.0.1:PORT
```

`FileStore` is the single source of truth for file state. Updates are **optimistic** — the in-memory record is patched immediately, then synced to the backend. AI-generated and manually-edited fields are tracked separately for badge display (cyan dot = AI, gold dot = manual).

### Component Organization

```
lib/
  api/client.ts          ── typed HTTP wrappers for all endpoints
  stores/                ── 5 reactive stores (files, ui, models, ucs, settings)
  types/index.ts         ── shared TypeScript interfaces (mirrors Pydantic models)
  components/
    Toolbar.svelte
    StatusBar.svelte
    SettingsModal.svelte
    FindReplaceModal.svelte
    ConfirmDialog.svelte
    sidebar/             ── Sidebar.svelte, FileTree.svelte
    sheet/               ── Sheet, SheetRow, CellEditOverlay, CellCombobox,
                            AnalysisDetailRow, FileDetailsModal, columns.ts
    main/                ── WaveformPanel.svelte
    ui/                  ── shadcn-svelte primitives (13 components)
  utils/                 ── debounce, error formatting, UCS cascade logic
```

---

## Backend Architecture

### Module Boundaries

```
src/app/
  main.py                ── FastAPI app, lifespan, CORS, router registration
  __main__.py            ── entrypoint: bind random port, print PORT=, start uvicorn
  paths.py               ── all path resolution (dev vs frozen via sys.frozen)
  models.py              ── Pydantic schemas (FileRecord, MetadataUpdate, etc.)
  errors.py              ── AppError exception + error codes

  routers/               ── HTTP layer (thin — delegates to services)
    files.py             ── /files/* — import, CRUD, save, revert, batch, audio stream
    analysis.py          ── /files/{id}/analyze, /files/analyze-batch
    models.py            ── /models/status
    ucs.py               ── /ucs/categories, /ucs/lookup, /ucs/parse-filename
    settings.py          ── /settings (GET/PUT), /settings/reset-db

  metadata/              ── WAV file I/O (the core of the app)
    reader.py            ── extract BEXT, iXML, LIST-INFO, technical info
    writer.py            ── atomic rewrite with stream-copy, verify after write

  db/                    ── persistence
    schema.py            ── DDL + migrations
    repository.py        ── async SQLite queries (aiosqlite)
    mappers.py           ── row → Pydantic conversion

  ucs/                   ── UCS standard logic
    engine.py            ── spreadsheet loader, category/synonym lookups
    filename.py          ── UCS filename parsing, fuzzy matching, generation

  ml/                    ── machine learning
    model_manager.py     ── background loading, readiness tracking
    classifier.py        ── CLAP zero-shot classification
    captioner.py         ── ClapCap audio captioning
    suggestions.py       ── map ML output → metadata suggestions
    label_builder.py     ── CLAP label set construction
    clap_compat.py       ── model compatibility shim

  services/              ── cross-cutting concerns
    settings.py          ── JSON-persisted app settings
    flagging.py          ── file status / dirty-field logic
```

### Dependency Flow

```
routers  ──→  services / ml  ──→  db
   │              │                │
   │              ▼                │
   │          metadata/            │
   │         reader + writer       │
   │              │                │
   └──────────────┴────────────────┘
                  │
                  ▼
           ucs/engine (read-only, in-memory)
```

Lower layers never import higher layers. `models.py` and `errors.py` are shared across all layers. The `ucs/` module is stateless after initial load — it's a pure lookup table.

### Database

Two tables in SQLite (via aiosqlite):

```
files
  ├─ id TEXT (PK, UUID)
  ├─ path TEXT (UNIQUE, indexed)
  ├─ filename, directory, status, file_hash
  ├─ 22 nullable metadata TEXT columns (category through source_id)
  ├─ suggested_filename TEXT
  ├─ technical, bext, info, custom_fields, analysis  (JSON blobs)
  ├─ changed_fields (JSON array)
  └─ imported_at, modified_at

analysis_cache
  ├─ file_hash TEXT (PK)
  ├─ classification TEXT (JSON — raw top-50 CLAP results)
  ├─ caption TEXT
  ├─ model_version TEXT
  └─ created_at TEXT
```

The `files` table is the working set — every imported file has a row. `analysis_cache` is keyed by content hash so results survive re-imports and renames.

---

## Data Flow

### Import → Edit → Save

```
                          ┌─────────────────┐
  User picks directory    │   WAV Files     │
          │               │   on Disk       │
          ▼               └────────┬────────┘
  POST /files/import               │
          │                   read_metadata()
          │                        │
          ▼                        ▼
  ┌──────────────┐         ┌──────────────┐
  │   SQLite     │◄────────│  FileRecord  │
  │   (files)    │         │  (Pydantic)  │
  └──────┬───────┘         └──────────────┘
         │
      GET /files ──→ Frontend stores ──→ Sheet UI
                                          │
                                User edits cells
                                          │
                          PUT /files/{id}/metadata
                                          │
                            SQLite updated (status: modified)
                                          │
                              POST /files/{id}/save
                                          │
                              ┌───────────┴───────────┐
                              │                       │
                        write_metadata()        verify_write()
                              │                       │
                     atomic temp→replace       re-read + check
                              │                       │
                     optional rename         update DB (status: saved)
```

### Analysis → Suggestions → User Decision

```
  POST /files/{id}/analyze
          │
          ├─ Cache hit? ──→ Re-rank with filename boost ──→ return
          │
          └─ Cache miss:
               │
          CLAP classifier (thread pool)
               │
          ┌────┴────┐
          │ Tier 1  │  category, subcategory, cat_id, keywords, filename
          │         │  (from top CLAP match + UCS synonym index)
          └────┬────┘
               │
         ┌─────┴────┐
         │  Tier 2  │  + description, fx_name
         │(optional)│  (from ClapCap caption)
         └─────┬────┘
               │
          Cache raw results in analysis_cache
               │
          Return suggestions to frontend
               │
          ┌────┴────────────────────────────┐
          │  Suggestions are PROPOSALS      │
          │  Nothing written until user     │
          │  explicitly accepts + saves     │
          └─────────────────────────────────┘
```

Suggestions are **not persisted**. They're recomputed from stored analysis data on every read, so they always reflect current settings (e.g., changed creator ID updates all suggested filenames).

---

## Build & Packaging

```
Source
  ├─ frontend/           Svelte + Tailwind + shadcn
  │     └─ build/        SvelteKit static output
  ├─ src/                Python 3.12+ FastAPI
  └─ frontend/src-tauri/ Rust shell

Build pipeline (scripts/build.ps1):
  1. pytest + ruff          ── backend tests + lint
  2. build-sidecar.ps1      ── PyInstaller → binaries/sidecar/nomen-sidecar.exe
  3. tauri build            ── bundles frontend + Rust + sidecar → installer

Production artifact:
  └─ Nomen Audio installer (.msi / .exe)
       ├─ Tauri shell (thin Rust binary)
       ├─ WebView2 runtime
       ├─ Sidecar (PyInstaller onedir bundle, ~900MB)
       │    ├─ nomen-sidecar.exe
       │    ├─ _internal/ (Python + all deps + UCS data)
       │    └─ ML model weights (loaded on demand)
       └─ Frontend assets (static HTML/JS/CSS)
```

Window: 1200x800 default, 900x600 minimum. Identifier: `com.nomenaudio.app`.

---

## Key Design Constraints

- **Audio data never loaded into memory.** Stream-copied in 1 MB buffers during writes.
- **All writes are atomic.** Temp file in same directory → `os.replace()`. Original untouched on error.
- **CatIDs are always looked up**, never derived algorithmically.
- **ML suggestions are proposals.** Nothing written to disk without explicit user action.
- **The app works without ML models.** Manual metadata editing is the baseline; ML is an accelerator.
- **Frontend is stateless on reload.** All truth lives in SQLite + files on disk. Stores are repopulated from the backend on each session.
