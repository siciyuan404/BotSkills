---
name: project-bootstrap
description: >
  Sub-Skill for creating a Flutter project and configuring it for open-source
  release. Route here when scaffolding a new app, setting display names across
  platforms, customizing main.dart, integrating flutter_dotenv env management,
  and adding LICENSE/README/.gitignore. Inherits all constraints from
  flutter-gh-starter; adds project-creation commands, platform config edits,
  env integration steps, and verification gates.
---

## 0. Relationship to Parent

Inherits all constraints from `flutter-gh-starter` (security, testing, error
recovery, China mirror strategy). This reference adds project-scaffolding and
configuration specifics.

***

## 1. Create the Flutter Project

### 1.1 Collect Parameters

Gather these from the user before running `flutter create`:

| Parameter | Format | Example |
| --------- | ------ | ------- |
| App display name | Title Case, spaces allowed | `Poco a Poco` |
| Project directory name | snake_case | `poco_a_poco` |
| Organization (reverse-DNS) | lower.case.dots | `com.pocoapoco` |
| App description | Short sentence | `循序渐进学西语的移动应用` |

### 1.2 Run flutter create

```bash
export FLUTTER_STORAGE_BASE_URL=https://storage.flutter-io.cn
export PUB_HOSTED_URL=https://pub.flutter-io.cn

flutter create \
  --org <org> \
  --project-name <dir_name> \
  --description "<description>" \
  <dir_name>
```

> The `--org` flag sets the Android package name and iOS bundle identifier
> prefix (e.g. `com.pocoapoco.poco_a_poco`).

### 1.3 Ignore Java/Gradle Warning

If a Java/Gradle version mismatch warning appears during creation, it does not
affect project structure. Note it for the user but proceed — it only matters
when building for Android.

***

## 2. Configure App Display Name

The `flutter create` template uses the project name as the display name. Update
it across all platforms to match the user's chosen display name.

### 2.1 Android

File: `android/app/src/main/AndroidManifest.xml`

```xml
<!-- Change android:label from project name to display name -->
android:label="<Display Name>"
```

### 2.2 iOS

File: `ios/Runner/Info.plist`

```xml
<key>CFBundleDisplayName</key>
<string><Display Name></string>

<key>CFBundleName</key>
<string><Display Name></string>
```

> The template may set `CFBundleDisplayName` to a Title-Case variant (e.g.
> `Poco A Poco`). Correct it to the exact desired casing (e.g. `Poco a Poco`).

### 2.3 Web

File: `web/index.html`

```html
<meta name="apple-mobile-web-app-title" content="<Display Name>">
<title><Display Name></title>
```

File: `web/manifest.json`

```json
{
  "name": "<Display Name>",
  "short_name": "<Display Name>"
}
```

### 2.4 Web description (optional)

`flutter create` already writes the `--description` value into `web/index.html`
`<meta name="description">` and `web/manifest.json` `"description"`. Verify these
are correct.

***

## 3. Add Open-Source Files

### 3.1 LICENSE (MIT)

Create `LICENSE` at project root. Use standard MIT text with the current year
and project name:

```
MIT License

Copyright (c) <YEAR> <Project Name> Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
...
```

### 3.2 README.md

Create `README.md` at project root with:
- Project title + one-line tagline
- Badge row (Flutter version, Dart version, License, Platform)
- Project overview
- Feature list (planned features with checkboxes)
- Tech stack table
- Environment requirements
- Quick start (clone, pub get, flutter run)
- China mirror note (if applicable)
- Project structure tree
- Testing instructions
- Roadmap (checkboxes)
- Contributing guide
- License link

### 3.3 .gitignore

The `flutter create` template already includes a comprehensive `.gitignore`.
**Append** secret-related entries at the top (before the existing content):

```gitignore
# Environment & secrets
.env
.env.local
.env.*.local
*.secrets
```

### 3.4 .env.example

Create `.env.example` as a safe-to-commit template with empty values:

```env
# Copy to .env and fill with real values
API_KEY=
API_BASE_URL=https://api.example.com
```

***

## 4. Integrate flutter_dotenv (Environment Variables)

### 4.1 Add Dependency

In `pubspec.yaml`, under `dependencies:`:

```yaml
dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.8
  flutter_dotenv: ^5.2.1
```

### 4.2 Register .env as Asset

In `pubspec.yaml`, under `flutter:`:

```yaml
flutter:
  uses-material-design: true
  assets:
    - .env
```

### 4.3 Create .env File

```env
# <Project>/.env — local secrets (gitignored, never committed)
API_KEY=your_real_key_here
API_BASE_URL=https://api.example.com
```

### 4.4 Create Env Accessor

Create `lib/config/env.dart`:

```dart
import 'package:flutter_dotenv/flutter_dotenv.dart';

class Env {
  Env._();

  static Future<void> load() async {
    await dotenv.load(fileName: '.env');
  }

  static String get(String key, {String fallback = ''}) {
    return dotenv.env[key] ?? fallback;
  }

  static bool has(String key) => dotenv.env.containsKey(key);
}
```

### 4.5 Update main.dart

```dart
import 'package:flutter/material.dart';
import 'config/env.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Env.load();
  runApp(const MyApp());
}
```

### 4.6 Set Up Global Secrets (Optional)

For cross-project keys (GitHub PAT, etc.), create `~/.secrets`:

```bash
cat > ~/.secrets << 'EOF'
export GH_TOKEN="<your_token>"
export GITHUB_TOKEN="$GH_TOKEN"
EOF
```

Add to `~/.zshrc` (or `~/.bashrc`):

```bash
[[ -f ~/.secrets ]] && source ~/.secrets
```

***

## 5. Verification Gate

Before the first git commit, ALL of the following must pass:

```bash
# 1. Dependencies resolved
flutter pub get

# 2. Static analysis clean
flutter analyze
# Expected: "No issues found!"

# 3. Tests pass
flutter test
# Expected: "All tests passed!"

# 4. .env is gitignored
git check-ignore .env
# Expected: prints ".env"

# 5. No secrets in staging area
git add -A && git status --short | grep -iE "\.env$|secret|token" || echo "CLEAN"
```

> **IMPORTANT**: If you replaced the default `main.dart`, the template test
> (`test/widget_test.dart`) still references `MyApp`. Update the test to match
> your new app class name, or it will fail.

***

## 6. Naming Conventions Reference

| Element | Convention | Example |
| ------- | ---------- | ------- |
| Project directory | snake_case | `poco_a_poco` |
| Dart package name | snake_case | `poco_a_poco` |
| App display name | Natural Title | `Poco a Poco` |
| Android label | Natural Title | `Poco a Poco` |
| iOS bundle display | Natural Title | `Poco a Poco` |
| GitHub repo name | kebab-case | `poco-a-poco` |
| Organization | reverse-DNS | `com.pocoapoco` |
| Git default branch | `main` | `main` |

After all checks pass, proceed to `references/github-management.md`.
