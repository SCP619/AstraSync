<#
.SYNOPSIS
  Expose the AstraSync web UI and API (only those two) through a Cloudflare Tunnel.

.DESCRIPTION
  Reads the dev ports from traficom-integration/backend/dev_stack.local.env (defaults 8800/8801/5173)
  and writes a cloudflared ingress configuration that routes:
      https://<UiHostname>  -> http://127.0.0.1:<UI port>
      https://<ApiHostname> -> http://127.0.0.1:<API port>
      everything else       -> HTTP 404
  n8n (5678), Ollama (11434) and the development identity provider are never routed. The dev
  identity provider signs anyone in as a persona, so it must not be public: remote users need a
  real OIDC provider (ASTRASYNC_OIDC_ISSUER / VITE_OIDC_AUTHORITY), which this script does not set.

  Requires cloudflared (winget install --id Cloudflare.cloudflared) and, for -Mode Named, a
  Cloudflare account with a zone for the host names (cloudflared tunnel login).

.PARAMETER Mode
  Check  : print the plan and the configuration, change nothing (default).
  Named  : create or reuse a named tunnel, write the config, route DNS, run the tunnel.
  Quick  : a temporary trycloudflare.com URL for the UI only (static/demo use; the API stays local).

.EXAMPLE
  ./scripts/setup_cloudflare_tunnel.ps1 -Mode Check -UiHostname app.example.org -ApiHostname api.example.org
.EXAMPLE
  ./scripts/setup_cloudflare_tunnel.ps1 -Mode Named -UiHostname app.example.org -ApiHostname api.example.org
  Stop with Ctrl+C. Remove with: cloudflared tunnel delete astrasync
#>
[CmdletBinding()]
param(
  [ValidateSet("Check", "Named", "Quick")] [string] $Mode = "Check",
  [string] $TunnelName = "astrasync",
  [string] $UiHostname,
  [string] $ApiHostname
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$localEnv = Join-Path $root "traficom-integration/backend/dev_stack.local.env"

$ports = @{ ASTRASYNC_DEV_API_PORT = 8800; ASTRASYNC_DEV_IDP_PORT = 8801; ASTRASYNC_DEV_UI_PORT = 5173 }
if (Test-Path $localEnv) {
  foreach ($line in Get-Content $localEnv) {
    if ($line -match '^\s*(ASTRASYNC_DEV_(API|IDP|UI)_PORT)\s*=\s*(\d+)\s*$') { $ports[$Matches[1]] = [int]$Matches[3] }
  }
}
foreach ($name in $ports.Keys) {
  $fromEnv = [Environment]::GetEnvironmentVariable($name)
  if ($fromEnv) { $ports[$name] = [int]$fromEnv }
}
$api = $ports.ASTRASYNC_DEV_API_PORT; $ui = $ports.ASTRASYNC_DEV_UI_PORT; $idp = $ports.ASTRASYNC_DEV_IDP_PORT
$forbidden = @(5678, 11434, $idp)
if ($forbidden -contains $api -or $forbidden -contains $ui) { throw "Refusing: the UI or API port collides with n8n, Ollama or the dev identity provider." }

Write-Host "Ports: UI $ui, API $api (dev IdP $idp, n8n 5678 and Ollama 11434 are NOT exposed)."

function Test-Local([int] $port) {
  try { $c = New-Object Net.Sockets.TcpClient; $c.Connect("127.0.0.1", $port); $c.Close(); $true } catch { $false }
}

if ($Mode -eq "Quick") {
  if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { throw "cloudflared not found. winget install --id Cloudflare.cloudflared" }
  if (-not (Test-Local $ui)) { throw "Nothing listens on 127.0.0.1:$ui. Start the UI first." }
  Write-Warning "Quick tunnel: UI only. The API, sign-in and data stay on this PC, so remote viewers see the UI shell or the offline demo only."
  & cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$ui"
  exit $LASTEXITCODE
}

if (-not $UiHostname -or -not $ApiHostname) { throw "Give -UiHostname and -ApiHostname (host names in your Cloudflare zone)." }
$configDir = Join-Path $env:USERPROFILE ".cloudflared"
$configPath = Join-Path $configDir "astrasync-config.yml"
$config = @"
# Written by scripts/setup_cloudflare_tunnel.ps1. Only the UI and the API are routed.
tunnel: $TunnelName
ingress:
  - hostname: $UiHostname
    service: http://127.0.0.1:$ui
  - hostname: $ApiHostname
    service: http://127.0.0.1:$api
  - service: http_status:404
"@
Write-Host "`n$config`n"
Write-Host "Also required (not done by this script):"
Write-Host "  - ASTRASYNC_CORS_ORIGINS must include https://$UiHostname"
Write-Host "  - VITE_API_BASE_URL=https://$ApiHostname when building or serving the UI"
Write-Host "  - a real OIDC provider for remote sign-in (the dev IdP stays local)"

if ($Mode -eq "Check") { Write-Host "Check mode: nothing changed."; exit 0 }

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) { throw "cloudflared not found. winget install --id Cloudflare.cloudflared" }
foreach ($p in @($ui, $api)) { if (-not (Test-Local $p)) { throw "Nothing listens on 127.0.0.1:$p. Start the dev stack first." } }
$existing = (& cloudflared tunnel list --output json | ConvertFrom-Json) | Where-Object { $_.name -eq $TunnelName }
if (-not $existing) { & cloudflared tunnel create $TunnelName; if ($LASTEXITCODE) { throw "tunnel create failed" } }
New-Item -ItemType Directory -Force $configDir | Out-Null
Set-Content -Path $configPath -Value $config -Encoding utf8
& cloudflared tunnel route dns $TunnelName $UiHostname
& cloudflared tunnel route dns $TunnelName $ApiHostname
Write-Host "Running. Stop with Ctrl+C."
& cloudflared tunnel --config $configPath run $TunnelName
