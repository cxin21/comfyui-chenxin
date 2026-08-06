<#
.SYNOPSIS
  Zero-dependency environment checker for prompt-forge.
.DESCRIPTION
  Checks Python availability and key internals files. prompt-forge is offline,
  so no ComfyUI check is needed. A blocker means STOP.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File preflight-env.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$skillRoot    = $PSScriptRoot
$internalsDir = Join-Path $skillRoot "internals"
$blockers     = @()

function Ok($m)  { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Bad($m) { Write-Host "  [FAIL] $m" -ForegroundColor Red }
function Fix($m) { Write-Host "         -> $m" -ForegroundColor Cyan }

# ── Phase 1: Cache integrity ─────────────────────────────────────────
Write-Host "[1/2] Cache integrity..." -ForegroundColor Cyan

$required = @(
    "tag_lookup.py",
    "dialect_lookup.py",
    "style_lookup.py",
    "prompt_compile.py",
    "evaluate.py",
    "prompt_package.py"
)

$missing = @()
foreach ($f in $required) {
    if (-not (Test-Path (Join-Path $internalsDir $f))) { $missing += $f }
}

if ($missing.Count -gt 0) {
    $blockers += "stale_cache"
    Bad "Cache is stale -- missing $($missing.Count) required file(s):"
    $missing | ForEach-Object { Write-Host "         - $_" -ForegroundColor Red }
    Fix "Re-run the installer to sync the plugin cache:"
    Write-Host "         powershell -ExecutionPolicy Bypass -File D:\Projects\comfyui-chenxin\scripts\install.ps1" -ForegroundColor Cyan
} else {
    Ok "All $($required.Count) required internals files present"
}

# ── Phase 2: Python ──────────────────────────────────────────────────
Write-Host "[2/2] Python..." -ForegroundColor Cyan

$py = $null

foreach ($c in @("python", "py", "python3")) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $py = $g.Source; break }
}

if (-not $py) {
    $candidates = @(
        "E:\Comfy\comfyui-licyk-20260608\core\python\python.exe",
        "E:\Comfy\comfyui-licyk-20260608\python_embeded\python.exe",
        "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) {
            $py = $p
            $env:PATH = (Split-Path $p -Parent) + ";" + $env:PATH
            break
        }
    }
}

if (-not $py) {
    $blockers += "python_missing"
    Bad "Python not found on PATH or in common locations"
    Fix "Install Python 3.10+ and add to PATH, or ensure ComfyUI embedded Python is accessible"
} else {
    $v = & $py --version 2>&1
    Ok "Python: $py ($v)"
}

# ── Summary ──────────────────────────────────────────────────────────
Write-Host ""
if ($blockers.Count -eq 0) {
    Write-Host "=== ALL CHECKS PASSED -- ready for prompt authoring ===" -ForegroundColor Green
    exit 0
} else {
    Write-Host "=== $($blockers.Count) BLOCKER(S) -- fix before proceeding ===" -ForegroundColor Red
    Write-Host "Do NOT attempt workarounds. Fix the blockers first." -ForegroundColor Yellow
    exit 1
}