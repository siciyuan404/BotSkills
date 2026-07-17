# Native Desktop Update Patterns (C / C++ / Rust / Go / Zig)

This reference maps the architecture from SKILL.md to platform-agnostic
syscalls and library choices available in compiled languages.

## State Machine

Use a struct protected by a read-write lock. In each language:

| Language | Shared state | Lock |
|----------|-------------|------|
| C (POSIX) | `struct app_update_state` | `pthread_rwlock_t` |
| C (Win32) | `struct app_update_state` | `SRWLOCK` (Vista+) |
| C++ | `AppUpdateState` | `std::shared_mutex` |
| Rust | `Arc<RwLock<AppUpdateState>>` | stdlib |
| Go | struct with exported fields | `sync.RWMutex` |
| Zig | struct | `std.Thread.RwLock` |

The lock guards every read and write. On a poisoned lock (writer panicked):
recover the inner state rather than wedging readers. A momentarily stale
snapshot is better than a blocked UI.

## IPC Communication

For a single-process desktop app (UI thread + worker threads), use in-process
channels:

| Pattern | C | C++ | Rust | Go |
|---------|---|-----|------|----|
| Event broadcast | Condition variable + callback list | `std::condition_variable` + observer | `tokio::broadcast` | Channel with fan-out |
| Snapshot query | Direct lock+read | Direct lock+read | `handle.read()` | `mutex.RLock()` |

For multi-process (UI app + background service), choose one transport:

| Transport | Pros | Cons |
|-----------|------|------|
| Unix domain socket | No port conflicts; permission control | Unix-only |
| Windows named pipe | No port conflicts; ACL support | Windows-only |
| TCP localhost + HTTP | Cross-platform; easy to test | Port conflicts possible |
| D-Bus | Standard on Linux desktops | Linux-only |

### Subscribe-then-fetch over a socket

```
// Subscribe
send(conn, { type: "subscribe", channel: "app_update_state" })

// Then fetch
send(conn, { type: "call", channel: "app_update_state" })
```

The server-side subscription registration must happen before the snapshot query
is processed. If the server handles them sequentially on the same connection,
send subscribe then fetch in order.

## HTTP Downloading (libcurl)

```c
CURL *curl = curl_easy_init();
curl_easy_setopt(curl, CURLOPT_URL, archive_url);
curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
curl_easy_setopt(curl, CURLOPT_XFERINFOFUNCTION, progress_callback);
curl_easy_setopt(curl, CURLOPT_NOPROGRESS, 0L);
curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 1L);
// Optional: set CURLOPT_MAXFILESIZE for the max archive size

// progress_callback receives: total, downloaded
// Return non-zero from progress_callback to abort the transfer
```

In Rust, use `reqwest`:
```rust
let response = client.get(url).send().await?;
let total = response.content_length();
let mut stream = response.bytes_stream();
let mut downloaded: u64 = 0;
while let Some(chunk) = stream.next().await {
    let chunk = chunk?;
    downloaded += chunk.len() as u64;
    if let Some(max) = max_bytes {
        if downloaded > max { return Err(...); }
    }
    on_progress(downloaded, total);
}
```

## Archive Extraction

### Tarball (tar.gz)

**C**: Use `libarchive` or `zlib` + manual tar parsing. Always:
- Reject symlinks (`AE_SYMLINK`). Set `ARCHIVE_EXTRACT_SECURE_SYMLINKS` and
  `ARCHIVE_EXTRACT_SECURE_NODOTDOT`.
- Check `archive_entry_pathname()` for `../`.
- Bound extracted bytes per entry.

**Rust**: Use the `tar` + `flate2` crates:
```rust
let mut archive = tar::Archive::new(flate2::read::GzDecoder::new(Cursor::new(bytes)));
for entry in archive.entries()? {
    let mut entry = entry?;
    let path = entry.path()?.into_owned();
    // Reject symlinks
    if entry.header().entry_type().is_symlink() { return Err(...); }
    // Sanitize path
    // Bound extracted bytes via entry.take(max_remaining + 1)
}
```

### Zip

**C**: Use `libzip` or `minizip`. Call `zip_fopen_index()` and verify
`zip_name_locate()` doesn't return paths with `../`.

**Rust**: Use the `zip` crate:
```rust
let mut archive = zip::ZipArchive::new(Cursor::new(bytes))?;
for i in 0..archive.len() {
    let mut file = archive.by_index(i)?;
    let Some(path) = file.enclosed_name() else { return Err(...); };
    // `enclosed_name()` already rejects path traversal
    // Bound extracted bytes via file.take(max_remaining + 1)
}
```

## Atomic File Swap

### POSIX (Linux, macOS)

```c
#include <fcntl.h>
#include <unistd.h>
#include <stdio.h>

// 1. Copy new binary to staging path
// ... (file copy) ...

// 2. fsync staged file
int fd = open(staged_path, O_RDONLY);
fsync(fd);
close(fd);

// 3. Hard-link old binary as backup
link(target_path, backup_path);  // may fail on some FS — fall back to copy

// 4. Atomic rename staged → target
rename(staged_path, target_path);

// 5. fsync the parent directory
int dirfd = open(dirname, O_RDONLY);
fsync(dirfd);
close(dirfd);
```

### Directory swap with RENAME_EXCHANGE (Linux)

```c
#define _GNU_SOURCE
#include <stdio.h>
#include <fcntl.h>

// Atomically exchange web/ and .web.new/
int rc = renameat2(AT_FDCWD, "web", AT_FDCWD, ".web.new", RENAME_EXCHANGE);
if (rc == 0) {
    // web/ now holds the new tree, .web.new/ holds the old one
    rename(".web.new", "web.bak");  // old tree becomes the backup
} else {
    // Fall back to non-atomic move
}
```

### Windows

```c
#include <windows.h>

// Windows rename (MoveFileEx) cannot overwrite an existing file.
// Move the old file aside first:
MoveFileExW(target_path, backup_path, MOVEFILE_REPLACE_EXISTING);
if (!MoveFileExW(staged_path, target_path, MOVEFILE_REPLACE_EXISTING)) {
    // Rollback: restore from backup
    MoveFileExW(backup_path, target_path, MOVEFILE_REPLACE_EXISTING);
    return error;
}
// On Windows, FlushFileBuffers on a directory handle is equivalent to fsync.
```

Note: Self-updating a running `.exe` on Windows is inherently tricky because
the file is locked while executing. Two approaches:
1. Use a "stager" executable that the main app spawns before exit — the stager
   waits for the main process to die, swaps the files, then relaunches it.
2. Use the Win32 `MoveFileEx` with `MOVEFILE_DELAY_UNTIL_REBOOT` flag to
   schedule the replacement on next boot (crude but reliable).

## Restart: Re-exec

### Unix

```c
#include <unistd.h>

void restart_now(const char *exe_path, char *const argv[]) {
    execvp(exe_path, argv);
    // Only reached if exec fails
    perror("execvp");
    _exit(86);
}
```

All FDs not marked `FD_CLOEXEC` survive `exec`. If you want the new process to
rebind the listening socket, set `SOCK_CLOEXEC` on `socket()` or use
`fcntl(F_SETFD, FD_CLOEXEC)`.

### Windows

```c
#include <windows.h>

void restart_now(const wchar_t *exe_path, const wchar_t *cmdline) {
    STARTUPINFOW si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    if (CreateProcessW(exe_path, (LPWSTR)cmdline, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi)) {
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
        ExitProcess(0);
    }
    // Spawn failed
    ExitProcess(86);
}
```

## Signature Verification

### Minisign verification

Call the `minisign` CLI tool or link `libsodium` directly:

```c
// Recommended approach: call minisign CLI (simpler, fewer dependencies)
// minisign -Vm <archive> -x <archive>.sig -P <public_key>
```

In Rust, use the `minisign` crate:
```rust
let signature = minisign::Signature::decode(&sig_b64)?;
let pubkey = minisign::PublicKey::decode(&PUBLIC_KEY_BASE64)?;
pubkey.verify(&archive_bytes, &signature, false)?;
```

### Checksum fallback

If you can't do Ed25519 signing, ship a SHA-256 hash alongside the download and
verify it after downloading. This protects against corruption but NOT against a
compromised release server (an attacker who replaces the archive can also
replace the hash file).

## Supervisor Implementation

If implementing supervised mode (SKILL.md §7) in C:

```c
// Supervisor loop (simplified)
while (1) {
    pid_t child = fork();
    if (child == 0) {
        // Worker: set CODEG_SUPERVISED=1, exec the binary
        setenv("CODEG_SUPERVISED", "1", 1);
        execvp(binary_path, argv);
        _exit(1);
    }

    int status;
    waitpid(child, &status, 0);

    if (WIFEXITED(status) && WEXITSTATUS(status) == 86) {
        // Update restart requested
        sleep(restart_delay_seconds);
        // Check for upgrade marker → set trial deadline
        trial_deadline = time(NULL) + trial_seconds;
        continue;  // relaunch
    }

    if (trial_deadline > 0 && time(NULL) < trial_deadline) {
        // Child crashed during trial window → auto-rollback
        rollback_bak_files();
        trial_deadline = 0;
        continue;  // relaunch with previous version
    }

    trial_deadline = 0;
    // Normal exit or crash after trial → relaunch without special handling
}
```

## Platform Checklist

When implementing native update on a new desktop platform:

- [ ] State machine with RwLock
- [ ] IPC transport (even if in-process, have a clean interface)
- [ ] HTTP download with progress callback
- [ ] Archive extraction with path sanitization and size caps
- [ ] Signature verification before file swap
- [ ] Atomic rename swap with .bak, fsync on all paths
- [ ] Upgrade marker file with atomic write
- [ ] Restart mechanism (exec/spawn)
- [ ] Rollback restore from .bak
- [ ] (Optional) Supervisor with trial window
