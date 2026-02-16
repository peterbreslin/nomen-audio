# Build Scripts

PowerShell scripts for building and testing the Nomen Audio production bundle.

## Prerequisites

All scripts require:

- [`uv`](https://docs.astral.sh/uv/) — Python environment and package runner
- [Node.js](https://nodejs.org/) ≥ 20 — frontend toolchain
- [Rust stable](https://rustup.rs/) + `cargo` — Tauri Rust shell
- [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — C++ workload required by Tauri on Windows

---

## `build.ps1` — Full production build

Runs all five steps in sequence and aborts on the first failure:

| Step | Action |
|---|---|
| 1/5 | `uv run pytest -q` — full Python test suite |
| 2/5 | `uv run ruff check .` — lint check |
| 3/5 | `build-sidecar.ps1` — PyInstaller sidecar |
| 4/5 | `npm run tauri build` — Tauri installer (MSI + NSIS) |
| 5/5 | Print installer paths and sizes |

```pwsh
pwsh -NoProfile -File scripts/build.ps1
```

Installers are written to:
- `frontend/src-tauri/target/release/bundle/msi/`
- `frontend/src-tauri/target/release/bundle/nsis/`

---

## `build-sidecar.ps1` — PyInstaller sidecar only

Packages the Python backend into a self-contained executable via PyInstaller using `nomen-sidecar.spec`, then copies the output to `frontend/src-tauri/binaries/sidecar/` for Tauri bundling.

```pwsh
pwsh -NoProfile -File scripts/build-sidecar.ps1
```

Run this in isolation when iterating on the Python backend without a full Tauri rebuild.

---

## `test-sidecar.ps1` — Sidecar smoke test

Starts the compiled sidecar binary, reads its `PORT=<n>` from stdout, and exercises four critical endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `GET /ucs/categories` | UCS data loaded |
| `GET /settings` | Settings service alive |
| `GET /models/status` | ML model state readable |

```pwsh
pwsh -NoProfile -File scripts/test-sidecar.ps1
```

Run this after `build-sidecar.ps1` to verify the compiled binary works before a full Tauri build.
