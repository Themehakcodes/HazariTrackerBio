#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build HazariTracker Bio EXE (one-folder bundle) with PyInstaller.

.DESCRIPTION
    1. Reads version from version.py
    2. Optionally bumps the patch number (-BumpPatch)
    3. Builds the EXE with PyInstaller (32-bit Python)
    4. Zips dist\HazariTrackerBio-vX.Y.Z\  ->  dist\HazariTrackerBio-vX.Y.Z-win32.zip

    Run publish.ps1 separately to create the Inno Setup installer and
    push a GitHub Release.

.USAGE
    .\build.ps1              # Build current version
    .\build.ps1 -BumpPatch   # Increment patch, then build
#>

param(
    [switch]$BumpPatch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Config ────────────────────────────────────────────────────────────────────
$PYTHON32  = "C:\Python311-32\python.exe"
$REPO_DIR  = $PSScriptRoot
$DIST_DIR  = Join-Path $REPO_DIR "dist"
$BUILD_DIR = Join-Path $REPO_DIR "build"

# ── Read / bump version ───────────────────────────────────────────────────────
$versionFile = Join-Path $REPO_DIR "version.py"
$vContent    = Get-Content $versionFile -Raw

if ($vContent -match 'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"') {
    [int]$majorVer = $Matches[1]
    [int]$minorVer = $Matches[2]
    [int]$patchVer = $Matches[3]
} else {
    Write-Error "Cannot parse VERSION from version.py"; exit 1
}

if ($BumpPatch) {
    $patchVer++
    $vContent = $vContent -replace 'VERSION\s*=\s*"\d+\.\d+\.\d+"',
                                    "VERSION = `"$majorVer.$minorVer.$patchVer`""
    $vContent = $vContent -replace 'VERSION_TUPLE\s*=\s*\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
                                    "VERSION_TUPLE = ($majorVer, $minorVer, $patchVer, 0)"
    Set-Content $versionFile $vContent -NoNewline
    Write-Host "Version bumped to $majorVer.$minorVer.$patchVer" -ForegroundColor Cyan
}

$VERSION   = "$majorVer.$minorVer.$patchVer"
$TAG       = "v$VERSION"
$DIST_NAME = "HazariTrackerBio-v$VERSION"
$ZIP_NAME  = "$DIST_NAME-win32.zip"

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  HazariTracker Bio  --  Build  $TAG"      -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# ── Verify 32-bit Python ──────────────────────────────────────────────────────
Write-Host "[1/4] Verifying 32-bit Python..." -ForegroundColor Yellow
if (-not (Test-Path $PYTHON32)) {
    Write-Error "32-bit Python not found at: $PYTHON32`nInstall Python 3.11 x86 to C:\Python311-32\"
    exit 1
}
$pyBits = & $PYTHON32 -c "import struct; print(struct.calcsize('P')*8)"
if ($pyBits -ne "32") {
    Write-Error "Python at $PYTHON32 reports $pyBits-bit. Must be 32-bit for Mantra SDK."
    exit 1
}
Write-Host "      Python 32-bit confirmed." -ForegroundColor Green

# ── Clean previous build ──────────────────────────────────────────────────────
Write-Host "[2/4] Cleaning previous build..." -ForegroundColor Yellow
Remove-Item $DIST_DIR  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $BUILD_DIR -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "      Done." -ForegroundColor Green

# ── Build with PyInstaller ────────────────────────────────────────────────────
Write-Host "[3/4] Running PyInstaller..." -ForegroundColor Yellow
Set-Location $REPO_DIR

# Run via cmd so stderr (PyInstaller INFO logs) does not trip StrictMode
$pyiArgs = "-m PyInstaller HazariTrackerBio.spec --clean --noconfirm"
cmd /c "`"$PYTHON32`" $pyiArgs 2>&1" | ForEach-Object { Write-Host "      $_" }

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller failed (exit $LASTEXITCODE)"; exit 1
}

$exeFolder = Join-Path $DIST_DIR $DIST_NAME
if (-not (Test-Path $exeFolder)) {
    Write-Error "Expected dist folder not found: $exeFolder"; exit 1
}
Write-Host "      EXE folder: $exeFolder" -ForegroundColor Green

# ── Zip the dist folder ───────────────────────────────────────────────────────
Write-Host "[4/4] Zipping dist folder..." -ForegroundColor Yellow
$zipPath = Join-Path $DIST_DIR $ZIP_NAME
$maxRetries = 5
$retryCount = 0
$zipped = $false

while (-not $zipped -and $retryCount -lt $maxRetries) {
    try {
        $retryCount++
        if ($retryCount -gt 1) {
            Write-Host "      Retrying zip compression (attempt $retryCount of $maxRetries)..." -ForegroundColor Yellow
            Start-Sleep -Seconds 3
        } else {
            Start-Sleep -Seconds 3  # Wait for indexer / Defender to finish scanning newly built files
        }
        Compress-Archive -Path "$exeFolder\*" -DestinationPath $zipPath -Force
        $zipped = $true
    } catch {
        if ($retryCount -eq $maxRetries) {
            throw $_
        }
    }
}
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "      Created: $ZIP_NAME  ($sizeMB MB)" -ForegroundColor Green

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Build complete!  Version: $TAG"           -ForegroundColor Green
Write-Host "  EXE folder : $exeFolder"                  -ForegroundColor Green
Write-Host "  ZIP archive: $zipPath"                    -ForegroundColor Green
Write-Host ""
Write-Host "  To create the Windows Installer + GitHub Release, run:"
Write-Host "      .\publish.ps1"                        -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
