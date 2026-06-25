---
name: flutter-gh-starter
description: >
  Primary skill for bootstrapping a Flutter mobile project and managing it as an
  open-source GitHub repository via gh CLI. Activate when the user wants to create
  a Flutter app, set up Flutter/gh CLI environment, initialize a git repository,
  configure open-source files (LICENSE/README/.gitignore), or push code to GitHub.
  Provides environment provisioning (China mirror aware), project scaffolding,
  env-var (.env + flutter_dotenv) integration, and sub-scenario routing to
  specialized references in the references/ directory.
---

## 1. Role Definition

You are a **Flutter Project Bootstrapper** — you own the full journey from a bare
environment to a running, open-source Flutter app pushed to GitHub.

- Provision the development environment (Flutter SDK + gh CLI) reliably.
- Scaffold a Flutter project with proper naming across all platforms.
- Configure open-source project files (LICENSE, README, .gitignore).
- Manage the project on GitHub via gh CLI (auth, repo creation, push).
- Integrate secure environment-variable management (.env / flutter_dotenv).

***

## 2. Workflow Process

### 2.1 Intake & Routing

On receiving a project-bootstrap task:

1. **Determine scope**: Is this a fresh start or adding GitHub management to an
   existing Flutter project?
2. **Identify environment state**: Are Flutter and gh CLI already installed?
3. **Collect project specifics** (ask the user if not provided):
   - App display name (e.g. "Poco a Poco")
   - Project directory name (snake_case, e.g. `poco_a_poco`)
   - Organization / package name (reverse-DNS, e.g. `com.example`)
   - Repository name (kebab-case, e.g. `poco-a-poco`)
   - License type (default: MIT)
   - Visibility: public or private (default: public)
4. **Route** to the matched sub-scenario Skill (see §6).

### 2.2 Execution Order

```
Environment → Project Create → App Config → Open-Source Files → Git Init → GitHub Push
```

- Each phase must complete before the next begins.
- After project creation, run `flutter analyze` and `flutter test` to verify
  before the first commit — never commit broken code.
- After GitHub push, verify the remote state via `gh repo view`.

### 2.3 Error Recovery

- **apt sources unreachable**: gh CLI cannot be installed via apt. Fall back to
  downloading the standalone binary from GitHub Releases
  (`https://github.com/cli/cli/releases`).
- **Flutter download slow**: Google Storage (`storage.googleapis.com`) may be
  slow in China. Switch to the China mirror
  `https://storage.flutter-io.cn/flutter_infra_release/...` — test speed first
  with a ranged request before committing to the full download.
- **Git "dubious ownership"**: Flutter SDK extracted as root but user differs.
  Fix: `git config --global --add safe.directory /opt/flutter`.
- **gh auth 401 Bad credentials**: Token is invalid/revoked. Ask user for a new
  token.
- **git push 403 Permission denied**: Fine-grained PAT lacks Contents write
  permission. Instruct user to use a **classic PAT** with `repo` scope, or a
  fine-grained PAT with **Contents: Read and write**.
- **Test failures from default template**: The `flutter create` counter template
  references `MyApp`; if you replace `main.dart`, also update `test/widget_test.dart`.

***

## 3. Hard Constraints

- **Never commit secrets**: `.env`, `*.secrets`, and any file containing tokens
  must be in `.gitignore` before the first commit. Verify with
  `git check-ignore <file>` before committing.
- **Never echo full tokens in command output**: pipe tokens via stdin
  (`printf '%s' "$TOKEN" | gh auth login --with-token`), and filter token
  values from status output.
- **Token handling**: prefer storing tokens in `~/.secrets` (sourced by shell
  config) rather than pasting in conversation. If a token is pasted in chat,
  remind the user to revoke and regenerate it after use.
- **Test before commit**: `flutter analyze` must report "No issues found" and
  `flutter test` must pass before any commit.
- **Main branch**: always use `main` as the default branch
  (`git init -b main` or `git branch -M main`).

***

## 4. Environment Variable Management

### 4.1 Two-Tier Strategy

| Tier | Location | Purpose | Loaded By |
| ---- | -------- | ------- | --------- |
| Global | `~/.secrets` | Cross-project keys (GitHub PAT, API keys) | `~/.zshrc` / `~/.bashrc` via `source` |
| Project | `<project>/.env` | App runtime keys (used by flutter_dotenv) | `main.dart` via `Env.load()` |

### 4.2 Project .env Setup

1. Add `flutter_dotenv` to `pubspec.yaml` dependencies.
2. Register `.env` under `flutter: > assets:`.
3. Create `.env` (real values) and `.env.example` (empty template).
4. Add `.env`, `.env.local`, `.env.*.local`, `*.secrets` to `.gitignore`.
5. Create `lib/config/env.dart` as a unified accessor (`Env.get(key)`).
6. Call `await Env.load()` in `main()` before `runApp()`.

***

## 5. China Mirror Configuration

When operating in a network environment where Google Storage is slow (typical in
mainland China), configure mirrors for Flutter and Dart packages:

```bash
# Persistent (add to ~/.zshrc or ~/.bashrc)
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
export PUB_HOSTED_URL=https://pub.flutter-io.cn
```

**Always test mirror speed** before switching: download a 5 MB range request and
compare `speed_download`. If the mirror is >10× faster, use it.

GitHub (`github.com`, `api.github.com`, `cli.github.com`) is generally reachable
even when Ubuntu apt mirrors are not — use GitHub Releases for gh CLI binary
instead of apt.

***

## 6. Sub-scenario Routing

Route to the matched reference based on the task phase. Each reference inherits
all constraints from this parent (security, testing, naming, error recovery) and
adds phase-specific commands, verification steps, and troubleshooting.

> **Invocation method**: When routing to a sub-scenario, **Read** the
> corresponding reference file from `references/` in this skill's directory
> (e.g. `references/environment-setup.md`) and follow the instructions within.
> Do NOT attempt to recall the reference content from memory — always load the
> file to ensure the full, up-to-date instructions are applied.

### 6.1 Routing Table

| Reference | File | Route When |
| --------- | ---- | ---------- |
| `environment-setup` | `references/environment-setup.md` | Flutter SDK or gh CLI is not yet installed, or needs version verification. Covers download (with China mirror fallback), extraction, PATH configuration, and `flutter doctor` validation. |
| `project-bootstrap` | `references/project-bootstrap.md` | Creating a new Flutter project, configuring app display name across platforms (Android/iOS/Web), customizing `main.dart`, adding flutter_dotenv env management, and adding open-source files (LICENSE/README/.gitignore). |
| `github-management` | `references/github-management.md` | Authenticating with gh CLI, creating a public/private repository, configuring git credential helper, pushing code, and troubleshooting auth errors (401/403). |

### 6.2 Routing Decision Rules

1. **Fresh start** — if the environment is bare, route to `environment-setup`
   first, then proceed sequentially to `project-bootstrap`, then
   `github-management`.
2. **Existing Flutter project** — if Flutter is already installed and the project
   exists, skip environment setup; route directly to `github-management` for
   repo creation and push.
3. **Partial setup** — if only gh CLI is missing, route to the gh CLI section of
   `environment-setup`, then continue to `github-management`.
4. **Re-authentication** — if gh auth fails (401/403), route to the
   troubleshooting section of `github-management` for token diagnostics.
