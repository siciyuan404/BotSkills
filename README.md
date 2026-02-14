# BotSkills 🤖

Picoclaw Bot Skills Repository - Centralized management for all Picoclaw bot skills.

## About

This repository contains all custom skills developed for the Picoclaw AI assistant. Each skill is a self-contained module that extends Picoclaw's capabilities.

## Available Skills

### telegram-editor 📝
Telegram message editing and push management tool.

**Features:**
- Message editing with Markdown/HTML support
- Real-time preview
- Draft saving and loading
- Template system
- Push to channels
- Send history

**Location:** `telegram-editor/`

**Configuration:**

敏感信息（Token、用户ID）可通过以下方式配置（优先级从高到低）：

1. **环境变量**（最安全，推荐用于服务器）
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token"
   export TELEGRAM_DEFAULT_CHANNEL="@your_channel"
   export TELEGRAM_ADMIN_USERS="123456789,987654321"
   ```

2. **本地配置文件**（推荐用于开发）
   - 复制 `config.local.yaml` 并填入真实信息
   - 此文件已被 `.gitignore` 保护，不会被提交

3. **主配置文件**（不推荐，仅用于非敏感配置）
   - 修改 `config.yaml` 中的非敏感设置

### rclone 📁
Comprehensive rclone control for MinIO and cloud storage operations.

**Location:** `rclone/`

## Usage

Skills are automatically loaded by Picoclaw from this repository.

## Issue Tracking

If you encounter any problems with a skill:
1. Check existing issues in the [Issues](https://github.com/siciyuan404/BotSkills/issues) tab
2. Create a new issue with detailed information

## License

MIT License
