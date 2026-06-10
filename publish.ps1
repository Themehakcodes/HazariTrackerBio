#!/usr/bin/env pwsh
# publish.ps1 - Create Windows Installer and publish GitHub Release
# PREREQUISITES:
#   - Run .\build.ps1 first to produce the EXE folder
#   - Inno Setup 6 installed: https://jrsoftware.org/isinfo.php
#   - Set env var before running:  $env:GITHUB_TOKEN = "github_pat_..."
# USAGE:
#   .\publish.ps1             # Full publish (installer + GitHub release)
#   .\publish.ps1 -DryRun     # Compile installer only, skip git + GitHub

param(
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Config ────────────────────────────────────────────────────────────────────
$REPO_DIR     = $PSScriptRoot
$DIST_DIR     = Join-Path $REPO_DIR "dist"
$ISS_FILE     = Join-Path $REPO_DIR "HazariTrackerBio.iss"
$REPO_OWNER   = "Themehakcodes"
$REPO_NAME    = "HazariTrackerBio"
$GITHUB_TOKEN = $env:GITHUB_TOKEN

# Inno Setup compiler locations
$ISCC_PATHS = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
)
$ISCC = $null
foreach ($p in $ISCC_PATHS) {
    if (Test-Path $p) { $ISCC = $p; break }
}

# ── Read version from version.py ──────────────────────────────────────────────
$versionFile = Join-Path $REPO_DIR "version.py"
$vContent    = Get-Content $versionFile -Raw

if ($vContent -match 'VERSION\s*=\s*"(\d+)\.(\d+)\.(\d+)"') {
    [int]$majorVer = $Matches[1]
    [int]$minorVer = $Matches[2]
    [int]$patchVer = $Matches[3]
} else {
    Write-Error "Cannot parse VERSION from version.py"
    exit 1
}

$VERSION    = "$majorVer.$minorVer.$patchVer"
$TAG        = "v$VERSION"
$DIST_NAME  = "HazariTrackerBio-v$VERSION"
$ZIP_NAME   = "$DIST_NAME-win32.zip"
$SETUP_NAME = "HazariTrackerBio-v$VERSION-Setup"
$SETUP_EXE  = Join-Path $DIST_DIR "$SETUP_NAME.exe"
$ZIP_PATH   = Join-Path $DIST_DIR $ZIP_NAME

Write-Host ""
Write-Host "============================================" -ForegroundColor Magenta
Write-Host "  HazariTracker Bio  --  Publish  $TAG"      -ForegroundColor Magenta
Write-Host "============================================" -ForegroundColor Magenta
Write-Host ""

# ── [1/5] Check PyInstaller build output ──────────────────────────────────────
Write-Host "[1/5] Checking build output..." -ForegroundColor Yellow
$exeFolder = Join-Path $DIST_DIR $DIST_NAME

if (-not (Test-Path $exeFolder)) {
    Write-Error "EXE folder not found: $exeFolder`nRun .\build.ps1 first!"
    exit 1
}
if (-not (Test-Path $ZIP_PATH)) {
    Write-Warning "ZIP not found: $ZIP_PATH  (will skip ZIP upload to GitHub)"
}
Write-Host "      EXE folder OK: $exeFolder" -ForegroundColor Green

# ── [2/5] Compile Inno Setup installer ────────────────────────────────────────
Write-Host "[2/5] Compiling Inno Setup installer..." -ForegroundColor Yellow

if ($null -eq $ISCC) {
    Write-Error (
        "Inno Setup (ISCC.exe) not found.`n" +
        "Download from: https://jrsoftware.org/isinfo.php`n" +
        "Checked:`n  " + ($ISCC_PATHS -join "`n  ")
    )
    exit 1
}

Write-Host "      Compiler: $ISCC"
cmd /c "`"$ISCC`" `"$ISS_FILE`" /DMyAppVersion=$VERSION 2>&1" |
    ForEach-Object { Write-Host "      $_" }

if ($LASTEXITCODE -ne 0) {
    Write-Error "Inno Setup failed (exit $LASTEXITCODE)"
    exit 1
}

if (-not (Test-Path $SETUP_EXE)) {
    Write-Error "Expected installer not found after compile: $SETUP_EXE"
    exit 1
}

$setupMB = [math]::Round((Get-Item $SETUP_EXE).Length / 1MB, 1)
Write-Host "      Installer: $SETUP_NAME.exe ($setupMB MB)" -ForegroundColor Green

# ── DryRun exit point ─────────────────────────────────────────────────────────
if ($DryRun) {
    Write-Host ""
    Write-Host "DryRun mode - skipping git and GitHub steps." -ForegroundColor Gray
    Write-Host "Installer ready at: $SETUP_EXE" -ForegroundColor Cyan
    exit 0
}

# ── [3/5] Check token ─────────────────────────────────────────────────────────
if (-not $GITHUB_TOKEN) {
    Write-Error (
        "GITHUB_TOKEN is not set.`n" +
        "Run: `$env:GITHUB_TOKEN = 'github_pat_...' then retry."
    )
    exit 1
}

# ── [4/5] Git commit + tag ────────────────────────────────────────────────────
Write-Host "[4/5] Committing and tagging $TAG..." -ForegroundColor Yellow
Set-Location $REPO_DIR

git add -A
git commit -m "chore: Release $TAG" --allow-empty 2>&1 |
    ForEach-Object { Write-Host "      git: $_" }

# Temporarily allow errors for tag cleanup
$oldEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
git tag -d $TAG 2>$null
git push origin ":refs/tags/$TAG" 2>$null
$ErrorActionPreference = $oldEAP

git tag $TAG
git push origin main --tags 2>&1 |
    ForEach-Object { Write-Host "      git: $_" }

if ($LASTEXITCODE -ne 0) {
    Write-Error "git push failed"
    exit 1
}
Write-Host "      Tag $TAG pushed." -ForegroundColor Green

# ── [5/5] GitHub Release + asset upload ──────────────────────────────────────
Write-Host "[5/5] Creating GitHub Release and uploading assets..." -ForegroundColor Yellow

$headers = @{
    Authorization          = "token $GITHUB_TOKEN"
    Accept                 = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$releaseBody = (
    "## HazariTracker Bio $TAG`n`n" +
    "### Downloads`n" +
    "| File | Description |`n" +
    "|------|-------------|`n" +
    "| HazariTrackerBio-v$VERSION-Setup.exe | Recommended - Windows Installer (bundles all DLLs, Start Menu shortcut) |`n" +
    "| HazariTrackerBio-v$VERSION-win32.zip | Portable ZIP - extract anywhere and run |`n`n" +
    "### Includes`n" +
    "- Auto-continuous fingerprint scanner (Mantra MFS100)`n" +
    "- Employee enrolment with fingerprint capture`n" +
    "- Date-wise attendance report with CSV export`n" +
    "- Minimises to system tray on close`n`n" +
    "### Prerequisites`n" +
    "1. **Mantra MFS100 Driver** - [Download here](https://www.mantratec.com/resources/Software-Resources/MFS100-Software)`n" +
    "   (installs the MFS100.sys kernel driver)`n" +
    "2. **Windows .NET Framework 4.x** (ships with Windows 10/11)`n`n" +
    "### Install`n" +
    "Run HazariTrackerBio-v$VERSION-Setup.exe as Administrator.`n" +
    "The installer checks prerequisites and warns if anything is missing."
)

$releasePayload = @{
    tag_name         = $TAG
    target_commitish = "main"
    name             = "HazariTracker Bio $TAG"
    body             = $releaseBody
    draft            = $false
    prerelease       = $false
} | ConvertTo-Json -Depth 3

try {
    $release = Invoke-RestMethod `
        -Uri "https://api.github.com/repos/$REPO_OWNER/$REPO_NAME/releases" `
        -Method Post `
        -Headers $headers `
        -Body $releasePayload `
        -ContentType "application/json"
    Write-Host "      Release created: $($release.html_url)" -ForegroundColor Green
} catch {
    Write-Error "Failed to create GitHub Release: $_"
    exit 1
}

# Upload helper function
function Upload-Asset {
    param(
        [string]$FilePath,
        [string]$UploadBaseUrl,
        [hashtable]$ReqHeaders
    )
    $fileName  = Split-Path $FilePath -Leaf
    $uploadUrl = $UploadBaseUrl -replace '\{\?name,label\}', "?name=$fileName"
    $bytes     = [System.IO.File]::ReadAllBytes($FilePath)
    $fileMB    = [math]::Round($bytes.Length / 1MB, 1)

    Write-Host "      Uploading $fileName ($fileMB MB)..." -NoNewline
    try {
        $resp = Invoke-RestMethod `
            -Uri $uploadUrl `
            -Method Post `
            -Headers $ReqHeaders `
            -Body $bytes `
            -ContentType "application/octet-stream"
        Write-Host " OK" -ForegroundColor Green
        Write-Host "        $($resp.browser_download_url)" -ForegroundColor DarkGray
    } catch {
        Write-Warning "Upload failed for $fileName`: $_"
    }
}

$uploadBase = $release.upload_url

# Setup EXE — primary asset
Upload-Asset -FilePath $SETUP_EXE -UploadBaseUrl $uploadBase -ReqHeaders $headers

# Portable ZIP — secondary asset
if (Test-Path $ZIP_PATH) {
    Upload-Asset -FilePath $ZIP_PATH -UploadBaseUrl $uploadBase -ReqHeaders $headers
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Published $TAG successfully!"              -ForegroundColor Green
Write-Host "  $($release.html_url)"                     -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
