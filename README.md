# BotSkills 🤖

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

| Skill | Description | Dependencies |
|-------|-------------|-------------|
| [flutter-gh-starter](./flutter-gh-starter/) | Primary skill for bootstrapping a Flutter mobile project and managing it as an o | — |
| [rclone](./rclone/) | Comprehensive rclone control for MinIO and cloud storage operations. Use when th | — |
| [telegram-editor](./telegram-editor/) | Telegram Bot message editing and push management skill. Provides capabilities fo | — |

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
