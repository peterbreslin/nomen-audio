# Installing Nomen Audio

Nomen Audio is a desktop application for sound designers that helps rename and re-tag legacy WAV files to the [Universal Category System (UCS)](https://universalcategorysystem.com/) standard. It analyzes audio content using AI, suggests UCS-compliant names and metadata, and writes the changes directly into the WAV files.

---

## System Requirements

| | Requirement |
|--|-------------|
| **OS** | Windows 10 or Windows 11 (64-bit) |
| **RAM** | 8 GB minimum, 16 GB recommended (AI analysis loads ~1.5 GB model weights) |
| **Disk** | 4 GB free for application + AI model weights |
| **CPU** | Any modern x64 processor (no GPU required — inference runs on CPU) |
| **WebView2** | Included with Windows 11; Windows 10 users may need the [WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) |

> **No Python, Node.js, or Rust installation required.** The Python backend is bundled inside the installer.

---

## Download

Go to the [Releases](https://github.com/peterbreslin/nomen-audio/releases) page on GitHub. Two installer formats are provided — choose one:

| Installer | Format | Best for |
|-----------|--------|----------|
| `Nomen Audio_0.1.0_x64-setup.exe` | NSIS | Most users — guided wizard with uninstaller |
| `Nomen Audio_0.1.0_x64_en-US.msi` | MSI (WiX) | IT/enterprise deployment, Group Policy |

**Recommended: download the `.exe` setup for a standard installation.**

---

## Installation

1. **Run the installer.** Double-click the downloaded file.

2. **SmartScreen warning:** Windows may show a "Windows protected your PC" prompt because the app is not yet code-signed. Click **More info → Run anyway**. This is expected for unsigned software and is not a virus alert.

3. **Accept the UAC prompt** when prompted (required to install to Program Files).

4. **Follow the installer wizard.** Default installation path: `C:\Program Files\Nomen Audio\`.

5. **Launch the app** from the Start menu or desktop shortcut.

---

## First Launch

The first time the app starts, it will:

1. **Open the main window** and connect to the Python backend (this takes a few seconds).
2. **Begin loading AI models in the background.** The status bar at the bottom shows the loading state. The app is fully usable as a manual metadata editor while models load.

### AI Model Download

Model weights are **not bundled in the installer** and are downloaded automatically on first use. There are two separate downloads triggered at different times:

| Model | Size | Trigger |
|-------|------|---------|
| MS-CLAP 2023 (classifier) | ~660 MB | Downloaded in the background on every first launch |
| ClapCap + GPT-2 (description generator) | ~2.1 GB | Downloaded the first time you click **Generate** with AI descriptions enabled |

**Total download on first full use: ~2.8 GB.** Subsequent launches use the cached weights with no download required.

Weights are stored in the standard Hugging Face cache: `%USERPROFILE%\.cache\huggingface\hub\` — not in `%APPDATA%\NomenAudio\`.

> If you are behind a corporate proxy or firewall, ensure `huggingface.co` is reachable. Models are hosted at `https://huggingface.co/microsoft/msclap`.

---

## Where Data is Stored

Nomen Audio stores all user data in `%APPDATA%\NomenAudio\` (e.g. `C:\Users\YourName\AppData\Roaming\NomenAudio\`):

| File | Purpose |
|------|---------|
| `nomen.db` | SQLite database of imported files and metadata |
| `settings.json` | App settings (creator ID, library name, AI preferences) |
| `cache\text_embeddings.npz` | Pre-computed AI label embeddings (generated on first analysis) |

Your WAV files are never moved or modified without your explicit action. The app imports a folder by reading the files in place — it doesn't copy them.

---

## Core Workflow

1. **Import** — Click **Browse** or drag a folder of WAV files onto the app. Files appear in the spreadsheet view with any existing metadata pre-filled.

2. **Analyze** — Select one or more files and click the **Generate** button (⚡). The AI analyzes the audio and suggests a UCS category, subcategory, description, keywords, and filename.

3. **Review** — Suggestions appear highlighted. Accept them as-is, tweak them, or ignore them. Nothing is written to disk until you explicitly save.

4. **Save** — Click **Save** (or **Save All**) to write metadata into the WAV files and optionally rename them. The original audio data is never touched — only the metadata chunks are rewritten.

---

## Uninstalling

Uninstall via **Settings → Apps** (Windows 11) or **Control Panel → Programs and Features** (Windows 10).

Your data in `%APPDATA%\NomenAudio\` (database, settings, model cache) is **preserved** after uninstall. To remove it completely, delete that folder manually.

---

## Troubleshooting

### "Windows protected your PC" warning on install

The app is not yet code-signed. This is a SmartScreen warning, not a virus alert. Click **More info → Run anyway**. The MSI installer will then proceed normally.

### App opens but shows "Disconnected" banner

The Python backend failed to start. Try:
- Restarting the app.
- Checking your antivirus — it may have quarantined `nomen-sidecar.exe` inside the install directory. Add an exclusion for `C:\Program Files\Nomen Audio\`.

### Analysis fails or models won't download

- Check your internet connection.
- Ensure `huggingface.co` is not blocked by firewall or proxy.
- Check available disk space — full model download requires ~2.8 GB free.
- Check the Hugging Face cache at `%USERPROFILE%\.cache\huggingface\hub\` for partial downloads; delete the `models--microsoft--msclap` folder to force a clean re-download.

### App is slow during first analysis

Two things happen on first use that only occur once:

1. **Text embedding computation** — the app pre-computes embeddings for all 753 UCS subcategory labels (~30–120 seconds depending on CPU). Cached to `%APPDATA%\NomenAudio\cache\`.
2. **ClapCap model download** — ~2.1 GB downloaded from Hugging Face the first time AI descriptions are generated. Subsequent launches skip both steps.

---

## Building from Source

If you prefer to build from source rather than using the installer:

**Prerequisites:** Git, Rust (stable), Node.js 20+, Python 3.12+, [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

```powershell
git clone https://github.com/peterbreslin/nomen-audio.git
cd nomen-audio
uv sync                   # Install Python dependencies
cd frontend
npm install               # Install frontend dependencies
npm run tauri dev         # Start dev server (hot-reload)
```

To produce a release installer:

```powershell
# From the repo root
pwsh -NoProfile -File scripts/build.ps1
```

The MSI installer will be output to `frontend/src-tauri/target/release/bundle/msi/`.
