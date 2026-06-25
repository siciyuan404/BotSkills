---
name: environment-setup
description: >
  Sub-Skill for provisioning the Flutter development environment and gh CLI.
  Route here when Flutter SDK or gh CLI is not installed, or needs version
  verification. Inherits all constraints from flutter-gh-starter; adds download
  (with China mirror fallback), extraction, PATH configuration, git safe.directory
  fix, and flutter doctor validation.
---

## 0. Relationship to Parent

Inherits all constraints from `flutter-gh-starter` (security, testing, error
recovery, China mirror strategy). This reference adds environment-provisioning
specifics.

***

## 1. Check Existing State

Before installing anything, verify what is already present:

```bash
flutter --version 2>/dev/null && echo "FLUTTER_OK" || echo "FLUTTER_MISSING"
gh --version 2>/dev/null && echo "GH_OK" || echo "GH_MISSING"
git --version 2>/dev/null && echo "GIT_OK" || echo "GIT_MISSING"
```

- If all three report OK, skip this reference entirely.
- If only Git is present, install Flutter and gh CLI.
- Proceed to the relevant section below.

***

## 2. Install gh CLI

### 2.1 Preferred: Standalone Binary from GitHub Releases

Ubuntu apt mirrors (`archive.ubuntu.com`, `cli.github.com`) are often unreachable
in sandboxed environments. Download the standalone binary directly from GitHub:

```bash
# 1. Get the latest release tag
LATEST=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
# e.g. v2.95.0

# 2. Download and extract
cd /tmp
curl -fL --progress-bar -o gh.tar.gz \
  "https://github.com/cli/cli/releases/download/${LATEST}/gh_${LATEST#v}_linux_amd64.tar.gz"
tar xzf gh.tar.gz

# 3. Install
sudo cp "gh_${LATEST#v}_linux_amd64/bin/gh" /usr/local/bin/gh
sudo chmod +x /usr/local/bin/gh

# 4. Verify
gh --version
```

### 2.2 Fallback: apt (only if GitHub is unreachable)

```bash
type -p curl >/dev/null || (sudo apt-get update && sudo apt-get install -y curl)
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
  | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list
sudo apt-get update && sudo apt-get install -y gh
```

### 2.3 Verify GitHub Reachability

Before proceeding, confirm GitHub endpoints are reachable:

```bash
curl -fsS -m 12 -o /dev/null -w "%{http_code}" https://github.com   # expect 200
curl -fsS -m 12 -o /dev/null -w "%{http_code}" https://api.github.com  # expect 200
```

***

## 3. Install Flutter SDK

### 3.1 Determine Latest Stable Version

```bash
curl -fsSL https://storage.googleapis.com/flutter_infra_release/releases/releases_linux.json \
  | python3 -c "import sys,json; d=json.load(sys.stdin); c=d['current_release']['stable']; \
  r=[x for x in d['releases'] if x['hash']==c][0]; print(r['version']); print(r['archive'])"
```

### 3.2 China Mirror Speed Test

Test whether the China mirror is significantly faster before downloading the
full SDK (~1.5 GB):

```bash
# Test Google Storage (default)
curl -fsS -m 10 -r 0-5000000 -o /dev/null -w "Google: %{speed_download} B/s\n" \
  https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_<VER>-stable.tar.xz

# Test China mirror
curl -fsS -m 10 -r 0-5000000 -o /dev/null -w "Mirror: %{speed_download} B/s\n" \
  https://storage.flutter-io.cn/flutter_infra_release/releases/stable/linux/flutter_linux_<VER>-stable.tar.xz
```

**Decision rule**: if the mirror is >5× faster, use it. In China-network
environments the mirror is typically 50–100× faster.

### 3.3 Download & Extract

```bash
# Set mirror env vars (persistent — add to ~/.zshrc)
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
export PUB_HOSTED_URL=https://pub.flutter-io.cn

# Download (use the faster source determined above)
cd /tmp
curl -fL --progress-bar -o flutter_sdk.tar.xz \
  "https://storage.flutter-io.cn/flutter_infra_release/releases/stable/linux/flutter_linux_<VER>-stable.tar.xz"

# Extract to /opt
cd /opt && tar xf /tmp/flutter_sdk.tar.xz

# Create system symlinks
sudo ln -sf /opt/flutter/bin/flutter /usr/local/bin/flutter
sudo ln -sf /opt/flutter/bin/dart /usr/local/bin/dart
```

### 3.4 Fix "dubious ownership"

When the SDK is extracted by a different user than the one running git
(common in sandboxed environments), Flutter's internal git operations fail:

```bash
git config --global --add safe.directory /opt/flutter
git config --global --add safe.directory '*'
```

### 3.5 Make Mirror Config Persistent

```bash
# Add to ~/.zshrc (or ~/.bashrc)
echo 'export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn' >> ~/.zshrc
echo 'export PUB_HOSTED_URL=https://pub.flutter-io.cn' >> ~/.zshrc
```

### 3.6 Verify

```bash
flutter --version
# Should print: Flutter <version> • channel stable • ...
#                Dart <version> • DevTools <version>
```

***

## 4. Post-Install Validation Checklist

| Check | Command | Expected |
| ----- | ------- | -------- |
| Flutter installed | `flutter --version` | Prints version + channel stable |
| Dart available | `dart --version` | Prints Dart version |
| gh CLI installed | `gh --version` | Prints gh version |
| Git available | `git --version` | Prints git version |
| Mirror configured | `echo $FLUTTER_STORAGE_BASE_URL` | Prints mirror URL |
| safe.directory set | `git config --global --get-all safe.directory` | Contains `/opt/flutter` |

If all checks pass, proceed to `references/project-bootstrap.md`.
