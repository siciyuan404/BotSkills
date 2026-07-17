# Tauri Update Patterns

This reference maps the architecture from SKILL.md to Tauri's ecosystem.

## State Machine

Tauri splits state across two processes: the **Rust backend** (holds the state)
and the **webview frontend** (subscribes to it).

```
Rust (src-tauri/src/):
  - AppUpdateState struct behind Arc<RwLock<...>>
  - Tauri managed state: app.manage(update_state_handle)
  - Commands: check_app_update, perform_app_update, restart_app, get_app_update_state
  - Events: app_update_state (emitted on every transition)

Frontend (src/):
  - Subscribes via listen('app_update_state', handler)
  - Fetchs snapshot via invoke('get_app_update_state')
  - Calls invoke('perform_app_update') to start
```

### Subscribe-then-fetch in Tauri

```typescript
// Frontend — mount
import { listen } from '@tauri-apps/api/event'
import { invoke } from '@tauri-apps/api/core'

let latestSeq = 0

const unlisten = await listen<AppUpdateState>('app_update_state', (event) => {
  if (event.payload.seq >= latestSeq) {
    latestSeq = event.payload.seq
    updateUI(event.payload)
  }
})

const snapshot = await invoke<AppUpdateState>('get_app_update_state')
if (snapshot.seq >= latestSeq) {
  latestSeq = snapshot.seq
  updateUI(snapshot)
}
```

## tauri-plugin-updater

Tauri's official plugin handles the heavy lifting:

```toml
# Cargo.toml (src-tauri)
[dependencies]
tauri-plugin-updater = "2"

# In lib.rs
fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_updater::Builder::new().build())
        .run(tauri::generate_context!())
}
```

```jsonc
// tauri.conf.json
{
  "plugins": {
    "updater": {
      "endpoints": [
        "https://releases.example.com/{{target}}/{{arch}}/{{current_version}}"
      ],
      "pubkey": "BASE64_ENCODED_PUBLIC_KEY",
      "windows": {
        "installMode": "passive"
      }
    }
  }
}
```

### Check + download flow with the plugin

```typescript
import { check } from '@tauri-apps/plugin-updater'

// Check for updates
const update = await check()
if (update) {
  // update.available is true, update.version is the new version

  // Download with progress
  let downloaded = 0
  await update.downloadAndInstall((event) => {
    switch (event.event) {
      case 'Started':
        downloaded = 0
        break
      case 'Progress':
        downloaded += event.data.chunkLength
        // emit progress to state machine
        break
      case 'Finished':
        // download complete, ready to restart
        break
    }
  })
}
```

Use the state machine pattern from SKILL.md on top of the plugin to manage
concurrent clicks, progress survival across navigation, and the
ReadyToRestart → Restarting transition.

## Commands (Rust side)

```rust
use tauri::State;
use std::sync::{Arc, RwLock};
use crate::update::state::{AppUpdateState, AppUpdateStateHandle, APP_UPDATE_STATE_CHANNEL};

#[tauri::command]
async fn get_app_update_state(
    state: State<'_, AppUpdateStateHandle>,
) -> Result<AppUpdateState, String> {
    Ok(state.read().unwrap().clone())
}

// Note: perform_app_update and restart_app can also be driven from the
// TypeScript side via tauri-plugin-updater, but owning the dispatch in Rust
// gives you full control over the state machine transitions.
#[tauri::command]
async fn perform_app_update(
    state: State<'_, AppUpdateStateHandle>,
    app: tauri::AppHandle,
) -> Result<AppUpdateState, String> {
    // 1. try_begin: atomically claim the download slot
    // 2. Spawn background task to download via tauri-plugin-updater
    // 3. On progress: update state, emit event
    // 4. On complete: set_ready, emit event
    // 5. On error: set_error, emit event
    unimplemented!()
}

#[tauri::command]
async fn restart_app(
    state: State<'_, AppUpdateStateHandle>,
    app: tauri::AppHandle,
) -> Result<(), String> {
    // 1. try_claim_restart: only if ReadyToRestart
    // 2. app.restart()
    unimplemented!()
}
```

## When NOT to use the plugin

The plugin works for standard desktop apps distributed via `.msi`/`.dmg`/`.deb`.
You should implement the in-place swap approach from SKILL.md §6 instead when:

- You're shipping a Tauri app as a portable/standalone binary (no installer).
- The app includes auxiliary services (MCP servers, background workers) that
  also need atomic replacement.
- You need rollback capability (the plugin doesn't offer rollback).
- You need a supervised trial window (Docker deployment of the backend).
- Windows server self-update (the plugin is desktop-only).

In these cases, follow the patterns in `desktop-native.md` and
`server-docker.md` for the Rust backend, while keeping the Tauri frontend as
the UI layer.

## Code Signing

### macOS

Without an Apple Developer ID certificate, Tauri's updater will refuse to
install. Set up in `tauri.conf.json`:

```json
{
  "bundle": {
    "macOS": {
      "signingIdentity": "Developer ID Application: Your Name (TEAMID)"
    }
  }
}
```

### Windows

Code signing is not strictly required for the updater to work, but Windows
SmartScreen will flag unsigned binaries. Use Azure Key Vault or a hardware
token with `tauri-signer` during the CI build.

## Release Distribution

Tauri's updater uses a JSON manifest. Generate it with the Tauri CLI:

```bash
npx tauri signer generate -w ~/app.cer --password $TAURI_SIGNING_PASSWORD
```

Then upload the resulting `.sig` files alongside your release assets. The
manifest `latest.json` is usually served from a GitHub Release or your own CDN.

## Tauri + Server Dual Mode

If your Tauri app also runs as a standalone server (like Codeg's dual mode),
the frontend must work with both communication paths. Use the Transport
abstraction from SKILL.md §10:

```typescript
// In Tauri desktop mode: invoke() + listen()
// In server/remote mode: HTTP POST + WebSocket
const transport = isDesktop()
  ? tauriTransport()
  : webTransport(serverUrl)
```

The Rust backend exposes the same commands both as Tauri commands (desktop) and
HTTP endpoints (server mode), so the same frontend code works in both contexts.

## Checklist for Tauri

- [ ] State machine in Rust, behind `Arc<RwLock<AppUpdateState>>`
- [ ] Commands: get, perform, restart
- [ ] Events emitted on every state transition
- [ ] Frontend subscribes then fetches
- [ ] `tauri-plugin-updater` configured (or custom swap for portable builds)
- [ ] Code signing for macOS
- [ ] Settings page + status bar UI
- [ ] Error classification and display
- [ ] Transport abstraction if dual-mode (desktop + server)
