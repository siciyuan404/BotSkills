# Telegram Editor Skill

📝 专门用于编辑和管理 Telegram 消息推送内容的工具。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Bot Token

编辑 `config.yaml`：

```yaml
bot:
  token: "YOUR_BOT_TOKEN_HERE"  # 从 @BotFather 获取
  default_channel: "@your_channel"  # 可选：默认推送频道
```

### 3. 运行

**Bot 模式**（需要 Token）：
```bash
python editor.py
```

**CLI 模式**（无需 Token，仅编辑）：
```bash
python editor.py --cli
```

## 功能特点

- ✏️ Markdown/HTML 格式支持
- 👁 实时预览消息效果
- 💾 自动保存草稿
- 🎨 消息模板系统
- 📤 一键推送到频道
- 📜 发送历史记录

## 命令列表

| 命令 | 说明 |
|------|------|
| /start | 启动编辑器 |
| /new | 创建新消息 |
| /preview | 预览当前消息 |
| /save | 保存草稿 |
| /drafts | 查看草稿列表 |
| /templates | 查看模板列表 |
| /send | 发送到频道 |
| /history | 查看发送历史 |
| /help | 显示帮助 |

## 消息格式

### Markdown
```
*粗体*    → 粗体
_斜体_    → 斜体
`代码`    → 代码
[链接](url) → 链接
```

### HTML
```html
<b>粗体</b>
<i>斜体</i>
<code>代码</code>
<a href="url">链接</a>
```

## 模板系统

内置 5 种常用模板：
- 欢迎消息
- 公告通知
- 更新通知
- 活动推广
- 日报

支持自定义模板，在 `templates.json` 中添加。

## 文件说明

| 文件 | 说明 |
|------|------|
| `editor.py` | 主程序 |
| `config.yaml` | 配置文件 |
| `templates.json` | 消息模板 |
| `drafts.json` | 草稿存储（自动生成）|
| `history.json` | 历史记录（自动生成）|

## 获取 Bot Token

1. 在 Telegram 搜索 `@BotFather`
2. 发送 `/newbot` 命令
3. 按提示设置名称和用户名
4. 保存获得的 Token

## 许可证

MIT
