---
name: github-management
description: >
  Sub-Skill for managing a Flutter project on GitHub via gh CLI. Route here when
  authenticating with GitHub, creating a repository, configuring git credential
  helper, pushing code, and troubleshooting auth errors (401/403). Inherits all
  constraints from flutter-gh-starter; adds token type guidance, credential
  helper configuration, repo creation, push verification, and a full
  troubleshooting matrix.
---

## 0. Relationship to Parent

Inherits all constraints from `flutter-gh-starter` (security, testing, error
recovery, token handling). This reference adds GitHub-specific operations and
troubleshooting.

***

## 1. Authenticate with gh CLI

### 1.1 Token Requirements

GitHub offers two token types. **Token type matters for git push.**

| Token Type | How to Create | Required Scope | Git Push Works? |
| ---------- | ------------- | -------------- | --------------- |
| Classic PAT | Settings → Developer settings → Personal access tokens → Tokens (classic) | `repo` (full) | ✅ Yes |
| Fine-grained PAT | Settings → Developer settings → Personal access tokens → Fine-grained tokens | Repository permissions → **Contents: Read and write** | ✅ Yes (if Contents is set) |

> **CRITICAL**: A fine-grained PAT without `Contents: Read and write` can call
> the REST API (e.g. create issues) but **cannot git push** — it returns 403
> "Permission denied". Always verify the token can push before reporting
> success.

### 1.2 Login via stdin (never echo token)

```bash
# Pipe token via stdin — does not write to shell history
printf '%s' "<TOKEN>" | gh auth login --with-token
```

### 1.3 Verify Authentication

```bash
gh auth status   # Should show "✓ Logged in to github.com account <username>"
gh api user --jq '.login'   # Should print the username
```

### 1.4 Check Token Scopes (for debugging)

```bash
# Inspect X-OAuth-Scopes header (classic PAT only — fine-grained returns empty)
curl -fsSI -H "Authorization: token <TOKEN>" https://api.github.com/user \
  | grep -i "oauth-scopes\|scope"
```

For fine-grained PATs, check repository permissions via API:

```bash
curl -fsS -H "Authorization: token <TOKEN>" \
  https://api.github.com/repos/<owner>/<repo> \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('permissions:', d.get('permissions'))"
```

> **Note**: API-reported `permissions` show the token's effective permissions on
> that repo, but a fine-grained PAT's permissions are set at token-creation time.
> Even if the API shows `push: true`, the token may lack the underlying
> `Contents: write` grant needed for git operations. When in doubt, use a
> Classic PAT with `repo` scope.

***

## 2. Configure Git Credential Helper

### 2.1 Standard Setup

```bash
gh auth setup-git
```

This configures git to use `gh auth git-credential` as the credential helper for
`github.com` and `gist.github.com`.

### 2.2 Fix Duplicate Credential Helper Entries

If `gh auth setup-git` is run multiple times, `.gitconfig` may accumulate
duplicate `credential.https://github.com.helper` entries (including empty ones),
causing auth failures. Clean up:

```bash
git config --global --unset-all credential.https://github.com.helper 2>/dev/null
git config --global --unset-all credential.https://gist.github.com.helper 2>/dev/null
gh auth setup-git
```

Verify only the `gh` helper remains:

```bash
git config --list --show-origin | grep credential
# Expected: exactly one entry per domain, pointing to gh auth git-credential
```

### 2.3 Configure Git Identity

```bash
git config --global user.name "<github_username>"
git config --global user.email "<github_username>@users.noreply.github.com"
```

> Using `<username>@users.noreply.github.com` ensures commits are properly
> attributed to the GitHub account without exposing a real email.

***

## 3. Create Repository & Push

### 3.1 Create and Push in One Command

```bash
cd <project_dir>

gh repo create <repo-name> \
  --public \                    # or --private
  --source=. \
  --remote=origin \
  --description "<description>" \
  --push
```

### 3.2 Verify Remote State

```bash
gh repo view <owner>/<repo-name> \
  --json name,visibility,url,description,defaultBranchRef
# Expected: visibility: "PUBLIC" (or PRIVATE), defaultBranchRef.name: "main"
```

***

## 4. Subsequent Pushes

After the initial push, for follow-up commits (e.g. adding features, updating
config):

```bash
cd <project_dir>
git add -A
git commit -m "<message>"
git push origin main
```

If push fails with auth errors, see §5 Troubleshooting.

***

## 5. Troubleshooting Matrix

| Error | Cause | Fix |
| ----- | ----- | --- |
| `HTTP 401: Bad credentials` | Token invalid or revoked | Generate a new token; re-run `gh auth login --with-token` |
| `HTTP 403: Permission denied` (git push) | Fine-grained PAT lacks `Contents: Read and write` | Use Classic PAT with `repo` scope, or edit fine-grained PAT to add Contents: Read and write |
| `HTTP 403: Permission denied` but API works | Credential helper conflict or wrong token cached | Clean duplicate credential helpers (§2.2); ensure `~/.secrets` has the correct token |
| `could not read Username for 'https://github.com'` | No credential helper configured | Run `gh auth setup-git` |
| `fatal: detected dubious ownership` | Flutter SDK git owned by different user | `git config --global --add safe.directory /opt/flutter` |
| `remote: invalid credentials` via `http.extraHeader` | Token not accepted as Basic auth header | Use credential helper (`gh auth setup-git`) instead of extraHeader |
| Token works for API but not git push | Fine-grained PAT has API scope but not Contents write | Regenerate token with correct scopes (§1.1) |
| Duplicate `credential.helper` entries | `gh auth setup-git` run multiple times | `git config --global --unset-all` then re-run setup (§2.2) |

### 5.1 Diagnostic Procedure

When push fails, run these in order to isolate the issue:

```bash
# 1. Is the token valid?
gh auth status
gh api user --jq '.login'

# 2. Can the token write to the repo via API?
curl -fsS -H "Authorization: token <TOKEN>" \
  -X POST -d '{"title":"test","body":"permission test"}' \
  https://api.github.com/repos/<owner>/<repo>/issues
# If this succeeds but git push fails → token type / Contents scope issue

# 3. Are credential helpers clean?
git config --list --show-origin | grep credential
# Look for duplicate or empty entries

# 4. Is the remote URL clean (no embedded credentials)?
git remote -v
# Should show: https://github.com/<owner>/<repo>.git (no token in URL)
```

***

## 6. Token Security Reminders

- **Never paste tokens in conversation** if avoidable. Prefer `~/.secrets`.
- If a token was pasted in chat, remind the user to **revoke it** at
  https://github.com/settings/tokens after use.
- After completing all pushes, suggest the user rotate/revokes the token.
- Verify `.env` and `*.secrets` are gitignored before every commit:
  `git check-ignore .env && echo "OK"`
