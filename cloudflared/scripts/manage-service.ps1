<#
.SYNOPSIS
  Manage the cloudflared Windows service.
.DESCRIPTION
  Install, start, stop, restart, remove, or check status of the cloudflared service.
.PARAMETER Action
  Action to perform: install, start, stop, restart, remove, status
.EXAMPLE
  .\manage-service.ps1 -Action status
  .\manage-service.ps1 -Action restart
#>

param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('install', 'start', 'stop', 'restart', 'remove', 'status')]
  [string]$Action
)

$serviceName = "cloudflared"

switch ($Action) {
  'install' {
    Write-Host "Installing cloudflared service..." -ForegroundColor Cyan
    cloudflared service install
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Service installed. Starting..." -ForegroundColor Green
      net start $serviceName
    } else {
      Write-Host "Installation failed." -ForegroundColor Red
    }
  }

  'start' {
    Write-Host "Starting cloudflared service..." -ForegroundColor Cyan
    net start $serviceName 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Service started." -ForegroundColor Green
    } else {
      Write-Host "Failed to start. Is it already running?" -ForegroundColor Yellow
    }
  }

  'stop' {
    Write-Host "Stopping cloudflared service..." -ForegroundColor Cyan
    net stop $serviceName 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Service stopped." -ForegroundColor Green
    } else {
      Write-Host "Failed to stop. Is it running?" -ForegroundColor Yellow
    }
  }

  'restart' {
    Write-Host "Restarting cloudflared service..." -ForegroundColor Cyan
    net stop $serviceName 2>$null
    Start-Sleep -Seconds 2
    net start $serviceName 2>$null
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Service restarted." -ForegroundColor Green
    } else {
      Write-Host "Failed to restart." -ForegroundColor Red
    }
  }

  'remove' {
    Write-Host "Removing cloudflared service..." -ForegroundColor Cyan
    net stop $serviceName 2>$null
    Start-Sleep -Seconds 2
    cloudflared service uninstall
    if ($LASTEXITCODE -eq 0) {
      Write-Host "Service removed." -ForegroundColor Green
    } else {
      Write-Host "Failed to remove." -ForegroundColor Red
    }
  }

  'status' {
    $svc = sc.exe query $serviceName 2>$null
    if ($LASTEXITCODE -eq 0) {
      if ($svc -match 'STATE\s+:\s+(\S+)\s+(\S+)') {
        $stateCode = $matches[1]
        $stateText = switch ($stateCode) {
          '1' { 'STOPPED' }
          '2' { 'START_PENDING' }
          '3' { 'STOP_PENDING' }
          '4' { 'RUNNING' }
          '5' { 'CONTINUE_PENDING' }
          '6' { 'PAUSE_PENDING' }
          '7' { 'PAUSED' }
          default { "UNKNOWN ($stateCode)" }
        }
        $color = if ($stateCode -eq '4') { 'Green' } elseif ($stateCode -eq '1') { 'Gray' } else { 'Yellow' }
        Write-Host "cloudflared: $stateText" -ForegroundColor $color

        if ($svc -match 'PID\s+:\s+(\d+)') {
          Write-Host "PID: $($matches[1])"
        }
      }
    } else {
      Write-Host "cloudflared: not installed" -ForegroundColor Gray
    }
  }
}
