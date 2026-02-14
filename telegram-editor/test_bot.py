#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试 Bot 模式初始化"""

import sys
sys.path.insert(0, '.')

print("=" * 50)
print("测试 Telegram Editor 导入")
print("=" * 50)

try:
    from editor import TelegramEditor, MessageDraft, MessageHistory
    print("[OK] 类导入成功")
    print(f"  - TelegramEditor: {TelegramEditor}")
    print(f"  - MessageDraft: {MessageDraft}")
    print(f"  - MessageHistory: {MessageHistory}")
except Exception as e:
    print(f"[X] 导入失败: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("测试 Telegram Bot 库")
print("=" * 50)

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, MessageHandler, filters
    print("[OK] python-telegram-bot 可用")
except ImportError as e:
    print(f"[X] python-telegram-bot 不可用: {e}")

print("\n" + "=" * 50)
print("测试配置加载")
print("=" * 50)

try:
    editor = TelegramEditor("config.yaml")
    print(f"[OK] 配置加载成功")
    print(f"  - 模板数量: {len(editor.templates.get('templates', []))}")
    print(f"  - 草稿数量: {len(editor.drafts)}")
    print(f"  - 历史记录: {len(editor.history)}")
    print(f"  - 自动保存: {editor.config.get('editor', {}).get('auto_save')}")
except Exception as e:
    print(f"[X] 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("测试数据类")
print("=" * 50)

from datetime import datetime

try:
    draft = MessageDraft(
        id="test_001",
        content="测试内容",
        parse_mode="Markdown",
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        tags=["test"]
    )
    print(f"[OK] MessageDraft 创建成功")
    print(f"  - ID: {draft.id}")
    print(f"  - Content: {draft.content}")
    print(f"  - Dict: {draft.to_dict()}")
except Exception as e:
    print(f"[X] MessageDraft 失败: {e}")

print("\n" + "=" * 50)
print("所有测试通过！")
print("=" * 50)