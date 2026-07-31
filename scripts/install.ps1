# install.ps1 — one-shot installer for comfyui-chenxin on Windows.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts/install.ps1
#
# Does:
#   1. Registers the plugin in ~/.claude/settings.json under "plugins".
#      (Uses the same JSON-edit pattern as `Skill(update-config)` so we never
#      touch the env segment directly.)
#   2. Copies mcp/mcp_servers.json to ~/.claude/mcp_servers/comfyui-chenxin.json.
#   3. Prints /plugin install instructions for the user.
#
# Idempotent: re-running does not duplicate entries.

[CmdletBinding()]
param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ClaudeHome = ($env:USERPROFILE + "\.claude")
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "[install] $msg" }
function Write-Warn($msg) { Write-Host "[install][warn] $msg" -ForegroundColor Yellow }

# ----- 1. Register plugin in ~/.claude/settings.json ------------------------ #

$settingsPath = Join-Path $ClaudeHome "settings.json"
if (-not (Test-Path $ClaudeHome)) {
    Write-Warn "Claude home not found at $ClaudeHome — creating it."
    New-Item -ItemType Directory -Path $ClaudeHome -Force | Out-Null
}

$settings = @{}
if (Test-Path $settingsPath) {
    try {
        $raw = Get-Content $settingsPath -Raw -Encoding UTF8
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            $settings = $raw | ConvertFrom-Json
        }
    }
    catch {
        Write-Warn "Could not parse $settingsPath — leaving it alone. Edit it manually."
        $settings = @{}
    }
}

if (-not $settings.PSObject.Properties.Name.Contains("plugins")) {
    Add-Member -InputObject $settings -NotePropertyName "plugins" -NotePropertyValue @() -Force
}

$pluginEntry = $settings.plugins | Where-Object { $_.name -eq "comfyui-chenxin" } | Select-Object -First 1
if (-not $pluginEntry) {
    $pluginEntry = [pscustomobject]@{
        name = "comfyui-chenxin"
        source = "github"
        repo  = "cxin21/comfyui-chenxin"
        enabled = $true
    }
    $settings.plugins = @($settings.plugins + $pluginEntry)
}

# settings.json round-trip preserves everything else.
$settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8
Write-Step "registered plugin in $settingsPath"

# ----- 2. Copy MCP server config ------------------------------------------- #

$mcpSrc = Join-Path $RepoRoot "mcp\mcp_servers.json"
$mcpDstDir = Join-Path $ClaudeHome "mcp_servers"
$mcpDst = Join-Path $mcpDstDir "comfyui-chenxin.json"

if (-not (Test-Path $mcpSrc)) {
    Write-Warn "mcp/mcp_servers.json not found at $mcpSrc — skipping MCP install."
}
else {
    if (-not (Test-Path $mcpDstDir)) {
        New-Item -ItemType Directory -Path $mcpDstDir -Force | Out-Null
    }
    Copy-Item -Path $mcpSrc -Destination $mcpDst -Force
    Write-Step "copied $mcpSrc -> $mcpDst"
}

# ----- 3. Print next-action instructions ----------------------------------- #

Write-Step "next: in Claude Code, run"
Write-Host "         /plugin marketplace add chenxin/comfyui-chenxin"
Write-Host "         /plugin install comfyui@chenxin"
Write-Host "         /chenxin-init"
Write-Step "DONE."
exit 0