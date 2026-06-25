#!/usr/bin/env bash
#
# BotSkills — Skill Installer
#
# Usage:
#   ./install.sh <skill-name>     Install a single skill
#   ./install.sh --all            Install all skills
#   ./install.sh --list           List available skills
#   ./install.sh --update         Update skills.json & README index
#
# Options:
#   --target <dir>                Target directory (default: ~/.trae/skills)
#   --remote                      Install from GitHub without cloning (uses sparse-checkout)
#
# Examples:
#   ./install.sh rclone                                    # Install rclone locally
#   ./install.sh rclone --target ./my-project/.trae/skills # Install to specific dir
#   curl -fsSL https://raw.githubusercontent.com/siciyuan404/BotSkills/main/install.sh | bash -s rclone --remote
#
set -euo pipefail

REPO_OWNER="siciyuan404"
REPO_NAME="BotSkills"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
RAW_BASE="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main"
DEFAULT_TARGET="${HOME}/.trae/skills"

# ── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC}  $*" >&2; }

# ── Parse args ──────────────────────────────────────────
ACTION=""
SKILL_NAME=""
TARGET=""
REMOTE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)   ACTION="list"; shift ;;
    --all)    ACTION="all"; shift ;;
    --update) ACTION="update"; shift ;;
    --remote) REMOTE=true; shift ;;
    --target) TARGET="$2"; shift 2 ;;
    -h|--help)
      sed -n '3,20p' "$0" 2>/dev/null || true
      exit 0 ;;
    -*) error "Unknown option: $1"; exit 1 ;;
    *)  SKILL_NAME="$1"; ACTION="install"; shift ;;
  esac
done

[[ -z "$TARGET" ]] && TARGET="$DEFAULT_TARGET"

# ── Resolve script root (for local mode) ────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"

# ── Get available skills from skills.json ───────────────
get_skills_json() {
  if [[ "$REMOTE" == true ]]; then
    curl -fsSL "${RAW_BASE}/skills.json" 2>/dev/null
  else
    cat "${SCRIPT_DIR}/skills.json" 2>/dev/null
  fi
}

list_skills() {
  local json
  json=$(get_skills_json) || { error "无法读取 skills.json"; exit 1; }
  echo -e "\n${BLUE}BotSkills — 可用 Skills${NC}\n"
  echo -e "  NAME                  DESCRIPTION"
  echo -e "  ────                  ────────────"
  echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data.get('skills', []):
    name = s['name'].ljust(20)
    desc = s.get('description', '')[:60]
    print(f'  {name}  {desc}')
print(f\"\n  共 {len(data.get('skills', []))} 个 skill\")
" 2>/dev/null || echo "$json"
  echo ""
}

# ── Install a single skill ──────────────────────────────
install_skill() {
  local name="$1"
  local json
  json=$(get_skills_json) || { error "无法读取 skills.json"; exit 1; }

  # Validate skill exists
  local found
  found=$(echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
names = [s['name'] for s in data.get('skills', [])]
print('yes' if '$name' in names else 'no')
" 2>/dev/null)

  if [[ "$found" != "yes" ]]; then
    error "Skill '$name' 不存在。运行 --list 查看可用列表。"
    exit 1
  fi

  # Check dependencies
  local deps
  deps=$(echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data.get('skills', []):
    if s['name'] == '$name':
        for d in s.get('dependencies', []):
            print(d)
" 2>/dev/null)

  if [[ -n "$deps" ]]; then
    for dep in $deps; do
      if ! command -v "$dep" &>/dev/null; then
        warn "依赖 '$dep' 未安装,该 skill 可能无法正常工作。"
      fi
    done
  fi

  mkdir -p "$TARGET"

  if [[ "$REMOTE" == true ]]; then
    # Remote mode: sparse-checkout from GitHub
    local tmpdir
    tmpdir=$(mktemp -d)
    info "从 GitHub 拉取 skill '$name'..."
    git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" "$tmpdir" 2>/dev/null
    cd "$tmpdir"
    git sparse-checkout set "$name"
    if [[ -d "$name" ]]; then
      cp -r "$name" "$TARGET/$name"
      ok "已安装 '$name' → $TARGET/$name"
    else
      error "sparse-checkout 未找到目录 '$name'"
      rm -rf "$tmpdir"
      exit 1
    fi
    rm -rf "$tmpdir"
  else
    # Local mode: copy from repo
    if [[ -d "${SCRIPT_DIR}/${name}" ]]; then
      cp -r "${SCRIPT_DIR}/${name}" "$TARGET/$name"
      ok "已安装 '$name' → $TARGET/$name"
    else
      error "本地未找到 skill 目录 '${SCRIPT_DIR}/${name}'"
      exit 1
    fi
  fi
}

# ── Install all skills ──────────────────────────────────
install_all() {
  local json
  json=$(get_skills_json) || { error "无法读取 skills.json"; exit 1; }

  local names
  names=$(echo "$json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for s in data.get('skills', []):
    print(s['name'])
" 2>/dev/null)

  for name in $names; do
    install_skill "$name" || warn "安装 '$name' 失败,跳过。"
  done
  ok "全部安装完成 → $TARGET"
}

# ── Main ────────────────────────────────────────────────
case "$ACTION" in
  list)    list_skills ;;
  install) install_skill "$SKILL_NAME" ;;
  all)     install_all ;;
  update)  python3 "${SCRIPT_DIR}/scripts/generate-index.py" "${SCRIPT_DIR}" ;;
  *)
    error "未指定操作。用法: ./install.sh <skill-name> | --all | --list | --update"
    exit 1
    ;;
esac
