# Server / Docker Self-Update Patterns

This reference maps the architecture from SKILL.md to server-side deployments:
Docker containers, standalone Linux/macOS servers, and any long-running
background process that needs to replace itself.

The server path is the most general — it must handle the full download →
verify → swap → restart → rollback cycle without any framework doing it for
you.

## State Machine

The backend owns the state in a global data structure protected by a read-write
lock (see `desktop-native.md` for per-language lock patterns). The frontend
subscribes via WebSocket or polling.

### WebSocket broadcast pattern

```go
// Go server example
type UpdateState struct {
    mu          sync.RWMutex
    current     AppUpdateState
    subscribers map[chan AppUpdateState]struct{}
}

func (s *UpdateState) Subscribe() (chan AppUpdateState, func()) {
    s.mu.Lock()
    defer s.mu.Unlock()
    ch := make(chan AppUpdateState, 8)
    s.subscribers[ch] = struct{}{}
    // Send current snapshot immediately
    ch <- s.current
    return ch, func() {
        s.mu.Lock()
        delete(s.subscribers, ch)
        s.mu.Unlock()
    }
}

func (s *UpdateState) Broadcast(snapshot AppUpdateState) {
    s.mu.Lock()
    s.current = snapshot
    for ch := range s.subscribers {
        select {
        case ch <- snapshot:
        default: // drop slow subscriber
        }
    }
    s.mu.Unlock()
}
```

### HTTP endpoints

Expose these endpoints for the frontend:

```
POST /api/check_app_update     → returns manifest info + whether an update is available
POST /api/perform_app_update   → starts background download, returns current snapshot
POST /api/get_app_update_state → returns current snapshot
POST /api/restart_app          → claims restart, schedules exit
POST /api/rollback_app         → restores .bak, schedules restart
POST /api/app_update_status    → returns local capability (no network call)
```

## Download + Verify + Extract + Swap (Go example)

```go
func PerformUpdate(dataDir string, onProgress func(phase string, downloaded, total int64)) error {
    // 1. Resolve targets: server binary, auxiliary binaries, static directory
    serverBin, _ := os.Executable()
    bindir := filepath.Dir(serverBin)
    webDir := resolveStaticDir()

    // 2. Preflight: check writability
    if err := checkWritable(bindir); err != nil { return err }
    if err := checkWritable(webDir); err != nil { return err }

    // 3. Refuse if an upgrade is already staged
    if _, err := os.Stat(filepath.Join(bindir, ".app-upgrade-staged")); err == nil {
        return errors.New("update already staged — restart to apply first")
    }

    // 4. Fetch manifest, compare versions
    manifest := fetchManifest()
    if !versionIsNewer(manifest.Version, CurrentVersion) {
        return errors.New("already running the latest version")
    }

    // 5. Download archive + signature
    archive := downloadFile(manifest.URL, onProgress)
    sig := downloadFile(manifest.URL + ".sig", nil)

    // 6. Verify signature before touching live files
    if err := minisignVerify(archive, sig, PublicKey); err != nil {
        return fmt.Errorf("signature verification failed: %w", err)
    }

    // 7. Extract to staging directory on the data volume
    staging := filepath.Join(dataDir, ".app-update-"+strconv.Itoa(os.Getpid()))
    defer os.RemoveAll(staging)
    os.MkdirAll(staging, 0755)
    extractArchive(archive, staging)

    // 8. Verify bundle completeness
    newServer := filepath.Join(staging, "your-server")
    if _, err := os.Stat(newServer); os.IsNotExist(err) {
        return errors.New("update package is missing the server binary")
    }

    // 9. Atomic swap: each artifact in order, roll back on failure
    swapFile(serverBin, newServer)
    swapDir(webDir, filepath.Join(staging, "web"))

    // 10. Write upgrade marker
    writeUpgradeMarker(bindir)

    return nil
}
```

## Atomic File Swap Helpers (Go)

```go
func swapFile(target, src string) error {
    dir := filepath.Dir(target)
    name := filepath.Base(target)
    staged := filepath.Join(dir, "."+name+".new")
    bak := target + ".bak"

    // Stage in same directory
    if err := copyFile(src, staged); err != nil { return err }
    os.Chmod(staged, 0755)

    // fsync staged file contents
    syncFile(staged)

    // Backup: hard-link or copy
    os.Remove(bak)
    if err := os.Link(target, bak); err != nil {
        // Hard link failed — copy via temp file
        bakTmp := bak + ".tmp"
        os.Remove(bakTmp)
        copyFile(target, bakTmp)
        syncFile(bakTmp)
        os.Rename(bakTmp, bak)
    }

    // Atomic swap
    if err := os.Rename(staged, target); err != nil {
        os.Remove(staged)
        return err
    }

    syncDir(dir)
    return nil
}

func swapDir(target, staged string) error {
    parent := filepath.Dir(target)
    name := filepath.Base(target)
    stagePath := filepath.Join(parent, "."+name+".new")
    bak := target + ".bak"

    // Move the extracted tree into the staging path
    os.RemoveAll(stagePath)
    if err := os.Rename(staged, stagePath); err != nil {
        return err
    }

    os.RemoveAll(bak)

    // Try atomic exchange first (Linux/macOS)
    if err := renameExchange(target, stagePath); err == nil {
        // target now holds new tree, stagePath holds old tree → become .bak
        os.Rename(stagePath, bak)
    } else {
        // Fall back: rename old aside, rename new in
        if err := os.Rename(target, bak); err != nil {
            if isCrossDevice(err) {
                // overlayfs: copy instead
                copyDirRecursive(target, bak+".tmp")
                os.Rename(bak+".tmp", bak)
                os.RemoveAll(target)
                os.Rename(stagePath, target)
            } else {
                return err
            }
        } else {
            os.Rename(stagePath, target)
        }
    }

    syncDir(parent)
    return nil
}
```

## Restart: Supervised Mode (Docker)

### Supervisor (Go example)

```go
func supervise(exePath string, args []string, env []string) {
    trialDeadline := time.Time{}

    for {
        cmd := exec.Command(exePath, args...)
        cmd.Env = append(os.Environ(), "CODEG_SUPERVISED=1")
        cmd.Stdout = os.Stdout
        cmd.Stderr = os.Stderr
        cmd.Start()

        err := cmd.Wait()
        exitCode := cmd.ProcessState.ExitCode()

        if exitCode == 86 {
            // Upgrade restart requested
            time.Sleep(restartDelay)
            if upgradeStaged(exePath) {
                trialDeadline = time.Now().Add(trialDuration)
            }
            continue
        }

        if !trialDeadline.IsZero() && time.Now().Before(trialDeadline) {
            // Crashed during trial → rollback
            if exitCode != 0 {
                rollback(exePath)
            }
            trialDeadline = time.Time{}
            continue
        }

        trialDeadline = time.Time{}
        // Normal exit or crash → pass through to Docker/container policy
        if err != nil {
            os.Exit(exitCode)
        }
        return
    }
}
```

### Dockerfile

```dockerfile
FROM alpine:3.20

# Install dependencies
RUN apk add --no-cache curl minisign

COPY your-server /app/your-server
COPY web/ /app/web/
COPY mcp-server /app/mcp-server

# Supervisor wraps the server binary
ENTRYPOINT ["/app/your-server", "--supervise"]
```

Important: The `--supervise` mode runs the supervisor loop, which in turn spawns
the real server worker as a child process. The supervisor itself never updates
— only the worker does, and the supervisor relaunches it.

## Restart: Re-exec Mode (standalone server)

### Go re-exec

```go
func restartNow() {
    exe, _ := os.Executable()

    // On Unix: exec replaces the process image
    if runtime.GOOS != "windows" {
        syscall.Exec(exe, os.Args, os.Environ())
        // Only reached if exec fails
        os.Exit(86)
    }

    // On Windows: spawn child and exit
    cmd := exec.Command(exe, os.Args[1:]...)
    cmd.Stdout = os.Stdout
    cmd.Stderr = os.Stderr
    cmd.Start()
    os.Exit(0)
}
```

### Python re-exec

```python
import os, sys

def restart_now():
    exe = sys.executable
    args = [exe] + sys.argv[1:]
    if os.name != 'nt':
        os.execv(exe, args)
    else:
        import subprocess
        subprocess.Popen(args)
        sys.exit(0)
```

### Node.js re-exec

```javascript
const { execSync, spawn } = require('child_process')

function restartNow() {
  if (process.platform !== 'win32') {
    // exec replaces the process
    const err = spawn(process.execPath, process.argv.slice(1), {
      stdio: 'inherit',
      env: process.env,
    }).on('error', (err) => {
      console.error('Failed to exec:', err)
      process.exit(86)
    })
    if (err.pid) process.exit(0)
  } else {
    spawn(process.execPath, process.argv.slice(1), {
      stdio: 'inherit',
      detached: true,
      env: process.env,
    }).unref()
    process.exit(0)
  }
}
```

## Rollback

```go
func rollback(serverBin string) error {
    bindir := filepath.Dir(serverBin)

    // Restore each artifact from .bak
    restoreFromBak(serverBin)
    restoreFromBak(filepath.Join(bindir, "mcp-server"))
    restoreDirFromBak(resolveStaticDir())

    // Clear upgrade marker
    os.Remove(filepath.Join(bindir, ".app-upgrade-staged"))

    return nil
}

func restoreFromBak(target string) bool {
    bak := target + ".bak"
    if _, err := os.Stat(bak); os.IsNotExist(err) {
        return false
    }
    os.Remove(target)
    os.Rename(bak, target)
    return true
}
```

## Non-Atomic Consideration for Windows Server

Self-updating a running Windows executable is inherently unreliable because the
`.exe` is locked. If you must support Windows server self-update:

1. Use a "stager" helper binary (`updater.exe`) shipped alongside the main
   server.
2. The main server, when ready to restart: spawns `updater.exe` with the paths
   to swap, then exits.
3. `updater.exe` waits for the main server's PID to terminate, swaps the
   files, then relaunches the main server.

This is fragile and has more failure modes than Unix `exec`. Consider
deploying Windows servers inside containers (Docker) and using the supervised
mode instead.

## Health Check Endpoint

Always expose a lightweight `/health` endpoint for post-restart polling:

```go
// GET /health
func healthHandler(w http.ResponseWriter, r *http.Request) {
    response := map[string]interface{}{
        "status":  "ok",
        "version": CurrentVersion,
        "uptime":  time.Since(startTime).Seconds(),
    }
    json.NewEncoder(w).Encode(response)
}
```

The frontend uses this to:
- Detect when the restarted server is back online.
- Confirm the post-restart version matches the expected new version.
- Detect an auto-rollback (version stayed the same or reverted).

## Checklist for Server/Docker

- [ ] State machine behind RwLock, emitted via WebSocket broadcast
- [ ] HTTP endpoints for check, perform, restart, rollback, status
- [ ] Download with progress throttling (update snapshot every chunk, emit every 100ms)
- [ ] Signature verification before touching live files
- [ ] Atomic file swap with .bak, fsync on all paths
- [ ] Upgrade marker file with temp + rename + fsync
- [ ] Supervisor loop with trial window (Docker) or re-exec (standalone)
- [ ] Rollback from .bak with marker cleanup
- [ ] `/health` endpoint returning version
- [ ] Size caps on archive (download) and decompressed bytes (extraction)
- [ ] Archive extraction: reject symlinks, path traversal, non-file entries
