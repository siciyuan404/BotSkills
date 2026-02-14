---
name: telegram-editor
description: Telegram Bot message editing and push management skill. Provides capabilities for editing message content, previewing messages before sending, managing message templates, and pushing messages to Telegram channels or groups.
---

# Telegram Editor

Edit and manage Telegram message content with preview and push functionality.

## Quick Start

### Send a Simple Message

```bash
# Send text message to a chat
telegram-send --chat-id CHAT_ID --text "Hello World!"
```

### Edit Message Content

```bash
# Preview message before sending
telegram-preview --text "Your message here" --format markdown
```

## Message Formatting

### Markdown Format

```bash
# Send formatted message
telegram-send \
  --chat-id CHAT_ID \
  --text "**Bold** and *italic* text" \
  --parse-mode markdown
```

### HTML Format

```bash
# Send HTML formatted message
telegram-send \
  --chat-id CHAT_ID \
  --text "<b>Bold</b> and <i>italic</i> text" \
  --parse-mode html
```

## Message Management

### Save Draft

```bash
# Save message as draft
telegram-draft save --name "announcement" --text "Draft content"
```

### List Drafts

```bash
# List all saved drafts
telegram-draft list
```

### Send Draft

```bash
# Send a saved draft
telegram-draft send --name "announcement" --chat-id CHAT_ID
```

## Push Operations

### Broadcast to Multiple Chats

```bash
# Send message to multiple chats
telegram-broadcast \
  --chats "CHAT_ID1,CHAT_ID2,CHAT_ID3" \
  --text "Broadcast message"
```

### Scheduled Messages

```bash
# Schedule message for later
telegram-schedule \
  --chat-id CHAT_ID \
  --text "Scheduled message" \
  --at "2026-02-15 10:00"
```

## Configuration

### Bot Token Setup

```bash
# Set bot token
telegram-config set-token "YOUR_BOT_TOKEN"
```

### Default Chat

```bash
# Set default chat ID
telegram-config set-default-chat "CHAT_ID"
```

## Notes

- Requires a valid Telegram Bot Token
- Chat ID can be obtained via @userinfobot or @getidsbot
- Markdown v2 is recommended for rich formatting
- HTML mode allows more complex formatting options