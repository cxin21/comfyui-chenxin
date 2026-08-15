<#
.SYNOPSIS
  comfyui-chenxin one-shot installer for Claude Code on Windows.
.DESCRIPTION
  Per P7 of the Skill-owned CLI / no-MCP plan, this script no longer
  touches %USERPROFILE%\.codex\config.toml and no longer stages a Codex
  plugin cache. It ensures the Anima tag-catalog SQLite bundle is in
  place, runs the source-tree release verifier, and pip-installs every
  Skill + the comfyui-http-runtime transport in editable mode so the
  Claude Code marketplace plugin (.claude-plugin/plugin.json) resolves
  them on the next session.
.PARAMETER RepoRoot
  Path to the comfyui-chenxin source checkout. Default: parent of this
  script's directory.
.PARAMETER SkipProbe
  Skip the ComfyUI reachability probe.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
.NOTES
  Idempotent.
#>

[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [switch]$SkipProbe
)

$ErrorActionPreference = 'Stop'

function Step($msg) { Write-Host "[install] $msg" }
function Warn($msg) { Write-Host "[install][warn] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "[install][error] $msg" -ForegroundColor Red; exit 1 }

# Resolve RepoRoot if not provided.
if (-not $RepoRoot) {
    $scriptPath = $MyInvocation.MyCommand.Path
    if ($scriptPath) {
        $RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $scriptPath) '..')).Path
    } else {
        Die 'Cannot determine RepoRoot; pass -RepoRoot explicitly.'
    }
}

# Pick a working Python.
$pythonExe = $null
foreach ($candidate in @('py','python','python3')) {
    $exe = $candidate
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $pythonExe = $exe
        break
    }
}
if (-not $pythonExe) {
    Die 'Python is required so the Skills can be pip-installed.'
}

if (-not $SkipProbe) {
    try {
        $probe = [System.Net.WebRequest]::CreateHttp('http://127.0.0.1:8188/system_stats')
        $probe.Timeout = 3000
        $probe.GetResponse() | Out-Null
    } catch { Warn 'ComfyUI at http://127.0.0.1:8188 did not respond (continuing).' }
}

# Download the Anima tag-catalog SQLite files (gitignored, too large for
# git; distributed as a release asset) and verify sha256 in place.
function Ensure-AnimaCatalog {
    param(
        [string]$SkillRoot,
        [string]$Version,
        [string]$Repo = 'cxin21/comfyui-chenxin'
    )
    $knowledgeDir = Join-Path $SkillRoot 'knowledge'
    $expected = @('tag-catalog.sqlite','tags.sqlite')
    $missing = @()
    foreach ($f in $expected) {
        if (-not (Test-Path (Join-Path $knowledgeDir $f))) { $missing += $f }
    }
    if ($missing.Count -eq 0) {
        Step 'Anima catalog already present in source tree'
        return
    }

    $releaseTag = "v$Version"
    $assetBase = "anima-catalog-$Version"
    $baseUrl = "https://github.com/$Repo/releases/download/$releaseTag"
    $zipUrl = "$baseUrl/$assetBase.zip"
    $shaUrl = "$baseUrl/$assetBase.zip.sha256"

    $tmpDir = Join-Path $env:TEMP "comfyui-chenxin-catalog-$Version"
    if (Test-Path -LiteralPath $tmpDir) { Remove-Item -LiteralPath $tmpDir -Recurse -Force }
    New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
    $zipPath = Join-Path $tmpDir "$assetBase.zip"
    $shaPath = Join-Path $tmpDir "$assetBase.zip.sha256"

    Step "Anima catalog missing ($($missing -join ', ')); downloading $assetBase.zip from $baseUrl"
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $wc = New-Object System.Net.WebClient
        $wc.DownloadFile($zipUrl, $zipPath)
        $wc.DownloadFile($shaUrl, $shaPath)
    } catch {
        Die "Failed to download catalog from $baseUrl. Manual recovery: download $assetBase.zip + .sha256 from the v$Version release and place the files under $knowledgeDir. Error: $($_.Exception.Message)"
    }

    $expectedSha = ((Get-Content -LiteralPath $shaPath -Raw -ErrorAction Stop).Trim() -split '\s+')[0].ToLower()
    $actualSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLower()
    if ($expectedSha -ne $actualSha) {
        Die "catalog sha256 mismatch: expected $expectedSha got $actualSha. Refusing to install unverified catalog."
    }
    Step "catalog sha256 verified: $actualSha"

    Expand-Archive -LiteralPath $zipPath -DestinationPath $tmpDir -Force
    $extracted = Join-Path $tmpDir 'anima-prompt-v1\knowledge'
    if (-not (Test-Path -LiteralPath $extracted)) {
        Die 'Extracted zip missing expected layout (anima-prompt-v1/knowledge/).'
    }
    if (-not (Test-Path $knowledgeDir)) { New-Item -ItemType Directory -Path $knowledgeDir -Force | Out-Null }
    Copy-Item -Path (Join-Path $extracted '*') -Destination $knowledgeDir -Recurse -Force
    Step "Anima catalog installed to $knowledgeDir"
    Remove-Item -LiteralPath $tmpDir -Recurse -Force
}

$releaseVerifier = Join-Path $RepoRoot 'scripts\verify_release.py'
if (-not (Test-Path -LiteralPath $releaseVerifier -PathType Leaf)) {
    Die "Missing release verifier at $releaseVerifier."
}

Step 'verifying source tree'
& $pythonExe $releaseVerifier --source-root $RepoRoot | Out-Null
if ($LASTEXITCODE -ne 0) { Die 'Source release verification failed.' }
Step 'Source release verified'

Step 'ensuring Anima catalog in source tree'
$animaSkillRoot = Join-Path $RepoRoot 'skills\anima-prompt-v1'
$pluginJsonPath = Join-Path $RepoRoot '.claude-plugin\plugin.json'
if (Test-Path -LiteralPath $pluginJsonPath -PathType Leaf) {
    $plugin = Get-Content $pluginJsonPath -Raw | ConvertFrom-Json
    $version = [string]$plugin.version
    if (-not $version) { Die 'plugin.json has no version.' }
    Ensure-AnimaCatalog -SkillRoot $animaSkillRoot -Version $version
} else {
    Warn 'No .claude-plugin/plugin.json; skipping Anima catalog download.'
}

Step 'pip-installing Skills + comfyui-http-runtime (editable)'
$installPkgs = @(
    @{ Name = 'comfyui-http-runtime'; Src = Join-Path $RepoRoot 'runtime\comfyui_http' },
    @{ Name = 'anima-prompt-v1';      Src = Join-Path $RepoRoot 'skills\anima-prompt-v1' },
    @{ Name = 'minimax-h3-prompt';    Src = Join-Path $RepoRoot 'skills\minimax-h3-prompt' },
    @{ Name = 'camera-image';         Src = Join-Path $RepoRoot 'skills\camera-image' },
    @{ Name = 'camera-multiview';     Src = Join-Path $RepoRoot 'skills\camera-multiview' },
    @{ Name = 'camera-video';         Src = Join-Path $RepoRoot 'skills\camera-video' }
)
foreach ($p in $installPkgs) {
    if (Test-Path (Join-Path $p.Src 'pyproject.toml')) {
        & $pythonExe -m pip install -e $p.Src --quiet | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Die "pip install -e $($p.Src) failed (rc=$LASTEXITCODE)."
        }
        Step "pip-installed $($p.Name)"
    } else {
        Warn "skip $($p.Name) (no pyproject.toml at $($p.Src))"
    }
}

Step 'DONE.'
Step 'next: reload the Claude Code plugin (marketplace id: comfyui-chenxin).'
exit 0
