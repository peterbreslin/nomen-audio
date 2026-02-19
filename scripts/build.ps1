#!/usr/bin/env pwsh
# End-to-end build script — tests, sidecar, Tauri installer

$ErrorActionPreference = "Stop"

Write-Host "=== Nomen Audio Full Build ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Run tests
Write-Host "[1/5] Running pytest..." -ForegroundColor Yellow
uv run python -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed! Aborting build." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ All tests passed" -ForegroundColor Green
Write-Host ""

# Step 2: Lint check
Write-Host "[2/5] Running ruff check..." -ForegroundColor Yellow
uv run python -m ruff check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Linting failed! Aborting build." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Linting passed" -ForegroundColor Green
Write-Host ""

# Step 3: Build sidecar
Write-Host "[3/5] Building PyInstaller sidecar..." -ForegroundColor Yellow
& "$PSScriptRoot\build-sidecar.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Sidecar build failed! Aborting." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Sidecar build complete" -ForegroundColor Green
Write-Host ""

# Step 4: Build Tauri
Write-Host "[4/5] Building Tauri installer..." -ForegroundColor Yellow
Set-Location frontend
npm run tauri build
if ($LASTEXITCODE -ne 0) {
    Set-Location ..
    Write-Host "Tauri build failed!" -ForegroundColor Red
    exit 1
}
Set-Location ..
Write-Host "  ✓ Tauri build complete" -ForegroundColor Green
Write-Host ""

# Step 5: Report installer location
Write-Host "[5/5] Build complete!" -ForegroundColor Green
Write-Host ""

$bundleRoot = "frontend\src-tauri\target\release\bundle"
$found = $false

# Search MSI (WiX) and NSIS directories
foreach ($subdir in @("msi", "nsis")) {
    $dir = Join-Path $bundleRoot $subdir
    if (Test-Path $dir) {
        $installers = Get-ChildItem -Path $dir -Include "*.msi", "*.exe" -Recurse | Select-Object -First 1
        if ($installers) {
            $fullPath = Resolve-Path $installers.FullName
            $size = [math]::Round($installers.Length / 1MB, 1)
            Write-Host "Installer ($subdir): $fullPath" -ForegroundColor Cyan
            Write-Host "Size: ${size}MB" -ForegroundColor Cyan
            $found = $true
        }
    }
}

if (-not $found) {
    Write-Host "Warning: No installer found in $bundleRoot" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Build Complete ===" -ForegroundColor Green
