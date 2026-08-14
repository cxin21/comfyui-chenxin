<#
.SYNOPSIS
  comfyui-chenxin one-shot installer for Codex on Windows.
.DESCRIPTION
  Writes the upstream comfyui-mcp stdio block into %USERPROFILE%\.codex\config.toml,
  pip-installs the project MCP server and skills (so the host can spawn
  comfyui-chenxin-mcp-server), then stages the plugin (skills + mcp_server +
  .codex-plugin + .mcp.json + LICENSE + README.md) into
  %USERPROFILE%\.codex\plugins\cache\personal\comfyui-chenxin\<version>.
  Re-running replaces the previous version directory; config.toml is backed up
  once per run before any edit.
.PARAMETER Mode
  npx  : portable default; launches comfyui-mcp via `npx -y comfyui-mcp@<ver>`
  local: offline; launches via `node <clone>/dist/index.js`
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1
  powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -Mode local -LocalClonePath C:\path\to\comfyui-mcp
.NOTES
  Idempotent. Re-running replaces existing registrations; Codex side keeps a
  timestamped backup of config.toml.
#>

[CmdletBinding()]
param(
    [string]$RepoRoot = '',
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [ValidateSet('npx','local')] [string]$Mode = 'npx',
    [string]$PackageVersion = '0.49.8',
    [string]$ComfyUrl = 'http://127.0.0.1:8188',
    [string]$LocalClonePath = '',
    [switch]$SkipCodex,
    [switch]$SkipProbe
)

$ErrorActionPreference = 'Stop'

function Step($msg) { Write-Host "[install] $msg" }
function Warn($msg) { Write-Host "[install][warn] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "[install][error] $msg" -ForegroundColor Red; exit 1 }

# ---------- 0. Resolve the upstream comfyui-mcp launch spec ----------

$command = $null
$argList = @()
switch ($Mode) {
    'npx' {
        $npxExe = Get-Command npx.cmd -ErrorAction SilentlyContinue
        if (-not $npxExe) { $npxExe = Get-Command npx -ErrorAction SilentlyContinue }
        if (-not $npxExe) { Die 'Mode=npx requires npx.cmd or npx on PATH. Use -Mode local if you only have node.' }
        $command = $npxExe.Source
        $argList = @('-y', "comfyui-mcp@$PackageVersion", '--full', '--comfyui-url', $ComfyUrl)
    }
    'local' {
        if (-not $LocalClonePath) { Die '-Mode local requires -LocalClonePath.' }
        $dist = Join-Path $LocalClonePath 'dist\index.js'
        if (-not (Test-Path $dist)) { Die "Local clone build not found at $dist." }
        $command = 'node'
        $argList = @($dist.Replace('\','/'), '--full', '--comfyui-url', $ComfyUrl)
    }
}

if (-not $SkipProbe) {
    try {
        $probe = [System.Net.WebRequest]::CreateHttp("$ComfyUrl/system_stats")
        $probe.Timeout = 3000
        $probe.GetResponse() | Out-Null
    } catch { Warn "ComfyUI at $ComfyUrl did not respond (continuing)." }
}

# ---------- Helpers ----------

function Format-TomlArgs([string[]]$arr) {
    return ($arr | ForEach-Object { '"' + ($_ -replace '\\','\\').Replace('"','\"') + '"' }) -join ', '
}

function Set-TomlBlock {
    param([string]$Path, [string]$Header, [string[]]$BlockLines)
    $lines = @()
    if (Test-Path $Path) { $lines = @(Get-Content $Path) }
    $out = New-Object System.Collections.Generic.List[string]
    $skipping = $false
    $replaced = $false
    foreach ($line in $lines) {
        $trim = $line.Trim()
        if ($trim.StartsWith('[') -and $trim.EndsWith(']')) {
            if ($skipping) { $skipping = $false }
            if ($trim -eq $Header) {
                foreach ($b in $BlockLines) { $out.Add($b) }
                $replaced = $true
                $skipping = $true
                continue
            }
        }
        if (-not $skipping) { $out.Add($line) }
    }
    if (-not $replaced) {
        if ($out.Count -gt 0 -and $out[$out.Count - 1] -ne '') { $out.Add('') }
        foreach ($b in $BlockLines) { $out.Add($b) }
    }
    Set-Content -Path $Path -Value $out -Encoding UTF8
}

# Download the Anima tag-catalog SQLite files (gitignored, too large for git;
# distributed as a release asset) and verify sha256 before installing.
function Ensure-AnimaCatalog {
    param(
        [string]$CacheRoot,
        [string]$Version,
        [string]$Repo = 'cxin21/comfyui-chenxin'
    )
    $skillRoot = Join-Path $CacheRoot 'skills\anima-prompt-v1'
    $knowledgeDir = Join-Path $skillRoot 'knowledge'
    $expected = @('tag-catalog.sqlite','tags.sqlite')
    $missing = @()
    foreach ($f in $expected) {
        if (-not (Test-Path (Join-Path $knowledgeDir $f))) { $missing += $f }
    }
    if ($missing.Count -eq 0) {
        Step 'Anima catalog already present in cache'
        return
    }

    $releaseTag = "v$Version"
    $assetBase = "anima-catalog-$Version"
    $baseUrl = "https://github.com/$Repo/releases/download/$releaseTag"
    $zipUrl = "$baseUrl/$assetBase.zip"
    $shaUrl = "$baseUrl/$assetBase.zip.sha256"

    $tmpDir = Join-Path $env:TEMP "comfyui-chenxin-catalog-$Version"
    if (Test-Path -LiteralPath $tmpDir) {
        Remove-Item -LiteralPath $tmpDir -Recurse -Force
    }
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
        Die "Extracted zip missing expected layout (anima-prompt-v1/knowledge/)."
    }
    if (-not (Test-Path $knowledgeDir)) {
        New-Item -ItemType Directory -Path $knowledgeDir -Force | Out-Null
    }
    Copy-Item -Path (Join-Path $extracted '*') -Destination $knowledgeDir -Recurse -Force
    Step "Anima catalog installed to $knowledgeDir"
    Remove-Item -LiteralPath $tmpDir -Recurse -Force
}

# Resolve RepoRoot if not provided (handles wrappers that leave $PSScriptRoot empty).
if (-not $RepoRoot) {
    $scriptPath = $MyInvocation.MyCommand.Path
    if ($scriptPath) {
        $RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $scriptPath) '..')).Path
    } else {
        Die 'Cannot determine RepoRoot; pass -RepoRoot explicitly.'
    }
}

$releaseVerifier = Join-Path $RepoRoot 'scripts\verify_release.py'
if (-not (Test-Path -LiteralPath $releaseVerifier -PathType Leaf)) {
    Die "Missing release verifier at $releaseVerifier."
}
$releaseStager = Join-Path $RepoRoot 'scripts\stage_release.py'
if (-not (Test-Path -LiteralPath $releaseStager -PathType Leaf)) {
    Die "Missing release stager at $releaseStager."
}
$verifyPython = Get-Command python -ErrorAction SilentlyContinue
if (-not $verifyPython) { $verifyPython = Get-Command py -ErrorAction SilentlyContinue }
if (-not $verifyPython) { Die 'Python is required for release verification.' }
if ($verifyPython.Name -eq 'py.exe') {
    & $verifyPython.Source -3 $releaseVerifier --source-root $RepoRoot | Out-Null
} else {
    & $verifyPython.Source $releaseVerifier --source-root $RepoRoot | Out-Null
}
if ($LASTEXITCODE -ne 0) { Die 'Source release verification failed.' }
Step 'Source release verified'

# ---------- 1. Codex: upstream MCP block + plugin cache ----------

if (-not $SkipCodex) {
    Step 'Codex: writing [mcp_servers.comfyui-mcp] into config.toml'
    $configPath = Join-Path $CodexHome 'config.toml'
    if (Test-Path $configPath) {
        $ts = (Get-Date).ToString('yyyyMMddHHmmss')
        $backup = "$configPath.bak-comfyui-chenxin-$ts"
        Copy-Item -Path $configPath -Destination $backup -Force
        Step "backed up $configPath -> $backup"
    }
    $argsStr = Format-TomlArgs $argList
    $block = @(
        '[mcp_servers.comfyui-mcp]'
        'type = "stdio"'
        "command = `"$command`""
        "args = [$argsStr]"
    )
    Set-TomlBlock -Path $configPath -Header '[mcp_servers.comfyui-mcp]' -BlockLines $block
    Step "wrote MCP block to $configPath"

    Step 'Codex: installing plugin into plugin cache'
    $pluginJsonPath = Join-Path $RepoRoot '.codex-plugin\plugin.json'
    if (-not (Test-Path $pluginJsonPath)) { Die "Missing $pluginJsonPath." }
    $plugin = Get-Content $pluginJsonPath -Raw | ConvertFrom-Json
    $version = [string]$plugin.version
    if (-not $version) { Die 'plugin.json has no version.' }
    $cacheRoot = Join-Path $CodexHome 'plugins\cache\personal\comfyui-chenxin'
    $stagingRoot = Join-Path $env:TEMP "comfyui-chenxin-install-$version"
    if (Test-Path -LiteralPath $stagingRoot) {
        $resolvedStaging = (Resolve-Path -LiteralPath $stagingRoot).Path
        $resolvedTemp = (Resolve-Path -LiteralPath $env:TEMP).Path
        if (-not $resolvedStaging.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase)) {
            Die "Refusing to remove staging path outside TEMP: $resolvedStaging"
        }
        Remove-Item -LiteralPath $resolvedStaging -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

    if ($verifyPython.Name -eq 'py.exe') {
        & $verifyPython.Source -3 $releaseStager --source-root $RepoRoot --destination-root $stagingRoot | Out-Null
    } else {
        & $verifyPython.Source $releaseStager --source-root $RepoRoot --destination-root $stagingRoot | Out-Null
    }
    if ($LASTEXITCODE -ne 0) { Die 'Plugin release staging failed.' }
    Step 'staged explicit plugin release file set'
    $stagedPlugin = Join-Path $stagingRoot '.codex-plugin\plugin.json'
    if (-not (Test-Path $stagedPlugin)) { Die "Staged plugin.json missing at $stagedPlugin." }
    $staged = Get-Content $stagedPlugin -Raw | ConvertFrom-Json
    if ([string]$staged.version -ne $version) { Die "Staged version [$($staged.version)] does not match directory." }
    if (-not (Test-Path (Join-Path $stagingRoot 'skills'))) { Die 'Staged skills/ missing.' }
    foreach ($asset in @('skills\anima-prompt-v1\SKILL.md','skills\minimax-h3-prompt\SKILL.md')) {
        if (-not (Test-Path (Join-Path $stagingRoot $asset))) { Die "Staged skill missing: $asset" }
    }

    if (Test-Path $cacheRoot) {
        $existing = @(Get-ChildItem $cacheRoot -Directory -Force -ErrorAction SilentlyContinue)
        foreach ($dir in $existing) {
            $full = $dir.FullName
            if (-not $full.StartsWith($cacheRoot, [StringComparison]::OrdinalIgnoreCase)) {
                Die "Refusing to delete path outside cache root: $full"
            }
            Step "removing previous version directory $full"
            Remove-Item -LiteralPath $full -Recurse -Force
        }
    }
    if (-not (Test-Path $cacheRoot)) { New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null }
    $target = Join-Path $cacheRoot $version
    Move-Item -Path $stagingRoot -Destination $target
    Step "installed plugin at $target"

    Ensure-AnimaCatalog -CacheRoot $target -Version $version
    Step 'Anima catalog ensured in plugin cache'

    if ($verifyPython.Name -eq 'py.exe') {
        & $verifyPython.Source -3 $releaseVerifier --source-root $RepoRoot --cache-root $target | Out-Null
    } else {
        & $verifyPython.Source $releaseVerifier --source-root $RepoRoot --cache-root $target | Out-Null
    }
    if ($LASTEXITCODE -ne 0) { Die 'Source/cache verification failed.' }
    Step 'Source/cache verification passed'

    Step 'Codex: pip-installing mcp_server + skills (so the host finds comfyui-chenxin-mcp-server)'
    $pythonExe = $null
    foreach ($candidate in @('py -3','python','python3')) {
        $parts = $candidate -split ' '
        $exe = $parts[0]
        if (Get-Command $exe -ErrorAction SilentlyContinue) {
            $pythonExe = $exe
            break
        }
    }
    if (-not $pythonExe) {
        $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path $bundled) { $pythonExe = $bundled }
    }
    if (-not $pythonExe) {
        Die 'python is required so the host can find comfyui-chenxin-mcp-server on PATH.'
    }
    $installPkgs = @(
        @{ Name = 'mcp_server';     Src = Join-Path $target 'mcp_server' },
        @{ Name = 'anima-prompt-v1'; Src = Join-Path $target 'skills\anima-prompt-v1' },
        @{ Name = 'minimax-h3-prompt'; Src = Join-Path $target 'skills\minimax-h3-prompt' },
        @{ Name = 'camera-image';    Src = Join-Path $target 'skills\camera-image' },
        @{ Name = 'camera-multiview';Src = Join-Path $target 'skills\camera-multiview' },
        @{ Name = 'camera-video';    Src = Join-Path $target 'skills\camera-video' }
    )
    foreach ($p in $installPkgs) {
        if (Test-Path (Join-Path $p.Src 'pyproject.toml')) {
            & $pythonExe -m pip install -e $p.Src --quiet | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Die "pip install -e $($p.Src) failed (rc=$LASTEXITCODE). Re-run without -e is fine; -e gives live source edits."
            }
            Step "pip-installed $($p.Name)"
        } else {
            Warn "skip $($p.Name) (no pyproject.toml at $($p.Src))"
        }
    }
}

Step 'DONE.'
Step 'next: restart the Codex desktop app (or open a new task) so it picks up the new MCP server.'
exit 0
