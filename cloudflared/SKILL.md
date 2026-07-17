---
name: cloudflared
description: Complete Cloudflare Tunnel (cloudflared) management for exposing local services to the internet. Use this skill whenever the user mentions Cloudflare tunnels, cloudflared, exposing local services, making localhost accessible from the internet, tunnel setup, ingress configuration, Cloudflare Access, `cloudflared tunnel` commands, or anything related to connecting local servers through Cloudflare's network. Also triggers when the user wants to secure local services, set up authentication for internal tools, or create persistent tunnels to Cloudflare. This is the go-to skill for all cloudflared operations — tunnel creation, DNS routing, ingress rules, running tunnels as services, and managing Access policies.
---

# Cloudflare Tunnel (cloudflared) Control

Complete cloudflared management for exposing local services through Cloudflare Tunnel.

## Overview

Cloudflare Tunnel creates a secure, encrypted connection from your local services to Cloudflare's edge network, without opening any inbound firewall ports. This skill covers the full lifecycle: authentication, tunnel creation, configuration, DNS routing, service management, and Access policies.

**Platform:** Windows (PowerShell)

## Quick Start

### Authentication

```powershell
# Login to Cloudflare (opens browser for OAuth)
cloudflared tunnel login

# Certificate is saved to: ~\.cloudflared\cert.pem
```

### Create Your First Tunnel

```powershell
# Create a tunnel
cloudflared tunnel create my-tunnel

# The tunnel credentials file is created at:
# ~\.cloudflared\<tunnel-id>.json
```

### Route DNS

```powershell
# Route a subdomain to your tunnel
cloudflared tunnel route dns my-tunnel app.yourdomain.com
```

### Create Config

Create `config.yml` in `~\.cloudflared\`:
```yaml
tunnel: my-tunnel
credentials-file: C:\Users\%USERNAME%\.cloudflared\<tunnel-id>.json

ingress:
  - hostname: app.yourdomain.com
    service: http://localhost:3000
  - service: http_status:404
```

### Run the Tunnel

```powershell
# Run in foreground (for testing)
cloudflared tunnel run my-tunnel

# Install as Windows service
cloudflared service install

# Start the service
net start cloudflared
```

## Tunnel Management

### Create Tunnel

```powershell
cloudflared tunnel create <tunnel-name>
```

Generates a UUID-based credentials JSON file. Save the tunnel ID — you'll need it for configuration.

### List Tunnels

```powershell
cloudflared tunnel list
```

Shows tunnel name, ID, status (active/inactive), and creation date.

### Delete Tunnel

```powershell
cloudflared tunnel delete <tunnel-name>
```

To force-delete a running tunnel:
```powershell
cloudflared tunnel delete -f <tunnel-name>
```

### Tunnel Info

```powershell
cloudflared tunnel info <tunnel-name>
```

### Cleanup Stale Tunnels

```powershell
# List all tunnels with status
cloudflared tunnel list

# Delete specific tunnels
cloudflared tunnel delete stale-tunnel-name
```

## Configuration (config.yml)

The config file lives at `~\.cloudflared\config.yml` (or a custom path).

### Full Config Example

```yaml
tunnel: my-tunnel
credentials-file: C:\Users\MyUser\.cloudflared\abc123.json

# Log settings
logfile: C:\Users\MyUser\.cloudflared\tunnel.log
loglevel: info

# Metrics (optional, for monitoring)
metrics: localhost:2000

# Ingress rules (routes hostnames to local services)
ingress:
  # Route app.yourdomain.com to localhost:3000
  - hostname: app.yourdomain.com
    service: http://localhost:3000

  # Route api.yourdomain.com to localhost:8080
  - hostname: api.yourdomain.com
    service: http://localhost:8080

  # Route dashboard.yourdomain.com to localhost:9000
  - hostname: dashboard.yourdomain.com
    service: http://localhost:9000

  # Catch-all rule — MUST be last. Returns 404 for unmatched routes.
  - service: http_status:404
```

### Ingress Rules Reference

| Type | Example | Description |
|------|---------|-------------|
| HTTP | `http://localhost:3000` | Route to local HTTP service |
| HTTPS | `https://localhost:8443` | Route to local HTTPS service |
| Unix | `unix:/tmp/app.sock` | Route to Unix socket (Linux only) |
| Status | `http_status:404` | Return HTTP status (404, 502, etc.) |
| File | `file:/var/www` | Serve static files (Linux only) |
| SSH | `ssh://localhost:22` | Proxy SSH through tunnel |
| RDP | `tcp://localhost:3389` | Proxy TCP (RDP, databases, etc.) |
| Bastion | `bastion` | SSH bastion mode |

### Origin Request Settings

```yaml
originRequest:
  connectTimeout: 30s
  tlsTimeout: 30s
  noTLSVerify: false
  # HTTP Host header override
  originServerName: service.internal
```

## DNS Configuration

### Route Domains

```powershell
# Route a DNS record to your tunnel
cloudflared tunnel route dns <tunnel-name> <hostname>

# Example
cloudflared tunnel route dns my-tunnel app.yourdomain.com
```

This creates a CNAME record in Cloudflare DNS pointing `<hostname>` to `<tunnel-id>.cfargotunnel.com`.

### Route IP Networks

```powershell
# Route an IP range through the tunnel (for private networks)
cloudflared tunnel route ip <network/cidr> <tunnel-name>
```

### Route to Load Balancer

```powershell
cloudflared tunnel route lb <tunnel-name> <lb-hostname> <lb-pool>
```

## Running Tunnels

### Foreground (Testing)

```powershell
cloudflared tunnel run <tunnel-name>
```

Press Ctrl+C to stop.

### Quick Run with Inline Config

```powershell
cloudflared tunnel run --url http://localhost:3000
```

This creates a quick tunnel with a random subdomain on trycloudflare.com — no account needed.

### Windows Service (Production)

```powershell
# Install service (uses ~\.cloudflared\config.yml)
cloudflared service install

# Start
net start cloudflared

# Stop
net stop cloudflared

# Restart
net stop cloudflared; net start cloudflared

# Remove service
cloudflared service uninstall

# Check status
sc query cloudflared
```

The service auto-starts on boot. It reads `config.yml` from `~\.cloudflared\`.

### Multiple Tunnel Services

For multiple tunnels, install separate services using `nssm` or configure each tunnel with its own config file:

```powershell
cloudflared tunnel --config C:\path\to\tunnel-a\config.yml run
```

## File Server

Cloudflare Tunnel can serve local directories through the edge:

```yaml
ingress:
  - hostname: files.yourdomain.com
    service: http://localhost:8080
    # Or use built-in file serving:
    # service: file:/path/to/directory
  - service: http_status:404
```

For Windows, use a web server (like `npx serve` or a Python HTTP server) as the local service.

## Cloudflare Access

Access policies let you add authentication in front of your tunneled services.

### Create a Self-Hosted Application

Via the Cloudflare Dashboard:
1. Go to Zero Trust → Access → Applications
2. Add a self-hosted application
3. Set domain (must be routed to your tunnel)
4. Configure policy rules

### Policy Rules Common Patterns

```yaml
# Example policy rules (configured via Dashboard or API):
# - Allow anyone with @yourcompany.com email
# - Require specific email domain
# - Allow only specific IP ranges
# - Require device posture checks
# - MFA enforcement
```

### Quick Access via Dashboard

For simple auth, use Cloudflare's built-in Access:
1. **Zero Trust Dashboard** → Access → Applications → Add Application
2. **Application type**: Self-hosted
3. **Domain**: `app.yourdomain.com` (must match your ingress hostname)
4. **Policy**: Name it, set rules (e.g., "Allow" if email ends with `@yourdomain.com`)
5. **Save** — Access enforces the policy automatically for traffic entering through the tunnel.

## Scripts

The skill includes PowerShell scripts for common operations:

### `scripts/setup-tunnel.ps1`
Interactive tunnel creation wizard — handles authentication check, tunnel creation, DNS routing, and config file generation in one guided flow.

### `scripts/list-tunnels.ps1`
Detailed tunnel listing with status, service health, and credential file info.

### `scripts/manage-service.ps1`
Windows service management: install, start, stop, restart, remove, and check status of the cloudflared service.

## Common Patterns

### Pattern 1: Quick Dev Tunnel

```powershell
# Test a local service without any setup
cloudflared tunnel run --url http://localhost:3000
```

### Pattern 2: Full Production Setup

```powershell
# 1. Login
cloudflared tunnel login

# 2. Create tunnel
cloudflared tunnel create my-app-tunnel

# 3. Route DNS
cloudflared tunnel route dns my-app-tunnel app.yourdomain.com

# 4. Write config.yml
#    (use setup-tunnel.ps1 or write manually)

# 5. Install service
cloudflared service install

# 6. Start
net start cloudflared
```

### Pattern 3: Multiple Services

```yaml
# config.yml — single tunnel, multiple hostnames
tunnel: main-tunnel
credentials-file: C:\Users\MyUser\.cloudflared\main-tunnel.json

ingress:
  - hostname: app.yourdomain.com
    service: http://localhost:3000
  - hostname: api.yourdomain.com
    service: http://localhost:8080
  - hostname: admin.yourdomain.com
    service: http://localhost:9000
  - hostname: status.yourdomain.com
    service: http://localhost:9090
  - service: http_status:404
```

### Pattern 4: RDP Through Tunnel

```yaml
ingress:
  - hostname: rdp.yourdomain.com
    service: tcp://localhost:3389
  - service: http_status:404
```

Then connect from any machine:
```powershell
# Using cloudflared access
cloudflared access rdp --hostname rdp.yourdomain.com --destination localhost:3389
```

### Pattern 5: SSH Bastion

```yaml
ingress:
  - hostname: ssh.yourdomain.com
    service: ssh://localhost:22
  - service: http_status:404
```

Configure SSH:
```powershell
# In ~/.ssh/config
Host tunnel-ssh
  ProxyCommand cloudflared access ssh --hostname ssh.yourdomain.com
```

## Troubleshooting

### Tunnel Won't Connect

```powershell
# Check authentication
cloudflared tunnel list

# Verify config
cloudflared tunnel --config ~\.cloudflared\config.yml ingress validate

# Run with verbose logging
cloudflared tunnel run <tunnel-name> --loglevel debug

# Check service
sc query cloudflared
netstat -an | findstr ":2000"  # Check metrics port
```

### Common Issues

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| `ERR Cannot determine default origin certificate path` | Not logged in | Run `cloudflared tunnel login` |
| `config.yml not found` | No config file | Create one in `~\.cloudflared\` |
| `service "cloudflared" not found` | Service not installed | `cloudflared service install` |
| `failed to connect to origin` | Local service not running | Start your local server |
| `404 for all routes` | No matching ingress rule | Check hostname case and patterns |
| `ERR 1033` | Argo Smart Routing issue | Check Cloudflare dashboard |

### Logs

```powershell
# Check service logs
Get-Content "$env:USERPROFILE\.cloudflared\tunnel.log" -Tail 50

# Run with debug output
cloudflared tunnel run <tunnel-name> --loglevel debug
```

### Config Validation

```powershell
# Validate config file without running tunnel
cloudflared tunnel --config ~\.cloudflared\config.yml ingress validate
```

## Notes

- Always login first: `cloudflared tunnel login`
- The `cert.pem` is the root certificate — keep it secure
- Each tunnel gets a UUID-based credentials JSON (the `.json` file)
- The catch-all ingress rule (`http_status:404`) is required at the end
- Use `scripts/setup-tunnel.ps1` for guided tunnel creation
- Tunnel credentials files are tied to the Cloudflare account that created them
- For production, run tunnel as a Windows service for auto-start
- Ingress hostnames are matched exactly — `app.domain.com` ≠ `App.domain.com`
- Origin services must be running before the tunnel starts
- Delete tunnel credentials safely when decommissioning a tunnel
