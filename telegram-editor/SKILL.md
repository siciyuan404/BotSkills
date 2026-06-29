---
name: telegram-editor
description: Telegram Bot message editing and push management skill. Provides capabilities for editing message content, previewing messages before sending, managing message templates, and pushing messages to Telegram channels or groups.
---

# Telegram Editor

Edit, manage and push Telegram messages via a Bot (polling) or a CLI.

所有 CLI 子命令通过 `python editor.py <command>` 调用；用 `--cli` 进入交互模式，或无参数直接启动 Bot polling。

## 快速开始

### CLI 子命令

```bash
# 发送一条文本消息
python editor.py send --chat-id CHAT_ID --text "Hello World!"

# 本地预览消息内容（不发送）
python editor.py preview --text "Your message here" --parse-mode markdown
```

### Bot 模式

```bash
# 无参数启动 Bot，随后在 Telegram 中使用 /start /new /preview 等命令
python editor.py
```

## 消息格式

支持三种 `--parse-mode`：`Markdown`、`MarkdownV2`、`HTML`。省略时按纯文本发送。

### Markdown

```bash
python editor.py send \
  --chat-id CHAT_ID \
  --text "**Bold** and *italic* text" \
  --parse-mode Markdown
```

### HTML

```bash
python editor.py send \
  --chat-id CHAT_ID \
  --text "<b>Bold</b> and <i>italic</i> text" \
  --parse-mode HTML
```

### MarkdownV2

MarkdownV2 支持更丰富的格式，但要求对 `_*[]()~` >#+-=|{}.!` 等特殊字符转义。
普通文本中的 `.`、`-` 等需写为 `\.`、`\-`，否则发送会失败。
工具方法 `TelegramEditor.escape_markdown_v2(text)` 可对纯文本片段转义（不要对包含格式语法的整段文本使用）。

```bash
python editor.py send \
  --chat-id CHAT_ID \
  --text "*Bold* and _italic_ text" \
  --parse-mode MarkdownV2
```

## 草稿管理

```bash
# 保存草稿（--name 可选，省略则自动生成 ID；同名覆盖）
python editor.py draft save --name "announcement" --text "Draft content"

# 列出所有草稿
python editor.py draft list

# 发送已保存的草稿
python editor.py draft send --name "announcement" --chat-id CHAT_ID
```

## 推送操作

### 群发

```bash
# 向多个 chat 群发同一消息
python editor.py broadcast \
  --chats "CHAT_ID1,CHAT_ID2,CHAT_ID3" \
  --text "Broadcast message"
```

### 定时发送

```bash
# 在指定时间发送（阻塞等待至发送时刻，Ctrl+C 取消）
python editor.py schedule \
  --chat-id CHAT_ID \
  --text "Scheduled message" \
  --at "2026-02-15 10:00"
```

## 配置

```bash
# 查看当前配置（Token 会脱敏显示）
python editor.py config show

# 设置 Bot Token（写入 config.local.yaml，不提交到 Git）
python editor.py config set-token "YOUR_BOT_TOKEN"

# 设置默认推送频道
python editor.py config set-default-chat "CHAT_ID"
```

敏感信息优先级：环境变量 > config.local.yaml > config.yaml。

| 变量 | 说明 |
|------|------|
| TELEGRAM_BOT_TOKEN | Bot Token |
| TELEGRAM_DEFAULT_CHANNEL | 默认频道 |
| TELEGRAM_ADMIN_USERS | 管理员用户 ID，逗号分隔 |

## Bot 交互命令

启动 Bot 后在 Telegram 中使用：

| 命令 | 说明 |
|------|------|
| /start | 显示欢迎与命令列表 |
| /help | 使用帮助 |
| /new | 创建新消息 |
| /preview | 预览当前消息 |
| /save | 保存草稿 |
| /drafts | 查看草稿列表 |
| /templates | 查看模板 |
| /send [channel] | 发送到频道 |
| /history | 查看发送历史 |
| /clear | 清空当前编辑 |

配置了 `admin_users` 后，仅管理员可执行写操作（/start /help 除外）。

## Notes

- 需要有效的 Telegram Bot Token
- Chat ID 可通过 @userinfobot 或 @getidsbot 获取
- MarkdownV2 可用但需转义特殊字符；普通富文本推荐 Markdown，复杂格式用 HTML
- 敏感信息请放入 config.local.yaml 或环境变量，避免提交到 Git
