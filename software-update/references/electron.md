# Electron Update Patterns

This reference maps the architecture from SKILL.md to Electron's ecosystem.

## State Machine

Use the **main process** as the source of truth. The renderer subscribes via
IPC and re-syncs on mount.

```
Main process:
  - Holds the AppUpdateState (in a simple variable or a store)
  - Runs the download in a background task (not tied to any BrowserWindow)
  - Sends IPC events to all windows on every state transition

Renderer:
  - On mount: ipcRenderer.on('app-update-state', handler) then ipcRenderer.invoke('get-app-update-state')
  - Unsubscribe on unmount with ipcRenderer.removeListener
```

### Subscribe-then-fetch pattern in Electron

```typescript
// Renderer — mount
ipcRenderer.on('app-update-state', (_event, state: AppUpdateState) => {
  if (state.seq > latestSeq) {
    latestSeq = state.seq
    updateUI(state)
  }
})
const snapshot = await ipcRenderer.invoke('get-app-update-state')
if (snapshot.seq > latestSeq) {
  latestSeq = snapshot.seq
  updateUI(snapshot)
}
```

## electron-updater Configuration

`electron-updater` (part of `electron-builder`) handles most of the download
and install mechanics. Your job is to wrap it with the state machine pattern.

```typescript
// main.ts
import { autoUpdater } from 'electron-updater'

let appUpdateState: AppUpdateState = { seq: 0, status: 'idle' }

// Wire up electron-updater events to your state machine
autoUpdater.on('checking-for-update', () => {
  // transitioning to checking state — emit event
})

autoUpdater.on('update-available', (info) => {
  // info.version is available — show "Upgrade to vX" button
})

autoUpdater.on('download-progress', (progress) => {
  appUpdateState = {
    seq: appUpdateState.seq + 1,
    status: 'downloading',
    downloaded: progress.transferred,
    total: progress.total,
  }
  broadcastToAllWindows('app-update-state', appUpdateState)
})

autoUpdater.on('update-downloaded', (info) => {
  appUpdateState = {
    seq: appUpdateState.seq + 1,
    status: 'ready_to_restart',
    version: info.version,
  }
  broadcastToAllWindows('app-update-state', appUpdateState)
})

autoUpdater.on('error', (error) => {
  appUpdateState = {
    seq: appUpdateState.seq + 1,
    status: 'error',
    error: error.message,
  }
  broadcastToAllWindows('app-update-state', appUpdateState)
})
```

### Concurrency for electron-updater

`electron-updater` internally serializes check/download/install, so the
concurrency patterns from SKILL.md §2 are mostly handled for you. You still
need to guard the user action layer:

```typescript
let updateInProgress = false

async function handleCheckUpdate() {
  if (updateInProgress) return  // second click is a no-op
  updateInProgress = true
  try {
    await autoUpdater.checkForUpdates()
  } finally {
    updateInProgress = false
  }
}

// For install: only call quitAndInstall from ReadyToRestart
async function handleRestart() {
  if (appUpdateState.status !== 'ready_to_restart') return
  appUpdateState = { seq: appUpdateState.seq + 1, status: 'restarting' }
  broadcastToAllWindows('app-update-state', appUpdateState)
  autoUpdater.quitAndInstall()
}
```

## Platform-Specific Notes

### macOS

- Code signing is **required** for auto-update. Without a valid developer
  certificate, `electron-updater` will refuse to install.
- DMG is the simplest format; `electron-builder` supports it natively.
- For MAS (Mac App Store) builds, updates go through the App Store — disable
  `electron-updater` entirely in that build variant.

### Windows

- NSIS installer is the most common choice.
- The installer must run elevated (admin) if the app is installed in
  `Program Files`. `electron-builder` handles this with the `runAfterFinish`
  option.
- If using a portable (no-installer) build, you need custom update logic since
  `electron-updater` assumes an installed app.

### Linux

- AppImage is the simplest self-updating format. `electron-updater` supports
  AppImage delta updates.
- Snap and Flatpak have their own update channels — disable
  `electron-updater` for those and let the store handle it.
- deb/rpm packages typically rely on the system package manager, not in-app
  updates.

## Release Distribution

### GitHub Releases (via electron-builder)

```json
// package.json
"build": {
  "publish": [{
    "provider": "github",
    "owner": "your-org",
    "repo": "your-repo"
  }]
}
```

The `latest.yml` (Windows/macOS) or `latest-linux.yml` manifest is generated
automatically by `electron-builder` during the publish step. `electron-updater`
reads it to determine if an update is available.

### Custom server

```json
"build": {
  "publish": [{
    "provider": "generic",
    "url": "https://releases.example.com/download/"
  }]
}
```

Serve the `latest.yml` file and all installer artifacts from the same
directory. You must generate `latest.yml` yourself (its format is documented in
the `electron-builder` source).

## Rollback

`electron-updater` does not provide built-in rollback. The next launch of the
app will be the updated version, period. If you need rollback:

- Keep a copy of the old `app.asar` or the old installer before the swap.
- On launch, check for a rollback marker file. If present, restore the old
  files before the app initializes.
- This is significantly more work in Electron than in a server/docker context
  because there is no supervisor to mediate.

For most Electron apps, rollback is not worth the complexity — the user can
always re-download the previous version manually. Focus on making the update
itself reliable (test thoroughly, use staged rollouts with
`electron-updater`'s `allowDowngrade` option for emergency rollbacks).

## UI Patterns (Renderer)

Since Electron renderers are essentially web pages, the UI patterns from
SKILL.md §9 apply directly. A few Electron-specific notes:

- Use `BrowserWindow`'s `'ready-to-show'` event to avoid flashing before the
  UI is painted.
- For the status bar, consider a `Tray` icon with a badge count or a subtle
  overlay on the main window's title bar.
- `ipcRenderer.invoke` returns a Promise, which maps naturally to the
  `Transport.call()` abstraction.

## Checklist for Electron

- [ ] `electron-updater` configured with a publish provider
- [ ] Code signing set up (required for macOS, recommended for Windows)
- [ ] State machine in main process, UI subscribed via IPC
- [ ] Subscribe-then-fetch on renderer mount
- [ ] Global status bar / tray indicator
- [ ] Settings page with "Check for Updates", progress, "Restart to Update"
- [ ] `quitAndInstall()` only callable from `ready_to_restart` state
- [ ] Error classification and display
- [ ] Platform-specific builds: disable updater for App Store / Snap / Flatpak variants
