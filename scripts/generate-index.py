#!/usr/bin/env python3
"""
BotSkills — Index Generator

Scans the repository for all skill directories (containing SKILL.md),
parses their YAML frontmatter, and generates:
  1. skills.json  — machine-readable manifest
  2. README.md     — human-readable index (preserves non-table sections)

Usage:
  python3 scripts/generate-index.py [repo-root]
"""

import json
import os
import re
import sys
from pathlib import Path


def parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from SKILL.md content."""
    fm = {}
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return fm

    front_text = match.group(1)
    for line in front_text.split("\n"):
        line = line.strip()
        if line.startswith("name:"):
            val = line.split(":", 1)[1].strip().strip('"').strip("'")
            fm["name"] = val
        elif line.startswith("description:"):
            val = line.split(":", 1)[1].strip()
            # Handle YAML folded block (> prefix)
            if not val:
                # Collect indented continuation lines
                pass
            elif val.startswith(">"):
                # Folded — description on following lines
                pass
            else:
                fm["description"] = val.strip('"').strip("'")

    # Handle folded description (> style)
    if "description" not in fm:
        lines = front_text.split("\n")
        in_desc = False
        desc_parts = []
        for line in lines:
            if line.strip().startswith("description:"):
                rest = line.split(":", 1)[1].strip()
                if rest.strip().startswith(">"):
                    in_desc = True
                    continue
                elif rest:
                    fm["description"] = rest.strip('"').strip("'")
                    in_desc = False
            elif in_desc:
                if line.startswith("  ") or line.startswith("\t"):
                    desc_parts.append(line.strip())
                else:
                    in_desc = False
        if desc_parts:
            fm["description"] = " ".join(desc_parts)

    # Parse dependencies (optional field)
    deps = []
    in_deps = False
    for line in front_text.split("\n"):
        if line.strip().startswith("dependencies:"):
            rest = line.split(":", 1)[1].strip()
            if rest.startswith("[") and rest.endswith("]"):
                deps = [
                    d.strip().strip('"').strip("'")
                    for d in rest[1:-1].split(",")
                    if d.strip()
                ]
                break
            in_deps = True
        elif in_deps:
            if line.strip().startswith("- "):
                deps.append(line.strip()[2:].strip('"').strip("'"))
            elif not line.startswith(" ") and not line.startswith("\t"):
                in_deps = False
    if deps:
        fm["dependencies"] = deps

    return fm


def scan_skills(repo_root: Path) -> list[dict]:
    """Scan repo for all skill directories containing SKILL.md."""
    skills = []
    for entry in sorted(repo_root.iterdir()):
        skill_md = entry / "SKILL.md"
        if entry.is_dir() and skill_md.exists():
            content = skill_md.read_text(encoding="utf-8")
            fm = parse_frontmatter(content)
            skill = {
                "name": fm.get("name", entry.name),
                "description": fm.get("description", ""),
                "path": f"{entry.name}/",
                "dependencies": fm.get("dependencies", []),
            }
            skills.append(skill)
    return skills


def generate_skills_json(repo_root: Path, skills: list[dict]) -> None:
    """Write skills.json manifest."""
    manifest = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "version": "1.0.0",
        "updated": __import__("datetime").datetime.now()
        .astimezone()
        .isoformat(),
        "skills": skills,
    }
    out = repo_root / "skills.json"
    out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"✓ skills.json 已生成 ({len(skills)} skills)")


def generate_readme(repo_root: Path, skills: list[dict]) -> None:
    """Regenerate README.md with skill index table."""
    readme = repo_root / "README.md"

    # Read existing README to preserve non-table sections
    header = """# BotSkills 🤖

TRAE Skills 集合仓库 — 可复用的 AI agent 技能库

## 快速安装

### 安装单个 skill

```bash
# 方式一: 克隆后本地安装
git clone https://github.com/siciyuan404/BotSkills.git
cd BotSkills
./install.sh <skill-name>

# 方式二: 一行命令远程安装(无需克隆)
curl -fsSL https://raw.githubusercontent.com/siciyuan404/BotSkills/main/install.sh | bash -s <skill-name> --remote
```

### 安装全部 skills

```bash
./install.sh --all
```

### 指定安装目录

```bash
./install.sh <skill-name> --target /path/to/.trae/skills
```

### 查看可用列表

```bash
./install.sh --list
```

## 可用 Skills

"""

    # Build table
    table = "| Skill | Description | Dependencies |\n|-------|-------------|-------------|\n"
    for s in skills:
        name = s["name"]
        desc = s.get("description", "")[:80]
        deps = ", ".join(s.get("dependencies", [])) or "—"
        table += f"| [{name}](./{name}/) | {desc} | {deps} |\n"

    footer = """
## 添加新 Skill

1. 在仓库根目录创建 `<skill-name>/` 目录
2. 创建 `SKILL.md`(带 frontmatter:name, description, dependencies)
3. 运行 `./install.sh --update` 更新索引

### SKILL.md 格式

```yaml
---
name: my-skill
description: "Does X. Invoke when Y happens or user asks for Z."
dependencies:
  - python3
  - rclone
---
```

## 索引维护

skills.json 和 README.md 的索引表由 `scripts/generate-index.py` 自动生成:

```bash
python3 scripts/generate-index.py
# 或
./install.sh --update
```

## License

MIT License
"""

    content = header + table + footer
    readme.write_text(content, encoding="utf-8")
    print(f"✓ README.md 已更新 ({len(skills)} skills)")


def main():
    repo_root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    if not (repo_root / "install.sh").exists():
        print(f"✗ 未在 {repo_root} 找到 install.sh,请指定正确的仓库根目录")
        sys.exit(1)

    skills = scan_skills(repo_root)
    if not skills:
        print("✗ 未找到任何 skill 目录")
        sys.exit(1)

    generate_skills_json(repo_root, skills)
    generate_readme(repo_root, skills)
    print("✓ 索引生成完成")


if __name__ == "__main__":
    main()
