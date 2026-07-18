<#
.SYNOPSIS
  Manage the cloudflared Windows service.
.DESCRIPTION
  Install (using New-Service with correct command order), start, stop, restart, remove, check status.
  IMPORTANT: cloudflared service install creates a generic agent that does NOT run your tunnel.
  Use this script instead — it creates a service that explicitly runs `tunnel --config path run`.
.PARAMETER Action
  install, start, stop, restart, remove, status
.PARAMETER ConfigPath
  Path to config.yml (default: ~\.cloudflared\config.yml)
.EXAMPLE
  .\manage-service.ps1 -Action install
  .\manage-service.ps1 -Action status
#>

param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('install', 'start', 'stop', 'restart', 'remove', 'status')]
  [string]$Action,
  [string]$ConfigPath = "$env:USERPROFILE\.cloudflared\config.yml"
)

$serviceName = "cloudflared"

function Write-OK { Write-Host "✅ $($args[0])" -ForegroundColor Green }
function Write-Info { Write-Host "ℹ $($args[0])" -ForegroundColor Cyan }

switch ($Action) {
  'install' {
    Write-Info "创建 cloudflared 服务..."
    # CRITICAL: --config must be BEFORE run, NOT after
    $binPath = "cloudflared.exe tunnel --config $ConfigPath run"

    # Remove existing service first if any
    sc.exe delete $serviceName 2>$null
    Start-Sleep 3

    $svc = New-Service -Name $serviceName -BinaryPathName $binPath -DisplayName "Cloudflare Tunnel" -StartupType Automatic 2>&1
    if ($?) {
      Write-OK "服务已创建"

      # Switch to delayed-auto to prevent boot-time DNS failure
      sc.exe config $serviceName start= delayed-auto 2>$null
      if ($?) { Write-Info "启动类型: delayed-auto (开机延迟启动)" }

      Start-Service $serviceName 2>$null
      if ($?) { Write-OK "服务已启动" }
    } else {
      Write-Host "  $svc" -ForegroundColor Red
    }
  }

  'start' {
    Write-Info "启动服务..."
    Start-Service $serviceName 2>$null
    if ($?) { Write-OK "已启动" } else { Write-Host "  启动失败或已运行" -ForegroundColor Yellow }
  }

  'stop' {
    Write-Info "停止服务..."
    Stop-Service $serviceName -Force 2>$null
    if ($?) { Write-OK "已停止" } else {
      Write-Host "  尝试强制停止..." -ForegroundColor Yellow
      taskkill /F /IM cloudflared.exe 2>$null
      Write-OK "已强制停止"
    }
  }

  'restart' {
    Write-Info "重启服务..."
    taskkill /F /IM cloudflared.exe 2>$null
    Start-Sleep 3
    Start-Service $serviceName 2>$null
    if ($?) { Write-OK "已重启" } else { Write-Host "  重启失败" -ForegroundColor Red }
  }

  'remove' {
    Write-Info "删除服务..."
    taskkill /F /IM cloudflared.exe 2>$null
    Start-Sleep 2
    sc.exe delete $serviceName 2>$null
    if ($?) { Write-OK "已删除" }
  }

  'status' {
    $svc = sc.exe query $serviceName 2>$null
    if ($LASTEXITCODE -eq 0) {
      if ($svc -match 'STATE\s+:\s+(\d+)') {
        $stateCode = $matches[1]
        $stateText = switch ($stateCode) {
          '1' { 'STOPPED' }; '2' { 'START_PENDING' }; '3' { 'STOP_PENDING' }
          '4' { 'RUNNING' }; '5' { 'CONTINUE_PENDING' }; '6' { 'PAUSE_PENDING' }; '7' { 'PAUSED' }
        }
        $color = switch ($stateCode) { '4' { 'Green' } '1' { 'Gray' } default { 'Yellow' } }
        Write-Host "cloudflared: $stateText" -ForegroundColor $color

        if ($svc -match 'PID\s+:\s+(\d+)') {
          Write-Host "PID: $($matches[1])"
        }
      }

      $qc = sc.exe qc $serviceName 2>$null
      if ($qc -match 'BINARY_PATH_NAME\s+:\s+(.+)') {
        Write-Host "命令: $($matches[1].Trim())" -ForegroundColor Gray
      }
    } else {
      Write-Host "cloudflared: 未安装" -ForegroundColor Gray
    }
  }
}
