---
name: cloudflared
description: Complete Cloudflare Tunnel (cloudflared) management for exposing local services to the internet. Use this skill whenever the user mentions Cloudflare tunnels, cloudflared, exposing local services, making localhost accessible from the internet, tunnel setup, ingress configuration, Cloudflare Access, `cloudflared tunnel` commands, or anything related to connecting local servers through Cloudflare's network. Also triggers when the user wants to secure local services, set up authentication for internal tools, or create persistent tunnels to Cloudflare. This is the go-to skill for all cloudflared operations — tunnel creation, DNS routing, ingress rules, running tunnels as services, and managing Access policies.
---

# Cloudflare Tunnel (cloudflared) Control

Complete cloudflared management for exposing local services through Cloudflare Tunnel.

**Platform:** Windows (PowerShell)

## Overview

Cloudflare Tunnel creates a secure, encrypted connection from your local services to Cloudflare's edge network, without opening any inbound firewall ports. This skill covers the full lifecycle: authentication, tunnel creation, configuration, DNS routing, Windows service management, and troubleshooting.

## Quick Start

### Authentication

```powershell
cloudflared tunnel login
# Certificate saved to: ~\.cloudflared\cert.pem
```

### Existing Tunnel → Add a Port

The most common task: you have a tunnel, you want to expose a new local service.

```powershell
# 1. Route DNS (if not already done)
cloudflared tunnel route dns <tunnel-name> <hostname>

# 2. Add ingress rule to config.yml, then restart
scripts\add-port.ps1 -TunnelName <tunnel-name> -Hostname <hostname> -LocalPort <port>
```

See `scripts\add-port.ps1` — one command does DNS routing, config update, and service restart.

### New Tunnel Setup (Full)

```powershell
# 1. Login
cloudflared tunnel login

# 2. Create tunnel
cloudflared tunnel create my-tunnel

# 3. Route DNS
cloudflared tunnel route dns my-tunnel app.yourdomain.com

# 4. Write config.yml, then install + start service
scripts\setup-tunnel.ps1
```

## Tunnel Management

### List Tunnels

```powershell
cloudflared tunnel list
```

Shows tunnel name, ID, status, and active connections.

### Create Tunnel

```powershell
cloudflared tunnel create <tunnel-name>
```

Generates a UUID-based credentials JSON file at `~\.cloudflared\<tunnel-id>.json`.

### Recover Missing Credentials

If the credentials `.json` is lost but the tunnel still exists in Cloudflare:

```powershell
# Get the tunnel token
$token = cloudflared tunnel token <tunnel-name>

# Decode it to JSON
$bytes = [Convert]::FromBase64String($token)
$cred = [System.Text.Encoding]::UTF8.GetString($bytes) | ConvertFrom-Json

# Write WITHOUT BOM — Set-Content with -Encoding UTF8 adds BOM and breaks cloudflared!
$json = $cred | ConvertTo-Json
[System.IO.File]::WriteAllText("$env:USERPROFILE\.cloudflared\$($cred.TunnelID).json", $json)
```

**CRITICAL:** Never use `Set-Content -Encoding UTF8` for credentials JSON. PowerShell adds a BOM (Byte Order Mark, `ï` bytes) at the start that cloudflared chokes on. Use `[System.IO.File]::WriteAllText()` instead.

### Delete Tunnel

```powershell
cloudflared tunnel delete <tunnel-name>
cloudflared tunnel delete -f <tunnel-name>  # Force delete even if running
```

## Configuration (config.yml)

Default location: `~\.cloudflared\config.yml`

### Full Example

```yaml
tunnel: my-tunnel
credentials-file: C:\Users\MyUser\.cloudflared\<tunnel-id>.json

logfile: C:\Users\MyUser\.cloudflared\tunnel.log
loglevel: info

ingress:
  - hostname: app.yourdomain.com
    service: http://localhost:3000
  - hostname: api.yourdomain.com
    service: http://localhost:8080
  - service: http_status:404  # MUST be last
```

### Validate Config

```powershell
cloudflared tunnel --config ~\.cloudflared\config.yml ingress validate
```

## DNS Configuration

```powershell
# Route a domain to the tunnel
cloudflared tunnel route dns <tunnel-name> <hostname>

# It's safe to re-run — if already routed, it says so and does nothing:
# "code.6200052.xyz is already configured to route to your tunnel"
```

## Windows Service (Production)

**⚠ `cloudflared service install` creates a generic agent that does NOT automatically connect to your tunnel.** Always use the custom service method below.

### Install Service (Correct Way)

```powershell
# Create service with explicit config path
$binPath = "cloudflared.exe tunnel --config $env:USERPROFILE\.cloudflared\config.yml run"
New-Service -Name cloudflared -BinaryPathName $binPath -DisplayName "Cloudflare Tunnel" -StartupType Automatic

# Start
Start-Service cloudflared

# Or one-liner:
sc.exe create cloudflared binPath= "cloudflared.exe tunnel --config C:\Users\MyUser\.cloudflared\config.yml run" start= auto displayname= "Cloudflare Tunnel"
```

**Why this works:** `--config` must come BEFORE the `run` subcommand. `cloudflared tunnel run --config path` fails with "flag provided but not defined". The correct order is `cloudflared tunnel --config path run`.

### Service Management

```powershell
Start-Service cloudflared          # Start
Stop-Service cloudflared           # Stop
Restart-Service cloudflared        # Restart
sc.exe query cloudflared           # Check status
```

### Force Restart (When Stuck)

```powershell
taskkill /F /IM cloudflared.exe    # Force kill all cloudflared processes
Start-Sleep 5
# Wait for service deletion to propagate if re-creating
sc.exe query cloudflared  # Verify service is gone
Start-Service cloudflared           # Restart
```

### View Service Config

```powershell
sc.exe qc cloudflared
# Verify BINARY_PATH_NAME has correct --config before run
```

### Remove Service

```powershell
Stop-Service cloudflared
sc.exe delete cloudflared
```

## Scripts

### `scripts/add-port.ps1`
**Most frequently used.** One command to add a new service to an existing tunnel:

```powershell
.\scripts\add-port.ps1 -TunnelName code-6200052 -Hostname api.6200052.xyz -LocalPort 8080
```

This does: DNS route → config.yml ingress update → validate → service restart.

### `scripts/setup-tunnel.ps1`
Interactive wizard for first-time tunnel setup.

### `scripts/list-tunnels.ps1`
Tunnel status overview.

### `scripts/manage-service.ps1`
Service lifecycle manager.

## Troubleshooting

### Tunnel Won't Connect

```powershell
# Check service is running
sc.exe query cloudflared

# Check tunnel connections
cloudflared tunnel list

# Validate config
cloudflared tunnel --config ~\.cloudflared\config.yml ingress validate

# Check logs
Get-Content "$env:USERPROFILE\.cloudflared\tunnel.log" -Tail 50

# Test local service is running
Test-NetConnection -ComputerName localhost -Port 3080
```

### Common Issues

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `Cannot determine default origin certificate path` | Not logged in | `cloudflared tunnel login` |
| `invalid JSON: invalid character 'ï'` | BOM in credentials file | Rewrite with `[System.IO.File]::WriteAllText()` (not `Set-Content`) |
| `failed to dial to edge with quic: timeout` | UDP/QUIC blocked by firewall or proxy | Auto-fallback to HTTP/2 — check precheck output |
| `cloudflared service install` creates agent that doesn't connect | Generic agent doesn't read config.yml | Use `New-Service` with `tunnel --config path run` |
| `flag provided but not defined: -config` | `--config` placed after `run` | Correct: `cloudflared tunnel --config path run` |
| `ERR 1033` | Argo Smart Routing / edge connection | Check tunnel connections in dashboard |
| `530` / `error code: 1033` via browser | No active tunnel connection | Check service and tunnel connections |
| `connection timeout` | Local service not running | Start your local server on the expected port |

### Logs

```powershell
Get-Content "$env:USERPROFILE\.cloudflared\tunnel.log" -Tail 50

# Foreground test with verbose output
cloudflared tunnel --config ~\.cloudflared\config.yml run
```

### Pre-checks (Connectivity Diagnostics)

When you run `cloudflared tunnel --config path run`, it automatically runs connectivity pre-checks:

```
DNS Resolution    → PASS  (DNS resolves correctly)
UDP Connectivity  → FAIL  (QUIC blocked — common on restrictive networks)
TCP Connectivity  → PASS  (HTTP/2 fallback works)
Cloudflare API    → PASS  (API reachable)
```

Cloudflared auto-falls back to HTTP/2 if QUIC fails. This is normal.

## Common Patterns

### Pattern 1: Add Port to Existing Tunnel

```powershell
# The fastest way — uses add-port.ps1
.\scripts\add-port.ps1 -TunnelName my-tunnel -Hostname app.mydomain.com -LocalPort 4200

# Manual equivalent:
# 1. Route DNS
cloudflared tunnel route dns my-tunnel app.mydomain.com
# 2. Edit config.yml — add ingress rule before the 404 catch-all
# 3. Restart service
taskkill /F /IM cloudflared.exe
Start-Service cloudflared
```

### Pattern 2: Full Production Setup

```powershell
# 1. Login
cloudflared tunnel login

# 2. Create tunnel
cloudflared tunnel create my-app-tunnel

# 3. Route DNS
cloudflared tunnel route dns my-app-tunnel app.yourdomain.com

# 4. Write config.yml with ingress rules

# 5. Install service (use New-Service, NOT cloudflared service install)
$binPath = "cloudflared.exe tunnel --config $env:USERPROFILE\.cloudflared\config.yml run"
New-Service -Name cloudflared -BinaryPathName $binPath -DisplayName "Cloudflare Tunnel" -StartupType Automatic

# 6. Start
Start-Service cloudflared
```

### Pattern 3: Multiple Services (One Tunnel)

```yaml
# config.yml — single tunnel routes multiple domains
tunnel: main-tunnel
credentials-file: C:\Users\MyUser\.cloudflared\main-tunnel.json

ingress:
  - hostname: app.yourdomain.com
    service: http://localhost:3000
  - hostname: api.yourdomain.com
    service: http://localhost:8080
  - hostname: admin.yourdomain.com
    service: http://localhost:9000
  - service: http_status:404
```

### Pattern 4: RDP / SSH / TCP Through Tunnel

```yaml
ingress:
  - hostname: rdp.yourdomain.com
    service: tcp://localhost:3389
  - hostname: ssh.yourdomain.com
    service: ssh://localhost:22
  - service: http_status:404
```

## Notes

- **CRITICAL: `--config` must be BEFORE `run`**: `cloudflared tunnel --config path run` ✓, `cloudflared tunnel run --config path` ✗
- **CRITICAL: Don't use `cloudflared service install`** — it creates a generic agent that doesn't connect to your tunnel. Use `New-Service` with explicit `tunnel --config path run` command.
- **CRITICAL: No BOM in credentials JSON** — Write with `[System.IO.File]::WriteAllText()`, not `Set-Content`
- Each tunnel gets a UUID-based credentials JSON file — keep it safe
- The catch-all ingress rule (`http_status:404`) is required at the end of ingress
- QUIC/UDP may be blocked by firewall — cloudflared auto-falls back to HTTP/2
- Ingress hostnames are matched exactly — `app.domain.com` ≠ `App.domain.com`
- `cloudflared tunnel route dns` is idempotent — safe to re-run
- DNS routing and ingress rules are separate: DNS points the hostname to the tunnel, ingress routes it to a local service
- When stuck, `taskkill /F /IM cloudflared.exe` is the nuclear option — always works
