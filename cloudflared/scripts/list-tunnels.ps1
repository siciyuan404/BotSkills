<#
.SYNOPSIS
  List all Cloudflare Tunnels with detailed status information.
.DESCRIPTION
  Displays tunnel name, ID, status, credentials file info, and service health.
.EXAMPLE
  .\list-tunnels.ps1
#>

Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  Cloudflare Tunnels Status" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# Check authentication
$certPath = "$env:USERPROFILE\.cloudflared\cert.pem"
if (-not (Test-Path $certPath)) {
  Write-Host "`n  Not authenticated. Run 'cloudflared tunnel login' first." -ForegroundColor Red
  exit 1
}

$raw = cloudflared tunnel list 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "`n  ERROR: $raw" -ForegroundColor Red
  exit 1
}

$lines = $raw | Where-Object { $_ -match '^[a-f0-9\-]{36}' }
$tunnels = @()

foreach ($line in $lines) {
  if ($line -match '^([a-f0-9\-]{36})\s+(\S+)\s+(\S+)\s+(\d{4}-\d{2}-\d{2}.*)') {
    $tunnels += [PSCustomObject]@{
      ID     = $matches[1]
      Name   = $matches[2]
      Status = $matches[3]
      Date   = $matches[4]
    }
  }
}

Write-Host "`nFound $($tunnels.Count) tunnel(s):" -ForegroundColor Yellow
Write-Host ""

foreach ($t in $tunnels) {
  $statusColor = if ($t.Status -eq 'active') { 'Green' } else { 'Gray' }
  Write-Host "  [$($t.Status)] $($t.Name)" -ForegroundColor $statusColor
  Write-Host "    ID:     $($t.ID)"
  Write-Host "    Since:  $($t.Date)"

  # Check if credentials file exists
  $credFile = "$env:USERPROFILE\.cloudflared\$($t.ID).json"
  if (Test-Path $credFile) {
    Write-Host "    Config: present" -ForegroundColor Green
  } else {
    Write-Host "    Config: missing credentials file" -ForegroundColor Red
  }

  Write-Host ""
}

# Check service status
$svc = sc.exe query cloudflared 2>$null
if ($LASTEXITCODE -eq 0) {
  $state = if ($svc -match 'STATE\s+:\s+(\S+)') { $matches[1] } else { "unknown" }
  $stateColor = if ($state -eq '4') { 'Green' } else { 'Yellow' }
  Write-Host "Windows Service: " -NoNewline
  Write-Host "$state" -ForegroundColor $stateColor
} else {
  Write-Host "Windows Service: not installed" -ForegroundColor Gray
}

Write-Host "`n==============================================" -ForegroundColor Cyan
