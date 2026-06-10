#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Build HazariTracker Bio EXE and publish a GitHub Release.

.DESCRIPTION
    1. Reads version from version.py
    2. Commits + tags the release in git
    3. Builds the EXE with PyInstaller (32-bit Python)
    4. Zips the dist folder
    5. Creates a GitHub Release via `gh` CLI and uploads the ZIP

.USAGE
    .\build.ps1              # Build and publish
    .\build.ps1 -SkipGitHub  # Build only (no GitHub release)
    .\build.ps1 -Patch       # Auto-increment patch version before building
#>

param(
    [switch]$SkipGitHub,
    [switch]$Patch
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
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    $patch = [int]$Matches[3]
} else {
    Write-Error "Cannot parse VERSION from version.py"
}

if ($Patch) {
    $patch++
    $vContent = $vContent -replace 'VERSION\s*=\s*"\d+\.\d+\.\d+"', "VERSION = `"$major.$minor.$patch`""
    $vContent = $vContent -replace 'VERSION_TUPLE\s*=\s*\(\d+,\s*\d+,\s*\d+,\s*\d+\)',
                                    "VERSION_TUPLE = ($major, $minor, $patch, 0)"
    Set-Content $versionFile $vContent -NoNewline
    Write-Host "Version bumped to $major.$minor.$patch" -ForegroundColor Cyan
}

$VERSION = "$major.$minor.$patch"
$TAG     = "v$VERSION"
$DIST_NAME = "HazariTrackerBio-v$VERSION"
$ZIP_NAME  = "$DIST_NAME-win32.zip"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  HazariTracker Bio  Build  $TAG" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Clean previous build ──────────────────────────────────────────────────────
Write-Host "[1/5] Cleaning previous build…" -ForegroundColor Yellow
Remove-Item $DIST_DIR  -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $BUILD_DIR -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "      Done." -ForegroundColor Green

# ── Build with PyInstaller ────────────────────────────────────────────────────
Write-Host "[2/5] Building EXE with PyInstaller…" -ForegroundColor Yellow
& $PYTHON32 -m PyInstaller HazariTrackerBio.spec --clean --noconfirm 2>&1 |
    ForEach-Object { Write-Host "      $_" }

$exeFolder = Join-Path $DIST_DIR $DIST_NAME
if (-not (Test-Path $exeFolder)) {
    Write-Error "Build failed — dist folder not found: $exeFolder"
}
Write-Host "      EXE built at: $exeFolder" -ForegroundColor Green

# ── Zip the dist folder ───────────────────────────────────────────────────────
Write-Host "[3/5] Creating ZIP archive…" -ForegroundColor Yellow
$zipPath = Join-Path $DIST_DIR $ZIP_NAME
Compress-Archive -Path "$exeFolder\*" -DestinationPath $zipPath -Force
$sizeMB = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
Write-Host "      $ZIP_NAME  ($sizeMB MB)" -ForegroundColor Green

if ($SkipGitHub) {
    Write-Host ""
    Write-Host "Skipping GitHub release (-SkipGitHub flag set)." -ForegroundColor Gray
    Write-Host "ZIP ready at: $zipPath" -ForegroundColor Cyan
    exit 0
}

# ── Git commit + tag ──────────────────────────────────────────────────────────
Write-Host "[4/5] Committing and tagging $TAG…" -ForegroundColor Yellow
Set-Location $REPO_DIR
git add -A
git commit -m "Release $TAG" --allow-empty
if ($LASTEXITCODE -ne 0) { Write-Error "git commit failed" }

# Delete existing tag if it exists
git tag -d $TAG 2>$null
git push origin :refs/tags/$TAG 2>$null
git tag $TAG
git push origin main --tags
Write-Host "      Tag $TAG pushed." -ForegroundColor Green

# ── GitHub Release ────────────────────────────────────────────────────────────
Write-Host "[5/5] Creating GitHub Release $TAG…" -ForegroundColor Yellow

$releaseNotes = @"
## HazariTracker Bio $TAG

### What's included
- Auto-continuous fingerprint scanner (Mantra MFS100)
- Employee enrolment with fingerprint capture
- Date-wise attendance report with CSV export
- Minimises to system tray on close

### Prerequisites (must be installed on the machine)
1. **Mantra MFS100 Driver** — installs \`MFS100.sys\` kernel driver
2. **Windows .NET Framework 4.x** — ships with Windows 10/11

### Run
Double-click \`HazariTrackerBio.exe\`
"@

gh release create $TAG $zipPath `
    --title "HazariTracker Bio $TAG" `
    --notes $releaseNotes `
    --repo Themehakcodes/HazariTrackerBio

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Release $TAG published successfully!" -ForegroundColor Green
    Write-Host "  https://github.com/Themehakcodes/HazariTrackerBio/releases/tag/$TAG" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Error "gh release create failed"
}
