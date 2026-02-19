# -*- mode: python ; coding: utf-8 -*-

"""PyInstaller spec for NomenAudio sidecar — onedir build."""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# Project structure
project_root = Path('.').resolve()
src_dir = project_root / 'src'
data_dir = project_root / 'data'

block_cipher = None

a = Analysis(
    [str(src_dir / 'app' / '__main__.py')],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[
        # UCS spreadsheets (read-only bundled data)
        (str(data_dir / 'UCS' / 'UCS v8.2.1 Full List.xlsx'), 'UCS'),
        (str(data_dir / 'UCS' / 'UCS v8.2.1 Top Level Categories.xlsx'), 'UCS'),
        # Collect package data for ML libraries
        *collect_data_files('msclap', include_py_files=False),
        *collect_data_files('transformers', include_py_files=False),
        # Copy metadata for packages that need it at runtime
        *copy_metadata('torch'),
        *copy_metadata('transformers'),
        *copy_metadata('msclap'),
        *copy_metadata('huggingface_hub'),
    ],
    hiddenimports=[
        # Uvicorn dynamic imports
        'uvicorn.logging',
        'uvicorn.lifespan.on',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        # FastAPI/Starlette
        'aiosqlite',
        'multipart',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unused torch modules
        'torch.distributed',
        'torch.testing',
        # Exclude GUI frameworks
        'matplotlib',
        'tkinter',
        'tensorboard',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='nomen-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='nomen-sidecar',
)
