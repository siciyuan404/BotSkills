<#
.SYNOPSIS
  Add a local port to an existing Cloudflare Tunnel — one command.
.DESCRIPTION
  Routes DNS, adds ingress rule to config.yml, validates, and restarts the service.
  The most common cloudflared operation: "I have a tunnel, I want to expose another port."
.PARAMETER TunnelName
  Name of the existing tunnel (e.g., "code-6200052")
.PARAMETER Hostname
  Domain to route (e.g., "api.6200052.xyz")
.PARAMETER LocalPort
  Local port to expose (e.g., 3080)
.PARAMETER LocalHost
  Local host address (default: localhost)
.PARAMETER Protocol
  Protocol: http, https, tcp, ssh (default: http)
.EXAMPLE
  .\add-port.ps1 -TunnelName code-6200052 -Hostname api.6200052.xyz -LocalPort 8080
  .\add-port.ps1 -TunnelName main-tunnel -Hostname rdp.mydomain.com -LocalPort 3389 -Protocol tcp
#>

param(
  [Parameter(Mandatory = $true)] [string]$TunnelName,
  [Parameter(Mandatory = $true)] [string]$Hostname,
  [Parameter(Mandatory = $true)] [int]$LocalPort,
  [string]$LocalHost = "localhost",
  [ValidateSet("http", "https", "tcp", "ssh")]
  [string]$Protocol = "http"
)

$configPath = "$env:USERPROFILE\.cloudflared\config.yml"
$ErrorActionPreference = "Stop"

function Write-OK { Write-Host "  ✅ $($args[0])" -ForegroundColor Green }
function Write-Warn { Write-Host "  ⚠ $($args[0])" -ForegroundColor Yellow }
function Write-Step { Write-Host "`n==> $($args[0])" -ForegroundColor Cyan }

# --- Step 1: Verify tunnel exists ---
Write-Step "Step 1: 验证隧道"
$tunnelList = cloudflared tunnel list 2>&1 | Select-String -Pattern "\s$TunnelName\s"
if (-not $tunnelList) {
  Write-Warn "隧道 '$TunnelName' 不存在。正在创建..."
  cloudflared tunnel create $TunnelName
}
Write-OK "隧道 '$TunnelName' 已存在"

# --- Step 2: Route DNS ---
Write-Step "Step 2: DNS 路由"
cloudflared tunnel route dns $TunnelName $Hostname 2>&1 | ForEach-Object {
  if ($_ -match "already configured") {
    Write-OK "DNS 已路由: $Hostname → $TunnelName"
  } elseif ($_ -match "has been created" -or $_ -match "success") {
    Write-OK "DNS 路由创建成功: $Hostname → $TunnelName"
  } else {
    Write-Host "  $_"
  }
}

# --- Step 3: Build service URL ---
$serviceUrl = switch ($Protocol) {
  "http"  { "http://${LocalHost}:${LocalPort}" }
  "https" { "https://${LocalHost}:${LocalPort}" }
  "tcp"   { "tcp://${LocalHost}:${LocalPort}" }
  "ssh"   { "ssh://${LocalHost}:${LocalPort}" }
}

# --- Step 4: Update config.yml ---
Write-Step "Step 3: 更新 config.yml"
if (-not (Test-Path $configPath)) {
  Write-Warn "config.yml 不存在，创建默认配置..."
  # Need tunnel ID for credentials path
  $tunnelId = if ($tunnelList -match '([a-f0-9\-]{36})') { $matches[1] } else { "" }
  @"
tunnel: $TunnelName
credentials-file: $env:USERPROFILE\.cloudflared\$tunnelId.json

logfile: $env:USERPROFILE\.cloudflared\tunnel.log
loglevel: info

ingress:
  - hostname: $Hostname
    service: $serviceUrl
  - service: http_status:404
"@ | Set-Content $configPath -Encoding UTF8
  Write-OK "config.yml 已创建"
} else {
  # Read existing config, add new ingress rule before the 404 catch-all
  $config = Get-Content $configPath -Raw

  # Check if hostname already exists
  if ($config -match "hostname:\s*$Hostname") {
    Write-OK "Ingress 规则已存在: $Hostname"
  } else {
    # Insert new ingress rule before the 404 catch-all line
    $newIngress = "  - hostname: $Hostname`n    service: $serviceUrl"
    $config = $config -replace '(  - service: http_status:404)', "$newIngress`n  - service: http_status:404"
    Set-Content $configPath $config -Encoding UTF8
    Write-OK "Ingress 规则已添加: $Hostname → $serviceUrl"
  }
}

# --- Step 5: Validate config ---
Write-Step "Step 4: 验证配置"
$validation = cloudflared tunnel --config $configPath ingress validate 2>&1
if ($validation -match "OK") {
  Write-OK "配置验证通过"
} else {
  Write-Warn "配置验证失败: $validation"
  exit 1
}

# --- Step 6: Restart service ---
Write-Step "Step 5: 重启服务"
$svc = sc.exe query cloudflared 2>$null
if ($LASTEXITCODE -eq 0) {
  Write-Host "  正在重启服务..."
  taskkill /F /IM cloudflared.exe 2>$null
  Start-Sleep 3
  Start-Service cloudflared -ErrorAction SilentlyContinue
  if ($?) {
    Write-OK "服务已重启"
  } else {
    Write-Warn "服务重启失败，尝试手动启动: Start-Service cloudflared"
  }
} else {
  Write-Warn "服务未安装。安装并启动..."
  $binPath = "cloudflared.exe tunnel --config $configPath run"
  sc.exe create cloudflared binPath= $binPath start= auto displayname= "Cloudflare Tunnel" 2>$null
  Start-Service cloudflared 2>$null
  if ($?) { Write-OK "服务已安装并启动" }
}

# --- Step 7: Wait and verify ---
Write-Step "Step 6: 验证连接"
Start-Sleep 10
$finalList = cloudflared tunnel list | Select-String -Pattern "\s$TunnelName\s"
Write-Host "  $($finalList.Trim())"
if ($finalList -match '([a-z]{3}\d{2}(?:, )?)+') {
  Write-OK "隧道已连接！https://$Hostname 将路由到 $serviceUrl"
} else {
  Write-Warn "隧道尚未连接，等待几秒后检查..."
  Write-Host "  检查服务状态: sc query cloudflared"
  Write-Host "  检查隧道日志: Get-Content $env:USERPROFILE\.cloudflared\tunnel.log -Tail 20"
}

Write-Host "`n====================================" -ForegroundColor Green
Write-Host "  完成！" -ForegroundColor Green
Write-Host "  URL:  https://$Hostname" -ForegroundColor Green
Write-Host "  -> $serviceUrl" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
