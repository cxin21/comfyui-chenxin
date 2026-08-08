<#
.SYNOPSIS
  Zero-dependency environment and cache-integrity checker for character-video-pipeline.
.DESCRIPTION
  Runs BEFORE any prompt authoring, file write, or capability probe.
  Checks cache integrity (key files exist), Python availability, ComfyUI reachability,
  then delegates to the runtime preflight (preflight.py). A blocker means STOP.
.PARAMETER ComfyUrl
  ComfyUI base URL. Defaults to http://127.0.0.1:8188.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File preflight-env.ps1
#>

[CmdletBinding()]
param(
    [string]$ComfyUrl = "http://127.0.0.1:8188"
)

$ErrorActionPreference = "Stop"

$skillRoot  = $PSScriptRoot
$runtimeDir = Join-Path $skillRoot "runtime"
$blockers   = @()

function Ok($m)   { Write-Host "  [OK]   $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [WARN] $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "  [FAIL] $m" -ForegroundColor Red }
function Fix($m)  { Write-Host "         -> $m" -ForegroundColor Cyan }

# ── Phase 1: Cache integrity (zero-dependency) ──────────────────────
Write-Host "[1/4] Cache integrity..." -ForegroundColor Cyan

$required = @(
    "preflight.py",
    "attempt_state.py",
    "camera_config_helper.py",
    "workflow_assets.py",
    "run_stage.py",
    "result_manifest.py",
    "config_contract.py",
    "stage_config_surface.py"
)

$missing = @()
foreach ($f in $required) {
    if (-not (Test-Path (Join-Path $runtimeDir $f))) { $missing += $f }
}

if ($missing.Count -gt 0) {
    $blockers += "stale_cache"
    Bad "Cache is stale -- missing $($missing.Count) required runtime file(s):"
    $missing | ForEach-Object { Write-Host "         - $_" -ForegroundColor Red }
    Fix "Re-run the installer to sync the plugin cache:"
    Write-Host "         powershell -ExecutionPolicy Bypass -File D:\Projects\comfyui-chenxin\scripts\install.ps1" -ForegroundColor Cyan
} else {
    Ok "All $($required.Count) required runtime files present"
}

# ── Phase 2: Python ──────────────────────────────────────────────────
Write-Host "[2/4] Python..." -ForegroundColor Cyan

$py = $null

# 2a. PATH lookup
foreach ($c in @("python", "py", "python3")) {
    $g = Get-Command $c -ErrorAction SilentlyContinue
    if ($g) { $py = $g.Source; break }
}

# 2b. Common-location fallback (including ComfyUI embedded Python)
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

# ── Phase 3: ComfyUI ─────────────────────────────────────────────────
Write-Host "[3/4] ComfyUI..." -ForegroundColor Cyan

try {
    $r = Invoke-WebRequest -Uri "$ComfyUrl/system_stats" -TimeoutSec 5 -UseBasicParsing
    $s = $r.Content | ConvertFrom-Json
    $gpuName = if ($s.devices -and $s.devices.Count -gt 0) { $s.devices[0].name } else { "unknown" }
    Ok "ComfyUI reachable at $ComfyUrl (GPU: $gpuName)"
} catch {
    $blockers += "comfyui_unreachable"
    Bad "ComfyUI not reachable at $ComfyUrl"
    Fix "Start ComfyUI before running any production stage"
}

# ── Phase 4: Runtime preflight (requires Python + clean earlier checks) ─
Write-Host "[4/4] Runtime preflight..." -ForegroundColor Cyan

if ($blockers.Count -eq 0 -and $py) {
    Push-Location $skillRoot
    try {
        $out = & $py -m runtime.preflight 2>&1
        $out | ForEach-Object { Write-Host "  $_" }
        if ($LASTEXITCODE -ne 0) {
            $blockers += "preflight_failed"
            Bad "Runtime preflight reported blockers (see output above)"
        } else {
            Ok "Runtime preflight passed"
        }
    } catch {
        $blockers += "preflight_error"
        Bad "Runtime preflight execution error: $_"
    } finally {
        Pop-Location
    }
} else {
    Warn "Skipping runtime preflight (blocked by earlier checks)"
}

# ── Summary ──────────────────────────────────────────────────────────
Write-Host ""
if ($blockers.Count -eq 0) {
    Write-Host "=== ALL CHECKS PASSED -- ready for production ===" -ForegroundColor Green
    exit 0
} else {
    Write-Host "=== $($blockers.Count) BLOCKER(S) -- fix before proceeding ===" -ForegroundColor Red
    Write-Host "Do NOT attempt workarounds. Fix the blockers first." -ForegroundColor Yellow
    exit 1
}