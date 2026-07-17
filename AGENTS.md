# BotSkills — AI Agent 技能仓库

集中管理可复用的 AI agent 技能（Skills）。每个技能是一个自包含模块，通过 `SKILL.md` 定义行为，扩展 agent 的能力边界。

**兼容工具：** Claude Code、Cursor、Copilot、Codex、Gemini CLI、Windsurf、Devin、Aider 等 20+ 支持 AGENTS.md 标准的 AI 编码代理。

## 技能列表

| 技能 | 说明 |
|-------|-------------|
| [rclone](rclone/SKILL.md) | Rclone/MinIO 云存储操作 — 桶、文件、同步、分享链接 |
| [cloudflared](cloudflared/SKILL.md) | Cloudflare Tunnel 管理 — 隧道创建、DNS、入口规则、Access |
| [flutter-gh-starter](flutter-gh-starter/SKILL.md) | Flutter 项目初始化 + GitHub 管理（gh CLI） |
| [telegram-editor](telegram-editor/SKILL.md) | Telegram Bot 消息编辑、模板和推送管理 |
| [cangjie-skill](cangjie-skill/SKILL.md) | 将书籍/视频/播客蒸馏为可执行 agent 技能 |
| [software-update](software-update/SKILL.md) | 桌面端、服务端、Docker 应用的自动更新/OTA |

## 技能目录结构

每个技能遵循 [agentskills.io](https://agentskills.io) 标准：

```
skill-name/
├── SKILL.md            # [必需] YAML frontmatter + 指令（≤500 行）
├── references/         # [可选] 深度参考文档，按需加载
├── scripts/            # [可选] 可执行辅助脚本
└── evals/              # [可选] 测试用例和断言
```

### SKILL.md Frontmatter

```yaml
---
name: skill-name           # 小写+连字符，必须匹配目录名
description: >             # 主要触发条件，包含动作关键词和触发场景
  技能用途和何时使用。包含具体的触发短语。
---
```

### skills.json 注册

每个技能还必须在 `skills.json` 中注册，供 `install.sh` 自动发现：

```json
{
  "name": "skill-name",
  "description": "简短描述，用于安装列表展示",
  "path": "skill-name/",
  "dependencies": ["tool1", "tool2"]
}
```

新增或修改技能后，运行 `./install.sh --update` 自动更新 skills.json 和 README 索引。

### 命名规则

- 首选单个小写单词：`rclone`、`docker`
- 多词用连字符连接：`flutter-gh-starter`、`software-update`
- 必须与目录名完全一致

## 开发工作流

### 新增技能

1. 创建 `skill-name/SKILL.md`，包含 frontmatter（name + description 必需）
2. 可选添加 `references/` 和 `scripts/` 支撑文件
3. 创建 `evals/evals.json`，包含 2-3 个测试提示
4. 更新本文件的技能表、`README.md` 的表格和 `skills.json`

### 质量标准

- SKILL.md ≤ 500 行。深度内容拆到 `references/`
- 每个技能专注一个职责。不要创建"全能"技能
- description 必须包含具体的触发短语——Claude 据此决定是否激活
- 指令使用祈使语气。解释每个步骤的"为什么"
- 为重复性任务编写脚本（避免每个 agent 重新发明轮子）
- 新增技能后运行 `./install.sh --update` 验证

### 触发描述设计

`description` 字段是技能激活的**唯一机制**。要具体：

```yaml
# 好的 — 明确的触发关键词和使用场景
description: >
  Docker 容器管理：构建、运行、停止、日志、exec、
  compose up/down、镜像管理。当用户提到容器、
  docker、部署、容器化应用时使用。

# 差的 — 过于模糊，agent 不知道何时使用
description: Docker 操作。
```

### 测试技能

- 在 `evals/evals.json` 中创建真实的测试提示
- 运行有技能 vs 无技能（基线）的对比
- 尽可能用程序化方式评估断言
- 迭代：检视输出 → 改进技能 → 重新测试

### 版本控制

- 提交格式：`feat(skill-name): 说明`、`fix:`、`docs:`、`refactor:`
- 每个技能作为原子提交
- 基础设施变更：`chore(skills): 说明`

## 跨工具兼容

本 AGENTS.md 遵循 [Agentic AI Foundation](https://agentskills.io)（Linux 基金会）标准，受 20+ AI 编码代理支持。技能可通过根级 `AGENTS.md` 发现，也兼容 `.claude/skills/` 布局。

## 安全

- 技能在用户批准后执行。敏感操作（网络、文件写入、环境变量）需逐次确认
- 技能中禁止明文凭证。使用 `${ENV_VAR}` 模式引用密钥
- `scripts/` 目录不应包含未经用户确认的破坏性自动执行代码

## 许可证

MIT — 详见 [LICENSE](LICENSE)
