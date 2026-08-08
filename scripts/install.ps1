<#
.SYNOPSIS
  comfyui-chenxin one-shot installer for Windows.
.DESCRIPTION
  Registers the plugin + comfyui-mcp MCP server for Claude Code and Codex,
  installs the plugin into Codex's plugin cache, and verifies that the MCP
  server actually starts and exposes the tools the runtime needs.
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
    [string]$ClaudeHome = (Join-Path $env:USERPROFILE '.claude'),
    [string]$CodexHome = (Join-Path $env:USERPROFILE '.codex'),
    [ValidateSet('npx','local')] [string]$Mode = 'npx',
    [string]$PackageVersion = '0.41.0',
    [string]$ComfyUrl = 'http://127.0.0.1:8188',
    [string]$LocalClonePath = '',
    [switch]$SkipClaude,
    [switch]$SkipCodex,
    [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'

function Step($msg) { Write-Host "[install] $msg" }
function Warn($msg) { Write-Host "[install][warn] $msg" -ForegroundColor Yellow }
function Die($msg)  { Write-Host "[install][error] $msg" -ForegroundColor Red; exit 1 }

# ---------- 0. Resolve the MCP launch spec ----------

$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) { Die 'node is required on PATH.' }

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

try {
    $probe = [System.Net.WebRequest]::CreateHttp("$ComfyUrl/system_stats")
    $probe.Timeout = 3000
    $probe.GetResponse() | Out-Null
} catch { Warn "ComfyUI at $ComfyUrl did not respond (continuing; server will be verified separately)." }

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

# Resolve RepoRoot if not provided (handles wrappers that leave $PSScriptRoot empty).
if (-not $RepoRoot) {
    $scriptPath = $MyInvocation.MyCommand.Path
    if ($scriptPath) {
        $RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $scriptPath) '..')).Path
    } else {
        Die 'Cannot determine RepoRoot; pass -RepoRoot explicitly.'
    }
}

# ---------- 1. Claude Code ----------

if (-not $SkipClaude) {
    Step 'Claude Code: registering plugin + copying MCP config'
    if (-not (Test-Path $ClaudeHome)) { New-Item -ItemType Directory -Path $ClaudeHome -Force | Out-Null }
    $settingsPath = Join-Path $ClaudeHome 'settings.json'
    $settings = @{}
    if (Test-Path $settingsPath) {
        try {
            $raw = Get-Content $settingsPath -Raw -Encoding UTF8
            if (-not [string]::IsNullOrWhiteSpace($raw)) { $settings = $raw | ConvertFrom-Json }
        } catch { Warn "Could not parse $settingsPath; leaving alone."; $settings = @{} }
    }
    if (-not $settings.PSObject.Properties.Name.Contains('plugins')) {
        Add-Member -InputObject $settings -NotePropertyName 'plugins' -NotePropertyValue @() -Force
    }
    $pluginEntry = $settings.plugins | Where-Object { $_.name -eq 'comfyui-chenxin' } | Select-Object -First 1
    if (-not $pluginEntry) {
        $pluginEntry = [pscustomobject]@{
            name    = 'comfyui-chenxin'
            source  = 'github'
            repo    = 'cxin21/comfyui-chenxin'
            enabled = $true
        }
        $settings.plugins = @($settings.plugins + $pluginEntry)
    }
    $settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8
    Step "registered plugin in $settingsPath"

    $mcpSrc = Join-Path $RepoRoot 'mcp\mcp_servers.json'
    $mcpDstDir = Join-Path $ClaudeHome 'mcp_servers'
    $mcpDst = Join-Path $mcpDstDir 'comfyui-chenxin.json'
    if (Test-Path $mcpSrc) {
        if (-not (Test-Path $mcpDstDir)) { New-Item -ItemType Directory -Path $mcpDstDir -Force | Out-Null }
        Copy-Item -Path $mcpSrc -Destination $mcpDst -Force
        Step "copied $mcpSrc -> $mcpDst"
    } else { Warn "mcp/mcp_servers.json not found; skipping Claude MCP file copy." }
}

# ---------- 2. Codex: MCP + plugin cache ----------

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
    $envBlock = @(
        '[mcp_servers.comfyui-mcp.env]'
        'NPM_CONFIG_REGISTRY = "https://registry.npmjs.org"'
        'npm_config_registry = "https://registry.npmjs.org"'
    )
    Set-TomlBlock -Path $configPath -Header '[mcp_servers.comfyui-mcp]' -BlockLines $block
    Set-TomlBlock -Path $configPath -Header '[mcp_servers.comfyui-mcp.env]' -BlockLines $envBlock
    Step "wrote MCP block to $configPath"

    Step 'Codex: installing plugin into plugin cache'
    $pluginJsonPath = Join-Path $RepoRoot '.codex-plugin\plugin.json'
    if (-not (Test-Path $pluginJsonPath)) { Die "Missing $pluginJsonPath." }
    $plugin = Get-Content $pluginJsonPath -Raw | ConvertFrom-Json
    $version = [string]$plugin.version
    if (-not $version) { Die 'plugin.json has no version.' }
    $cacheRoot = Join-Path $CodexHome 'plugins\cache\personal\comfyui-chenxin'
    $stagingRoot = Join-Path $env:TEMP "comfyui-chenxin-install-$version"
    if (Test-Path $stagingRoot) { Remove-Item $stagingRoot -Recurse -Force }
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null

    $candidates = @(
        @{ Name = 'skills';         Src = Join-Path $RepoRoot 'skills' }
        @{ Name = '.codex-plugin';  Src = Join-Path $RepoRoot '.codex-plugin' }
        @{ Name = '.mcp.json';      Src = Join-Path $RepoRoot '.mcp.json' }
        @{ Name = 'LICENSE';        Src = Join-Path $RepoRoot 'LICENSE' }
        @{ Name = 'README.md';      Src = Join-Path $RepoRoot 'README.md' }
    )
    foreach ($c in $candidates) {
        if (Test-Path $c.Src) {
            Copy-Item -Path $c.Src -Destination (Join-Path $stagingRoot $c.Name) -Recurse -Force
        }
    }
    $stagedPlugin = Join-Path $stagingRoot '.codex-plugin\plugin.json'
    if (-not (Test-Path $stagedPlugin)) { Die "Staged plugin.json missing at $stagedPlugin." }
    $staged = Get-Content $stagedPlugin -Raw | ConvertFrom-Json
    if ([string]$staged.version -ne $version) { Die "Staged version [$($staged.version)] does not match directory." }
    if (-not (Test-Path (Join-Path $stagingRoot 'skills'))) { Die 'Staged skills/ missing.' }

    if (Test-Path $cacheRoot) {
        $existing = @(Get-ChildItem $cacheRoot -Directory -Force -ErrorAction SilentlyContinue)
        foreach ($dir in $existing) {
            $full = $dir.FullName
            if (-not $full.StartsWith($cacheRoot, [StringComparison]::OrdinalIgnoreCase)) {
                Die "Refusing to delete path outside cache root: $full"
            }
            Step "removing previous version directory $full"
            Remove-Item $full -Recurse -Force
        }
    }
    if (-not (Test-Path $cacheRoot)) { New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null }
    $target = Join-Path $cacheRoot $version
    Move-Item -Path $stagingRoot -Destination $target
    Step "installed plugin at $target"

    # --- Generate integrity manifest ---
    Step 'Generating integrity manifest...'
    $manifest = @{
        version      = $version
        generated_at = (Get-Date -Format 'o')
        files        = @()
    }
    $skillDirs = @(
        'skills\character-video-pipeline'
        'skills\prompt-forge'
    )
    foreach ($skillDir in $skillDirs) {
        $fullSkillDir = Join-Path $target $skillDir
        if (-not (Test-Path $fullSkillDir)) { continue }
        $skillFiles = Get-ChildItem $fullSkillDir -Recurse -File | Where-Object {
            $_.Extension -in '.py', '.ps1', '.md', '.json'
        }
        foreach ($sf in $skillFiles) {
            $rel = $sf.FullName.Substring($target.Length + 1).Replace('\', '/')
            $hash = (Get-FileHash $sf.FullName -Algorithm SHA256).Hash
            $manifest.files += @{ path = $rel; sha256 = $hash }
        }
    }
    $manifestPath = Join-Path $target 'manifest.json'
    $manifest | ConvertTo-Json -Depth 5 | Set-Content $manifestPath -Encoding UTF8
    Step "Manifest written: $($manifest.files.Count) files"

    # --- Verify critical files match between repo and cache ---
    $criticalFiles = @(
        'skills/character-video-pipeline/SKILL.md'
        'skills/character-video-pipeline/preflight-env.ps1'
        'skills/character-video-pipeline/runtime/preflight.py'
        'skills/character-video-pipeline/runtime/camera_config_helper.py'
        'skills/character-video-pipeline/runtime/attempt_state.py'
        'skills/prompt-forge/SKILL.md'
        'skills/prompt-forge/preflight-env.ps1'
        'skills/_mcp/pyproject.toml'
    )
    foreach ($rel in $criticalFiles) {
        $cacheFile = Join-Path $target ($rel -replace '/', '\')
        $repoFile  = Join-Path $RepoRoot ($rel -replace '/', '\')
        if ((Test-Path $cacheFile) -and (Test-Path $repoFile)) {
            $cacheHash = (Get-FileHash $cacheFile).Hash.Substring(0, 16)
            $repoHash  = (Get-FileHash $repoFile).Hash.Substring(0, 16)
            $match = if ($cacheHash -eq $repoHash) { 'MATCH' } else { 'DIFFER' }
            Step "$rel [$match]"
        }
    }
}

# ---------- 3. Verification ----------

if (-not $SkipVerify) {
    Step "Verifying MCP handshake (command=$command)"
    $pythonExe = $null
    $pythonArgs = @()
    foreach ($candidate in @('py -3','python','python3')) {
        $parts = $candidate -split ' '
        $exe = $parts[0]
        if (Get-Command $exe -ErrorAction SilentlyContinue) {
            $pythonExe = $exe
            $pythonArgs = $parts[1..($parts.Count-1)]
            break
        }
    }
    if (-not $pythonExe) {
        $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
        if (Test-Path $bundled) { $pythonExe = $bundled }
    }
    if (-not $pythonExe) {
        Warn 'No python on PATH and Codex bundled python missing. Skipping handshake verification.'
    } else {
        $verify = Join-Path $RepoRoot 'scripts\verify_mcp.py'
        $argsJson = (ConvertTo-Json -Compress -InputObject @($argList))
        $argsJson | & $pythonExe @pythonArgs $verify --command $command --timeout 180
        switch ($LASTEXITCODE) {
            0 { Step 'MCP handshake OK; all required tools present.' }
            1 { Die   'MCP handshake started but the server is missing required tools (see JSON above).' }
            default { Die 'MCP server failed to start or did not answer the handshake (see JSON above).' }
        }
    }
}

Step 'DONE.'
Step 'next: restart the Codex desktop app (or open a new task) so it picks up the new MCP server.'
exit 0
