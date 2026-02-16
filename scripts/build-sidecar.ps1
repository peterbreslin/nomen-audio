#!/usr/bin/env pwsh
# Build PyInstaller sidecar and copy to Tauri resources

$ErrorActionPreference = "Stop"

Write-Host "Building PyInstaller sidecar..." -ForegroundColor Cyan

# Clean previous build
if (Test-Path "dist/nomen-sidecar") {
    Remove-Item -Recurse -Force "dist/nomen-sidecar"
    Write-Host "Cleaned previous build" -ForegroundColor Yellow
}

# Run PyInstaller
uv run pyinstaller nomen-sidecar.spec --clean

if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller build failed" -ForegroundColor Red
    exit 1
}

Write-Host "PyInstaller build successful" -ForegroundColor Green

# Copy to Tauri resources
$targetDir = "frontend/src-tauri/binaries/sidecar"
if (Test-Path $targetDir) {
    Remove-Item -Recurse -Force "$targetDir/*" -Exclude ".gitkeep"
}

Copy-Item -Recurse -Force "dist/nomen-sidecar/*" $targetDir

Write-Host "Copied sidecar to $targetDir" -ForegroundColor Green
Write-Host "Sidecar ready for Tauri bundling" -ForegroundColor Cyan
