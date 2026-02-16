#!/usr/bin/env pwsh
# Test compiled sidecar endpoints systematically

$ErrorActionPreference = "Stop"

Write-Host "Starting compiled sidecar..." -ForegroundColor Cyan

# Start sidecar in background
$sidecarPath = "frontend/src-tauri/binaries/sidecar/nomen-sidecar.exe"
$process = Start-Process -FilePath $sidecarPath -PassThru -NoNewWindow -RedirectStandardOutput "sidecar-stdout.txt" -RedirectStandardError "sidecar-stderr.txt"

# Wait for PORT output
Start-Sleep -Seconds 2
$port = (Get-Content "sidecar-stdout.txt" | Select-String "PORT=(\d+)").Matches.Groups[1].Value

if (-not $port) {
    Write-Host "Failed to get PORT from sidecar" -ForegroundColor Red
    Stop-Process -Id $process.Id -Force
    exit 1
}

Write-Host "Sidecar running on port $port" -ForegroundColor Green
$baseUrl = "http://127.0.0.1:$port"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Path,
        [string]$Method = "GET",
        [hashtable]$Body = @{}
    )

    Write-Host "Testing $Name ($Path)..." -ForegroundColor Yellow

    try {
        if ($Method -eq "GET") {
            $response = Invoke-WebRequest -Uri "$baseUrl$Path" -UseBasicParsing -TimeoutSec 10
        } else {
            $jsonBody = $Body | ConvertTo-Json
            $response = Invoke-WebRequest -Uri "$baseUrl$Path" -Method $Method -Body $jsonBody -ContentType "application/json" -UseBasicParsing -TimeoutSec 10
        }

        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ $Name succeeded" -ForegroundColor Green
            return $true
        } else {
            Write-Host "  ✗ $Name failed (HTTP $($response.StatusCode))" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "  ✗ $Name error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "    $($_.Exception.Response.StatusCode)" -ForegroundColor DarkRed
        return $false
    }
}

Write-Host ""
Write-Host "=== Endpoint Tests ===" -ForegroundColor Cyan

# Test sequence from plan
$results = @()
$results += Test-Endpoint "Health check" "/health"
$results += Test-Endpoint "UCS categories" "/ucs/categories"
$results += Test-Endpoint "Settings" "/settings"
$results += Test-Endpoint "Models status" "/models/status"

# Cleanup
Write-Host ""
Write-Host "Stopping sidecar..." -ForegroundColor Cyan
Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
Remove-Item "sidecar-stdout.txt" -ErrorAction SilentlyContinue
Remove-Item "sidecar-stderr.txt" -ErrorAction SilentlyContinue

# Summary
Write-Host ""
$passed = ($results | Where-Object { $_ -eq $true }).Count
$total = $results.Count
Write-Host "Results: $passed/$total tests passed" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

if ($passed -eq $total) {
    Write-Host "All critical endpoints working!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "Some endpoints failed - check spec for missing imports" -ForegroundColor Yellow
    exit 1
}
