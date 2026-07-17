---
name: software-update
description: >
  Implement auto-update, self-update, OTA, and release-distribution features for desktop, server,
  and Docker applications in any language or framework. Use this skill whenever the user asks about
  adding an update mechanism, checking for new versions, downloading and installing updates, atomic
  file replacement, rollback strategies, restart-after-update, or progress tracking for an update
  flow — even if they don't explicitly say "auto-update" or "self-update." Covers Electron, Tauri,
  native (C/C++/Rust/Go), and server/Docker deployment patterns.
---

# Software Update Architecture

This document captures architectural patterns for building safe, resilient
application update systems. It is language- and framework-agnostic — the same
patterns apply whether you build with C on Win32, Rust with Actix, Electron,
Tauri, or a Go server. Only the low-level APIs differ. For concrete API
guidance, read the platform reference that matches your stack (listed at the
bottom of this document).

## 1. The State Machine

If update progress lives in a UI component, navigating away from the settings
page destroys the component and loses the progress while the download keeps
running underneath. **Own the update state in the backend** — a process-global,
thread-safe data structure. The UI becomes a pure subscriber that re-syncs from
a snapshot on mount.

### Lifecycle

```
Idle ──> Downloading ──> Installing ──> ReadyToRestart ──> Restarting
  │                                                          │
  └────────────────── Error <───────────────────────────────┘
  │                                                          │
  └──────────── (retry from Error restarts at Downloading) ──┘
```

- **Idle** — nothing happening, UI shows a "Check for Updates" button.
- **Downloading** — bytes are streaming in; the UI shows a determinate progress bar.
- **Installing** — download finished, now verifying / extracting / swapping files; UI shows indeterminate progress.
- **ReadyToRestart** — new files are staged on disk; the only path forward is a restart.
- **Restarting** — a restart or rollback has been claimed and is about to happen.
- **Error** — terminal failure; the user can retry (which goes back to Downloading).

### Emitting state changes

Every transition emits the *entire snapshot* to all subscribers. Use a flat
struct with a discriminator field (`status`) so the UI uses a single switch to
render the correct view:

```
{ seq: 3, status: "downloading", downloaded: 12582912, total: 50331648 }
{ seq: 4, status: "downloading", downloaded: 25165824, total: 50331648 }
{ seq: 5, status: "installing" }
{ seq: 6, status: "ready_to_restart", version: "2.1.0", restartDelayMs: 2000 }
```

### Monotonic sequence numbers

Every state mutation bumps a `seq` counter. The frontend keeps only the
highest-`seq` value it has ever seen:

- A late-arriving snapshot (seq=2) cannot overwrite a newer live event (seq=5).
- After a backend restart (e.g. self-update), the seq resets to 0. The
  reconnect handler must reset the client's high-water mark so the new
  process's state (starting from 0) is accepted.
- When clearing operation fields (progress, error text) on a state transition,
  bump seq so stale data never leaks into the new status.

## 2. Concurrency Control

Updates are multi-step operations that touch shared resources (the running
binary, a `.bak` backup). Multiple clicks, a rollback while downloading, or a
restart while swapping must not race.

### System operation lock

A single process-level mutex (`system_op_lock`) serializes three mutually
exclusive operations:

| Operation | What it does | Allowed from |
|-----------|-------------|-------------|
| `perform_update` | Download + verify + swap | Idle, Error |
| `restart` | Relaunch into staged update | ReadyToRestart |
| `rollback` | Restore previous `.bak` | Idle, Error |

Each operation acquires the op-lock, then atomically checks and claims the
state. If the state doesn't allow the operation, release the lock and back off.

### Atomic claim functions

```
try_begin(handle, emitter) → (started: bool, snapshot)

  // Acquire write-lock. If status is NOT Idle or Error:
  //   return (false, current_snapshot) — caller attaches, doesn't start.
  // Else:
  //   bump seq, clear old fields, set status=Downloading, downloaded=0
  //   return (true, new_snapshot)

try_claim_restart(handle, emitter) → bool

  // If status IS ReadyToRestart:
  //   bump seq, set status=Restarting, return true
  // Else: return false

try_claim_rollback(handle, emitter) → bool

  // If status IS Idle or Error:
  //   bump seq, set status=Restarting, return true
  // Else: return false
```

The check-and-set happens in one critical section, so two concurrent callers
cannot both succeed. Whoever claims first wins; the loser backs off without
blocking the winner.

### Aborting a claim

When a caller wins `try_begin` but then fails to acquire the op-lock (because a
restart or rollback holds it), it must revert the state back to Idle. Guard
this with a seq check: only revert if the current seq equals the claim's seq.
If a concurrent operation has since moved the state to Error or beyond, leave
it alone — don't clobber a newer state.

## 3. Version Checking

### Manifest

Serve a JSON manifest at a well-known URL (e.g.
`https://releases.example.com/latest.json`). At minimum:

```json
{
  "version": "v2.1.0",
  "notes": "Bug fixes and performance improvements.",
  "pub_date": "2025-07-03T12:00:00Z"
}
```

For multi-platform releases, add a `platforms` map with per-target download
URLs and expected hashes.

### Version comparison

Use semver. Strip a leading `v` before parsing:

```
"v2.1.0" → (2, 1, 0)
"2.0.9"  → (2, 0, 9)
```

Compare `major.minor.patch` numerically. If either string fails to parse,
fall back to simple string inequality — it will at least detect a change even
if the format is non-standard.

### Meaning of "update available"

An update is available **only** when `latest_version > current_version`.
Re-downloading an equal version would move the current binary into `.bak`
and destroy the rollback target for zero benefit.

## 4. Downloading with Progress

### Chunked streaming

Stream the response body in chunks. Don't buffer the entire file in memory —
you need real progress data and the download may be tens of megabytes.

### Progress throttling

Update the snapshot on **every chunk** so a late-mounting UI always reads exact
data. But emit a live event at most once every 100 ms — a multi-megabyte
download done per-chunk would otherwise emit thousands of events.

Always emit on the first byte (`downloaded == 0`) and the last byte
(`downloaded >= total`) even within the throttle window, so the UI transitions
immediately.

If the lifecycle has already left `Downloading` when a late progress callback
arrives, drop the callback — don't resurrect the progress bar.

### Size caps

Set hard limits before starting the download:

| Limit | Value (example) | Why |
|-------|----------------|-----|
| Maximum archive bytes | 600 MB | Prevents a hostile Content-Length from triggering an unbounded allocation |
| Maximum decompressed bytes | 1.5 GB | Stops a zip bomb or mispackaged release from filling the disk |

Check both limits *during* streaming, not just afterward. Abort mid-stream if
either is exceeded.

## 5. Security

### Signature verification

Download a detached signature alongside the archive. Verify the signature
**before touching any live file** on the target system. Never extract an
unverified archive into a staging directory — a rename could promote it.

Minisign/Ed25519 is recommended for its simplicity and small key footprint. The
public key is hard-coded (or overridable via config for enterprise deployments).

### Archive safety during extraction

When extracting a tarball or zip, reject:
- Symbolic links, hard links, device nodes, FIFOs — only regular files and
  directories.
- Paths containing `../` or absolute paths.
- Entries whose uncompressed size exceeds the budget (check actual bytes
  written, not the header-declared size — those can lie).

On Unix, preserve the `+x` mode bit from the archive so extracted binaries are
executable after the swap.

## 6. Atomic Installation

A power loss or SIGKILL at any moment during the swap must leave the system
with either the old version or the new version — never half-upgraded.

### The swap pattern (per file)

```
1. Copy new file to  <target_dir>/.<name>.new     (stage in same directory)
2. fsync the .new file                             (durable bytes before rename)
3. Hard-link target → .bak                         (O(1) inode ref; fall back to copy via .bak.tmp)
4. rename .<name>.new → <name>                     (same-filesystem, atomic)
5. fsync the parent directory                      (durable directory entry)
```

**Why stage in the target's own directory:** `rename(2)` is atomic only within
the same filesystem. Staging in `/tmp` and renaming across mount points is not
atomic.

**Why hard-link the backup:** Moving `target` to `.bak` first would leave the
name momentarily absent — a crash in that window leaves the system unbootable.
A hard link creates a second name for the same inode; the rename of `.new` to
`target` then atomically redirects the name.

**If hard links fail** (some filesystems, containers): copy the old file to
`.bak.tmp`, fsync it, then rename `.bak.tmp` to `.bak`. This guarantees `.bak`
only ever appears complete or not at all.

### Platform-specific swap considerations

| Scenario | Problem | Workaround |
|----------|---------|------------|
| NTFS (Windows) | `rename` cannot overwrite an existing file | Move aside first: rename target → .bak, then rename .new → target |
| overlayfs (Docker) | Renaming an image-layer directory returns EXDEV | Use `RENAME_EXCHANGE` (Linux) / `RENAME_SWAP` (macOS) syscalls, or copy + delete as fallback |
| Cross-filesystem | rename not atomic | Copy is the only option; accept the non-atomic window |

On Linux 3.15+ and macOS, prefer `renameat2(RENAME_EXCHANGE)` /
`renamex_np(RENAME_SWAP)` for directory swaps — both directories are atomically
exchanged, so neither is ever momentarily absent.

### Directory fsync

On Unix, `fsync` on a file flushes its data but **not** the parent directory's
updated entry. After every file/directory rename, `fsync` the parent directory
so the rename survives a power loss.

### Upgrade staged marker

After a successful swap, write a small marker file (e.g.
`.your-app-upgrade-staged`) to the binary's directory, using the same
temp-file + fsync + rename pattern. This marker:

1. **Prevents a second `perform_update`** before a restart: re-swapping would
   move the already-new files into `.bak`, destroying the rollback target.
2. **Signals trial mode**: in supervised deployments, the supervisor sees the
   marker and puts the next launch on probation.

If the marker cannot be persisted durably, undo the entire swap.

## 7. Restart Strategies

Three restart modes, selected by deployment context:

### Supervised (Docker, systemd)

The worker process exits with a specific exit code (pick an unused number, e.g.
86). The supervisor sees that code and relaunches after a configurable delay
(default 2000 ms).

```
Worker flow:
  1. Swap files, write upgrade marker, flush everything.
  2. exit(86)

Supervisor flow:
  1. Wait restart_delay_ms after child exits with 86.
  2. Spawn new worker.
  3. Worker starts, supervisor sees upgrade marker.
  4. Put worker on probation for trial_seconds (default 30 s).
  5. If worker crashes within window → auto-rollback to .bak.
  6. If worker survives window → clear marker (upgrade committed).
```

The upgrade marker must NOT be consumed by the supervisor during the trial
window — it is only *peeked* at. If consumed, a second `perform_update` would
no longer be blocked and could clobber the rollback target.

### Re-exec (standalone, Unix)

Replace the current process image with `execvp()`:

```
const char *args[] = {argv[0], argv[1], ..., NULL};
execvp(self_exe_path, args);
// Only reached if exec fails
```

- FDs marked `CLOEXEC` are automatically closed, so the listening socket is
  released for the new process.
- Before calling `exec`, allow ~400 ms for the HTTP response (that confirms the
  restart to the client) to flush. Keep the op-lock guard alive until exit.
- On Windows (no `exec`), spawn a child process and exit the parent.

### Framework restart (desktop GUI)

Let the framework handle it: `electron-updater.quitAndInstall()`,
`app.restart()` in Tauri, etc. The architecture above still applies — the
framework handles the relaunch but you still own state, progress, and the
update lifecycle on both sides.

## 8. Rollback

### When rollback is allowed

Only from settled states (`Idle` or `Error`), never when an update is in
flight. The check-and-set claim pattern serializes rollback against
perform/restart.

### Rollback mechanics

For each artifact that was swapped:
1. Delete the current file/directory.
2. Rename `.bak` → original name.

Delete the upgrade staged marker so the next `perform_update` is not blocked.

### Post-rollback confirmation

After the rollback restart, poll the health endpoint and read the running
version. If it differs from the pre-rollback version, the rollback succeeded.

## 9. UI Patterns

### Global status bar

A small persistent indicator visible on all pages:

```
Idle (hidden)           →  nothing shown, or app version only
Downloading             →  spinner + "Downloading 48%"
Installing              →  pulse animation + "Installing..."
ReadyToRestart          →  clickable button: "Restart to Update"
Restarting              →  "Restarting in 3 seconds..."
Error                   →  red tag + error summary
```

### Settings page

The dedicated update panel shows:
- Current version string.
- "Check for Updates" button.
- "Upgrade to vX.Y.Z" button (when an update is available).
- Determinate progress bar during download; indeterminate during install.
- Release notes rendered from the manifest.
- Manual rollback button (if `.bak` exists), with a confirmation dialog.
- Docker-specific hints (e.g. "Restarting the container will revert this
  update — pull the latest image to make it permanent").

### Error classification

Classify raw error messages into user-facing categories by pattern-matching
keywords:

```
source_unreachable  → "Could not reach the update server"
network             → "Network error — check your connection"
download_failed     → "Download was interrupted"
install_failed      → "Could not install the update — check permissions"
unknown             → display the raw message
```

## 10. Communication Between Frontend and Backend

### Subscribe-then-fetch

On mount, subscribe to update events *before* fetching the snapshot:

```
subscribe(eventChannel, handler)   // 1. arm listener first
snapshot = fetchState()            // 2. then fetch current state
```

Reversing the order creates a race: if an event fires between `fetchState` and
`subscribe`, it is silently dropped.

### Transport abstraction

If the app runs in multiple modes (local desktop vs remote server), abstract
the communication:

```
interface Transport {
  call(channel: string, payload?: any): Promise<any>;
  subscribe(channel: string, handler: (payload: any) => void): Promise<() => void>;
  onReconnect(cb: () => void): void;
}
```

| Mode | `call` | `subscribe` |
|------|--------|-------------|
| Desktop (IPC) | Native invoke / D-Bus / named pipe | Native event / signal |
| Remote (HTTP) | HTTP POST to /api/<channel> | WebSocket subscription |

### Reconnection

When the transport reconnects (e.g. WebSocket drops during server restart):
1. Reset the client's high-water seq (the backend's seq starts from 0 again).
2. Re-subscribe to events.
3. Fetch the snapshot.

---

## Platform References

Based on your target platform, read the matching reference for concrete API
guidance:

| If you are building with... | Read |
|-----------------------------|------|
| C / C++ / Rust / Go / Zig (native desktop) | [desktop-native.md](references/desktop-native.md) |
| Node.js + Electron | [electron.md](references/electron.md) |
| Rust + Tauri | [tauri.md](references/tauri.md) |
| Go / Rust / Python / Node.js server (Docker or standalone) | [server-docker.md](references/server-docker.md) |
