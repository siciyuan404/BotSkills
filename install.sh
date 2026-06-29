#!/usr/bin/env bash
#
# BotSkills — Skill Installer (multi-agent aware)
#
# 自动检测当前环境使用的 AI agent（Claude / TRAE / Cursor / Codex），
# 把 skill 安装到该 agent 真正读取的目录，并接入其注册机制：
#   - Claude / TRAE: ~/.agents/skills/ + ~/.agents/.skill-lock.json + ~/.claude/skills 软链
#   - Cursor:       ~/.cursor/skills/
#   - Codex:        ~/.codex/skills/
#
# Usage:
#   ./install.sh <skill-name>           Install a single skill (auto-detect agent)
#   ./install.sh --all                 Install all skills (auto-detect agent)
#   ./install.sh --list                List available skills
#   ./install.sh --update              Update skills.json & README index
#   ./install.sh --remove <name>       Remove an installed skill + unregister
#   ./install.sh --agents              Show supported agents & detection result
#
# Options:
#   --agent <claude|trae|cursor|codex|all|auto>  Force target agent (default: auto)
#   --target <dir>                Override target directory (skip auto-detection)
#   --remote                      Install from GitHub without cloning (sparse-checkout)
#
# Examples:
#   ./install.sh rclone                              # auto-detect & install
#   ./install.sh rclone --agent cursor              # force cursor
#   ./install.sh rclone --agent all                 # install to every detected agent
#   ./install.sh --all --remote                     # remote install all
#   curl -fsSL https://raw.githubusercontent.com/siciyuan404/BotSkills/main/install.sh | bash -s rclone --remote
#
set -euo pipefail

REPO_OWNER="siciyuan404"
REPO_NAME="BotSkills"
REPO_SOURCE="${REPO_OWNER}/${REPO_NAME}"
REPO_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}.git"
RAW_BASE="https://raw.githubusercontent.com/${REPO_OWNER}/${REPO_NAME}/main"

# ── Colors ───────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${BLUE}ℹ${NC}  $*"; }
ok()    { echo -e "${GREEN}✓${NC}  $*"; }
warn()  { echo -e "${YELLOW}⚠${NC}  $*"; }
error() { echo -e "${RED}✗${NC}  $*" >&2; }

# ── Parse args ──────────────────────────────────────────
ACTION=""
SKILL_NAME=""
TARGET=""
AGENT="auto"
REMOTE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --list)    ACTION="list"; shift ;;
    --all)     ACTION="all"; shift ;;
    --update)  ACTION="update"; shift ;;
    --remove)  ACTION="remove"; shift; [[ $# -gt 0 ]] && SKILL_NAME="$1" && shift ;;
    --agents)  ACTION="agents"; shift ;;
    --remote)  REMOTE=true; shift ;;
    --agent)   AGENT="$2"; shift 2 ;;
    --target)  TARGET="$2"; shift 2 ;;
    -h|--help)
      sed -n '3,40p' "$0" 2>/dev/null || true
      exit 0 ;;
    -*) error "未知选项: $1"; exit 1 ;;
    *)  SKILL_NAME="$1"; ACTION="install"; shift ;;
  esac
done

# ── Resolve script root (for local mode) ────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd)"

# ── Agent directory mapping ─────────────────────────────
# Claude & TRAE 共享 agents 机制：文件落 ~/.agents/skills，注册 ~/.agents/.skill-lock.json，
# Claude 额外建 ~/.claude/skills 软链入口。
agents_dir() {
  case "$1" in
    claude|trae) echo "${HOME}/.agents/skills" ;;
    cursor)      echo "${HOME}/.cursor/skills" ;;
    codex)       echo "${HOME}/.codex/skills" ;;
    *) return 1 ;;
  esac
}
agent_link_dir() {
  case "$1" in
    claude) echo "${HOME}/.claude/skills" ;;
    *) echo "" ;;
  esac
}
agent_lock_file() {
  case "$1" in
    claude|trae) echo "${HOME}/.agents/.skill-lock.json" ;;
    *) echo "" ;;
  esac
}

# 检测某个 agent 是否"存在/活跃"（其宿主目录已建立）
agent_exists() {
  case "$1" in
    claude) [[ -d "${HOME}/.claude" ]] ;;
    trae)   [[ -d "${HOME}/.agents" ]] ;;
    cursor) [[ -d "${HOME}/.cursor" ]] ;;
    codex)  [[ -d "${HOME}/.codex" ]] ;;
    *) return 1 ;;
  esac
}

# auto 模式：返回检测到的 agent 列表（空格分隔）
detect_agents() {
  local found=()
  agent_exists claude && found+=("claude")
  agent_exists trae   && found+=("trae")
  agent_exists cursor && found+=("cursor")
  agent_exists codex  && found+=("codex")
  # 都没检测到 → 默认采用 trae（创建 ~/.agents 机制）
  if [[ ${#found[@]} -eq 0 ]]; then
    found+=("trae")
  fi
  echo "${found[*]}"
}

# 解析实际要安装的 agent 列表
resolve_agents() {
  case "$AGENT" in
    auto) detect_agents ;;
    all)  echo "claude trae cursor codex" ;;
    claude|trae|cursor|codex) echo "$AGENT" ;;
    *) error "未知 agent: $AGENT（支持: claude/trae/cursor/codex/all/auto）"; exit 1 ;;
  esac
}

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

show_agents() {
  echo -e "\n${BLUE}BotSkills — Agent 检测${NC}\n"
  printf "  %-10s %-12s %s\n" "AGENT" "STATUS" "SKILLS DIR"
  printf "  %-10s %-12s %s\n" "─────" "──────" "──────────"
  for a in claude trae cursor codex; do
    local status dir
    if agent_exists "$a"; then status="${GREEN}active${NC}"; else status="${RED}—${NC}"; fi
    dir=$(agents_dir "$a" 2>/dev/null || echo "-")
    echo -e "  ${a}        $(echo -e "$status")   ${dir}"
  done
  echo ""
  info "auto 检测结果: $(detect_agents)"
  echo ""
}

# ── Compute skill folder hash (sha256) via python ───────
compute_folder_hash() {
  local skill_dir="$1"
  python3 - "$skill_dir" <<'PYEOF'
import hashlib, os, sys
path = sys.argv[1]
h = hashlib.sha256()
files = []
for root, _, fs in os.walk(path):
    for f in fs:
        files.append(os.path.join(root, f))
files.sort()
for f in files:
    rel = os.path.relpath(f, path)
    h.update(rel.encode())
    with open(f, 'rb') as fh:
        h.update(fh.read())
print(h.hexdigest())
PYEOF
}

# ── Register skill into agent lock file ─────────────────
register_lock() {
  local agent="$1" name="$2" skill_dir="$3"
  local lock_file
  lock_file=$(agent_lock_file "$agent")
  [[ -z "$lock_file" ]] && return 0

  local folder_hash
  folder_hash=$(compute_folder_hash "$skill_dir")
  mkdir -p "$(dirname "$lock_file")"

  python3 - "$lock_file" "$name" "$folder_hash" "$REPO_SOURCE" "$REPO_URL" <<'PYEOF'
import json, os, sys, datetime
lock_file, name, folder_hash, source, source_url = sys.argv[1:6]
data = {"version": 3, "skills": {}, "dismissed": {}}
if os.path.exists(lock_file):
    try:
        with open(lock_file) as f:
            data = json.load(f)
    except Exception:
        data = {"version": 3, "skills": {}, "dismissed": {}}
data.setdefault("skills", {})
data.setdefault("dismissed", {})
existing = data["skills"].get(name, {})
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
data["skills"][name] = {
    "source": source,
    "sourceType": "github",
    "sourceUrl": source_url,
    "skillPath": f"{name}/SKILL.md",
    "skillFolderHash": folder_hash,
    "installedAt": existing.get("installedAt", now),
    "updatedAt": now,
}
with open(lock_file, "w") as f:
    json.dump(data, f, indent=2)
print(f"✓ 已注册 {name} → {lock_file}")
PYEOF
}

# ── Unregister skill from agent lock file ───────────────
unregister_lock() {
  local agent="$1" name="$2"
  local lock_file
  lock_file=$(agent_lock_file "$agent")
  [[ -z "$lock_file" || ! -f "$lock_file" ]] && return 0

  python3 - "$lock_file" "$name" <<'PYEOF'
import json, os, sys
lock_file, name = sys.argv[1:3]
if not os.path.exists(lock_file):
    sys.exit(0)
with open(lock_file) as f:
    data = json.load(f)
changed = False
if name in data.get("skills", {}):
    del data["skills"][name]
    changed = True
if name in data.get("dismissed", {}):
    del data["dismissed"][name]
    changed = True
if changed:
    with open(lock_file, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✓ 已从 {lock_file} 注销 {name}")
PYEOF
}

# ── Install a single skill to a specific agent ──────────
install_to_agent() {
  local agent="$1" name="$2"
  local target link_dir
  target=$(agents_dir "$agent")
  link_dir=$(agent_link_dir "$agent")

  mkdir -p "$target"

  # 拷贝 skill 文件到 target
  if [[ "$REMOTE" == true ]]; then
    local tmpdir
    tmpdir=$(mktemp -d)
    info "从 GitHub 拉取 skill '$name'..."
    git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" "$tmpdir" 2>/dev/null
    (cd "$tmpdir" && git sparse-checkout set "$name")
    if [[ -d "$tmpdir/$name" ]]; then
      rm -rf "${target:?}/$name"
      cp -r "$tmpdir/$name" "$target/$name"
    else
      error "sparse-checkout 未找到目录 '$name'"
      rm -rf "$tmpdir"; return 1
    fi
    rm -rf "$tmpdir"
  else
    if [[ -d "${SCRIPT_DIR}/${name}" ]]; then
      rm -rf "${target:?}/$name"
      cp -r "${SCRIPT_DIR}/${name}" "$target/$name"
    else
      error "本地未找到 skill 目录 '${SCRIPT_DIR}/${name}'"
      return 1
    fi
  fi

  # Claude: 额外建 ~/.claude/skills/<name> 软链入口
  if [[ -n "$link_dir" ]]; then
    mkdir -p "$link_dir"
    local rel_target
    rel_target=$(python3 -c "import os; print(os.path.relpath('${target}/${name}', '${link_dir}'))")
    ln -sfn "$rel_target" "${link_dir}/${name}"
  fi

  # 注册到 lock 文件（agents 机制）
  register_lock "$agent" "$name" "${target}/${name}"

  ok "已安装 '${name}' → ${agent}: ${target}/${name}"
}

# ── Install a single skill (fan-out to agents) ──────────
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

  # 安装到指定目录（--target 覆盖，单 agent）
  if [[ -n "$TARGET" ]]; then
    mkdir -p "$TARGET"
    if [[ "$REMOTE" == true ]]; then
      local tmpdir
      tmpdir=$(mktemp -d)
      info "从 GitHub 拉取 skill '$name'..."
      git clone --depth 1 --filter=blob:none --sparse "$REPO_URL" "$tmpdir" 2>/dev/null
      (cd "$tmpdir" && git sparse-checkout set "$name")
      cp -r "$tmpdir/$name" "$TARGET/$name" && rm -rf "$tmpdir"
    else
      rm -rf "${TARGET:?}/$name"
      cp -r "${SCRIPT_DIR}/${name}" "$TARGET/$name"
    fi
    ok "已安装 '${name}' → ${TARGET}/${name}"
    return
  fi

  # Fan-out to resolved agents（按 target 目录去重，避免 claude+trae 重复拷贝）
  local agents
  agents=$(resolve_agents)
  local any_ok=false
  declare -A handled_targets=()
  for agent in $agents; do
    # all 模式下跳过未检测到且非显式存在的 agent
    if [[ "$AGENT" == "all" ]] && ! agent_exists "$agent"; then
      continue
    fi
    local t
    t=$(agents_dir "$agent")
    # 同一 target 目录只拷贝一次；claude/trae 共享 ~/.agents/skills 时，
    # 第二个 agent 只需补建软链入口，不重复拷贝。
    if [[ -n "${handled_targets[$t]:-}" ]]; then
      local link_dir
      link_dir=$(agent_link_dir "$agent")
      if [[ -n "$link_dir" ]]; then
        mkdir -p "$link_dir"
        local rel_target
        rel_target=$(python3 -c "import os; print(os.path.relpath('${t}/${name}', '${link_dir}'))")
        ln -sfn "$rel_target" "${link_dir}/${name}"
        ok "已建 ${agent} 软链入口 → ${link_dir}/${name}"
      fi
      register_lock "$agent" "$name" "${t}/${name}"
      continue
    fi
    handled_targets["$t"]=1
    if install_to_agent "$agent" "$name"; then
      any_ok=true
    else
      warn "安装到 ${agent} 失败,跳过。"
    fi
  done
  [[ "$any_ok" == true ]] || { error "'$name' 安装失败"; exit 1; }
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
  ok "全部安装完成"
}

# ── Remove a skill ──────────────────────────────────────
remove_skill() {
  local name="$1"
  [[ -z "$name" ]] && { error "用法: ./install.sh --remove <name>"; exit 1; }
  local removed=false

  for agent in $(resolve_agents); do
    local target link_dir lock_file
    target=$(agents_dir "$agent")
    link_dir=$(agent_link_dir "$agent")
    if [[ -e "${target}/${name}" || -L "${target}/${name}" ]]; then
      rm -rf "${target:?}/${name}"
      # 清理 claude 软链入口
      [[ -n "$link_dir" && -L "${link_dir}/${name}" ]] && rm -f "${link_dir}/${name}"
      unregister_lock "$agent" "$name"
      ok "已从 ${agent} 移除 '${name}'"
      removed=true
    fi
  done

  if [[ "$removed" == false ]]; then
    warn "未在任何 agent 中找到已安装的 '${name}'"
  fi
}

# ── Main ────────────────────────────────────────────────
case "$ACTION" in
  list)    list_skills ;;
  agents)  show_agents ;;
  install) install_skill "$SKILL_NAME" ;;
  all)     install_all ;;
  remove)  remove_skill "$SKILL_NAME" ;;
  update)  python3 "${SCRIPT_DIR}/scripts/generate-index.py" "${SCRIPT_DIR}" ;;
  *)
    error "未指定操作。用法: ./install.sh <skill-name> | --all | --list | --update | --remove <name> | --agents"
    exit 1
    ;;
esac
