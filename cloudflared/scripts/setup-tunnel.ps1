<#
.SYNOPSIS
  Interactive Cloudflare Tunnel setup wizard.
.DESCRIPTION
  Guides the user through authentication, tunnel creation, DNS routing, and config file generation.
.EXAMPLE
  .\setup-tunnel.ps1
#>

function Write-Step {
  param([string]$Message, [string]$Color = "Cyan")
  Write-Host "`n==> $Message" -ForegroundColor $Color
}

function Confirm-Action {
  param([string]$Message)
  $answer = Read-Host "`n$Message (y/n)"
  return $answer -eq 'y' -or $answer -eq 'yes'
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "  Cloudflare Tunnel Setup Wizard" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Step 1: Check authentication
Write-Step "Step 1: Checking authentication"
$certPath = "$env:USERPROFILE\.cloudflared\cert.pem"
if (-not (Test-Path $certPath)) {
  Write-Host "  No certificate found. Opening browser for login..." -ForegroundColor Yellow
  cloudflared tunnel login
  if (-not (Test-Path $certPath)) {
    Write-Host "  ERROR: Login failed. Run 'cloudflared tunnel login' manually." -ForegroundColor Red
    exit 1
  }
  Write-Host "  Login successful!" -ForegroundColor Green
} else {
  Write-Host "  Already authenticated (cert.pem found)." -ForegroundColor Green
}

# Step 2: Tunnel name
Write-Step "Step 2: Setting up tunnel"
$tunnelName = Read-Host "  Enter a name for the tunnel (e.g., my-app-tunnel)"
if (-not $tunnelName) {
  Write-Host "  Tunnel name cannot be empty." -ForegroundColor Red
  exit 1
}

# Check if tunnel already exists
$existing = cloudflared tunnel list | Select-String -Pattern "\s$tunnelName\s"
if ($existing) {
  Write-Host "  Tunnel '$tunnelName' already exists." -ForegroundColor Yellow
  if (-not (Confirm-Action "  Use existing tunnel?")) {
    exit 0
  }
} else {
  Write-Host "  Creating tunnel '$tunnelName'..."
  cloudflared tunnel create $tunnelName
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Failed to create tunnel." -ForegroundColor Red
    exit 1
  }
  Write-Host "  Tunnel created successfully!" -ForegroundColor Green
}

# Get tunnel ID
$tunnelInfo = cloudflared tunnel list | Select-String -Pattern "\s$tunnelName\s"
$tunnelId = if ($tunnelInfo -match '([a-f0-9\-]{36})') { $matches[1] } else { "" }

# Step 3: DNS routing
Write-Step "Step 3: DNS routing"
$domain = Read-Host "  Enter the domain to route (e.g., app.yourdomain.com)"
if ($domain) {
  if (Confirm-Action "  Route '$domain' to tunnel '$tunnelName'?") {
    cloudflared tunnel route dns $tunnelName $domain
    if ($LASTEXITCODE -ne 0) {
      Write-Host "  WARNING: DNS routing may have failed. You can do this later." -ForegroundColor Yellow
    } else {
      Write-Host "  DNS route created: $domain -> $tunnelName" -ForegroundColor Green
    }
  }
}

# Step 4: Local service
Write-Step "Step 4: Configuring local service"
$localService = Read-Host "  Enter local service URL (e.g., http://localhost:3000)"

# Step 5: Generate config
Write-Step "Step 5: Generating config.yml"

$credFile = Get-ChildItem "$env:USERPROFILE\.cloudflared" -Filter "*.json" | Where-Object { $_.Name -ne "cert.pem" } | Select-Object -First 1

if (-not $credFile -and $tunnelId) {
  $credFile = Get-ChildItem "$env:USERPROFILE\.cloudflared" -Filter "$tunnelId.json" -ErrorAction SilentlyContinue
}

$configLines = @(
  "tunnel: $tunnelName",
  "credentials-file: $env:USERPROFILE\.cloudflared\$($credFile.Name)",
  "",
  "logfile: $env:USERPROFILE\.cloudflared\tunnel.log",
  "loglevel: info",
  "",
  "ingress:"
)

if ($domain -and $localService) {
  $configLines += "  - hostname: $domain"
  $configLines += "    service: $localService"
} elseif ($localService) {
  $configLines += "  - hostname: $domain"  # Let user fix domain later
  $configLines += "    service: $localService"
}

$configLines += "  - service: http_status:404"

$configPath = "$env:USERPROFILE\.cloudflared\config.yml"
$configLines | Set-Content -Path $configPath -Encoding UTF8
Write-Host "  Config written to: $configPath" -ForegroundColor Green

Write-Host "`nConfig content:" -ForegroundColor Cyan
Get-Content $configPath | ForEach-Object { Write-Host "  $_" }

# Step 6: Run or install
Write-Step "Step 6: (Optional) Start tunnel"
$choice = Read-Host "  [F]oreground test, [I]nstall as service, [S]kip (f/i/s)"
switch ($choice.ToLower()) {
  'f' {
    Write-Host "  Starting tunnel in foreground (Ctrl+C to stop)..." -ForegroundColor Green
    cloudflared tunnel run $tunnelName
  }
  'i' {
    Write-Host "  Installing service..." -ForegroundColor Green
    cloudflared service install
    if ($LASTEXITCODE -eq 0) {
      net start cloudflared
      Write-Host "  Service installed and started!" -ForegroundColor Green
    }
  }
  default {
    Write-Host "  Skipped. Run 'cloudflared tunnel run $tunnelName' to test." -ForegroundColor Yellow
  }
}

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "  Tunnel: $tunnelName"
Write-Host "  Config: $configPath"
Write-Host "========================================" -ForegroundColor Green
