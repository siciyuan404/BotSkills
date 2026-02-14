#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Editor Skill
专门用于编辑和管理 Telegram 消息推送内容
"""

import json
import logging
import os
import re
import yaml
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

# 尝试导入 telegram bot 库
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, MessageHandler, 
        ConversationHandler, CallbackQueryHandler, ContextTypes, filters
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("警告: python-telegram-bot 未安装，运行: pip install python-telegram-bot")


# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


@dataclass
class MessageDraft:
    """消息草稿数据类"""
    id: str
    content: str
    parse_mode: str  # MarkdownV2, HTML, Markdown
    created_at: str
    updated_at: str
    tags: List[str]
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MessageDraft':
        return cls(**data)


@dataclass
class MessageHistory:
    """消息历史记录"""
    id: str
    content: str
    channel: str
    sent_at: str
    status: str  # sent, failed
    error_msg: Optional[str] = None


class TelegramEditor:
    """Telegram 消息编辑器主类"""
    
    # 对话状态
    EDITING, PREVIEWING, SELECTING_TEMPLATE, SENDING = range(4)
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.drafts: List[MessageDraft] = []
        self.history: List[MessageHistory] = []
        self.templates: Dict = {}
        self.current_draft: Optional[MessageDraft] = None
        
        # 加载数据
        self._load_templates()
        self._load_drafts()
        self._load_history()
        
        # 初始化 bot
        self.application: Optional[Application] = None
        if TELEGRAM_AVAILABLE and self.config.get('bot', {}).get('token'):
            self._init_bot()
    
    def _load_config(self, path: str) -> Dict:
        """加载配置文件（支持本地配置文件和环境变量）"""
        default_config = {
            'bot': {'token': '', 'default_channel': '', 'admin_users': []},
            'editor': {'auto_save': True, 'max_history': 50},
            'templates': {'enabled': True}
        }
        
        config = default_config.copy()
        
        # 1. 加载主配置文件
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    main_config = yaml.safe_load(f)
                    if main_config:
                        config.update(main_config)
            except Exception as e:
                logger.error(f"加载主配置失败: {e}")
        
        # 2. 加载本地配置文件（config.local.yaml - 不提交到 GitHub）
        local_config_path = path.replace('.yaml', '.local.yaml').replace('.yml', '.local.yml')
        if os.path.exists(local_config_path):
            try:
                with open(local_config_path, 'r', encoding='utf-8') as f:
                    local_config = yaml.safe_load(f)
                    if local_config:
                        # 合并本地配置（优先）
                        if 'bot' in local_config:
                            config['bot'].update(local_config['bot'])
                        if 'editor' in local_config:
                            config['editor'].update(local_config['editor'])
                        logger.info(f"已加载本地配置: {local_config_path}")
            except Exception as e:
                logger.error(f"加载本地配置失败: {e}")
        
        # 3. 从环境变量读取敏感信息（最高优先级）
        env_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if env_token:
            config['bot']['token'] = env_token
            logger.info("已从环境变量读取 Bot Token")
        
        env_channel = os.getenv('TELEGRAM_DEFAULT_CHANNEL')
        if env_channel:
            config['bot']['default_channel'] = env_channel
        
        env_admins = os.getenv('TELEGRAM_ADMIN_USERS')
        if env_admins:
            # 支持逗号分隔的用户ID，如: "123456,789012"
            try:
                admin_list = [int(x.strip()) for x in env_admins.split(',') if x.strip()]
                config['bot']['admin_users'] = admin_list
            except ValueError:
                logger.warning("环境变量 TELEGRAM_ADMIN_USERS 格式错误，应为逗号分隔的数字")
        
        return config
    
    def _load_templates(self):
        """加载模板文件"""
        templates_file = self.config.get('storage', {}).get('templates_file', 'templates.json')
        if os.path.exists(templates_file):
            try:
                with open(templates_file, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
                    logger.info(f"已加载 {len(self.templates.get('templates', []))} 个模板")
            except Exception as e:
                logger.error(f"加载模板失败: {e}")
                self.templates = {"templates": [], "version": "1.0.0"}
        else:
            self.templates = {"templates": [], "version": "1.0.0"}
    
    def _load_drafts(self):
        """加载草稿"""
        draft_file = self.config.get('storage', {}).get('draft_file', 'drafts.json')
        if os.path.exists(draft_file):
            try:
                with open(draft_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.drafts = [MessageDraft.from_dict(d) for d in data.get('drafts', [])]
                    logger.info(f"已加载 {len(self.drafts)} 个草稿")
            except Exception as e:
                logger.error(f"加载草稿失败: {e}")
    
    def _load_history(self):
        """加载历史记录"""
        history_file = self.config.get('storage', {}).get('history_file', 'history.json')
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.history = [MessageHistory(**h) for h in data.get('history', [])]
                    logger.info(f"已加载 {len(self.history)} 条历史记录")
            except Exception as e:
                logger.error(f"加载历史失败: {e}")
    
    def _save_drafts(self):
        """保存草稿"""
        draft_file = self.config.get('storage', {}).get('draft_file', 'drafts.json')
        try:
            with open(draft_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'drafts': [d.to_dict() for d in self.drafts]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存草稿失败: {e}")
    
    def _save_history(self):
        """保存历史记录"""
        history_file = self.config.get('storage', {}).get('history_file', 'history.json')
        try:
            # 限制历史记录数量
            max_history = self.config.get('editor', {}).get('max_history', 50)
            history_to_save = self.history[-max_history:] if len(self.history) > max_history else self.history
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'history': [h.__dict__ for h in history_to_save]
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存历史失败: {e}")
    
    def _init_bot(self):
        """初始化 Telegram Bot"""
        token = self.config.get('bot', {}).get('token')
        if not token:
            logger.warning("未配置 Bot Token")
            return
        
        try:
            self.application = Application.builder().token(token).build()
            self._setup_handlers()
            logger.info("Bot 初始化成功")
        except Exception as e:
            logger.error(f"Bot 初始化失败: {e}")
    
    def _setup_handlers(self):
        """设置命令处理器"""
        if not self.application:
            return
        
        # 基础命令
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("new", self.cmd_new))
        self.application.add_handler(CommandHandler("preview", self.cmd_preview))
        self.application.add_handler(CommandHandler("save", self.cmd_save))
        self.application.add_handler(CommandHandler("drafts", self.cmd_list_drafts))
        self.application.add_handler(CommandHandler("templates", self.cmd_list_templates))
        self.application.add_handler(CommandHandler("send", self.cmd_send))
        self.application.add_handler(CommandHandler("history", self.cmd_history))
        self.application.add_handler(CommandHandler("clear", self.cmd_clear))
        
        # 消息处理器
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # 回调处理器
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
    
    # ==================== 命令处理器 ====================
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/start 命令"""
        welcome_text = """
📝 *Telegram Editor*

欢迎使用消息编辑器！

可用命令：
/new - 创建新消息
/preview - 预览当前消息
/save - 保存草稿
/drafts - 查看草稿列表
/templates - 查看模板
/send - 发送到频道
/history - 查看历史
/help - 显示帮助

直接发送消息即可开始编辑！
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/help 命令"""
        help_text = """
📖 *使用帮助*

*基础操作：*
1. 直接发送消息开始编辑
2. 使用 Markdown 格式：*粗体* _斜体_ `代码`
3. 使用 /preview 预览效果
4. 使用 /save 保存草稿

*格式说明：*
• *粗体* → *text*
• _斜体_ → _text_
• `代码` → `code`
• [链接](url) → [text](url)

*模板变量：*
在模板中使用 {variable} 作为占位符

*发送消息：*
/send @channel_name
或使用默认频道
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def cmd_new(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/new 命令 - 创建新消息"""
        self.current_draft = None
        await update.message.reply_text(
            "✏️ *创建新消息*\n\n请直接发送消息内容，支持 Markdown 格式。",
            parse_mode='Markdown'
        )
    
    async def cmd_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/preview 命令 - 预览消息"""
        if not self.current_draft:
            await update.message.reply_text("❌ 当前没有编辑中的消息，使用 /new 创建")
            return
        
        try:
            await update.message.reply_text(
                f"👁 *预览消息*\n\n{self.current_draft.content}",
                parse_mode=self.current_draft.parse_mode if self.current_draft.parse_mode != 'MarkdownV2' else None
            )
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ 预览失败，可能是格式错误：\n{str(e)}\n\n原始内容：\n{self.current_draft.content}"
            )
    
    async def cmd_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/save 命令 - 保存草稿"""
        if not self.current_draft:
            await update.message.reply_text("❌ 没有可保存的内容")
            return
        
        # 更新或添加草稿
        existing = [d for d in self.drafts if d.id == self.current_draft.id]
        if existing:
            existing[0].content = self.current_draft.content
            existing[0].updated_at = datetime.now().isoformat()
        else:
            self.drafts.append(self.current_draft)
        
        self._save_drafts()
        await update.message.reply_text(f"✅ 草稿已保存 (ID: {self.current_draft.id})")
    
    async def cmd_list_drafts(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/drafts 命令 - 列出现有草稿"""
        if not self.drafts:
            await update.message.reply_text("📭 没有保存的草稿")
            return
        
        text = "📝 *草稿列表*\n\n"
        for i, draft in enumerate(self.drafts[-10:], 1):
            preview = draft.content[:50] + "..." if len(draft.content) > 50 else draft.content
            text += f"{i}. `{draft.id}`\n   {preview}\n   _{draft.updated_at[:16]}_\n\n"
        
        # 添加加载按钮
        keyboard = [
            [InlineKeyboardButton(f"加载草稿 {i}", callback_data=f"load_draft:{d.id}")]
            for i, d in enumerate(self.drafts[-5:], 1)
        ]
        
        await update.message.reply_text(
            text, 
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
        )
    
    async def cmd_list_templates(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/templates 命令 - 列出模板"""
        templates = self.templates.get('templates', [])
        if not templates:
            await update.message.reply_text("📭 没有可用模板")
            return
        
        text = "🎨 *消息模板*\n\n"
        keyboard = []
        
        for t in templates:
            text += f"• *{t['name']}* (`{t['id']}`)\n  {t.get('description', '无描述')}\n\n"
            keyboard.append([InlineKeyboardButton(f"使用: {t['name']}", callback_data=f"use_template:{t['id']}")])
        
        await update.message.reply_text(
            text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def cmd_send(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/send 命令 - 发送消息"""
        if not self.current_draft:
            await update.message.reply_text("❌ 没有可发送的消息，使用 /new 创建")
            return
        
        # 获取目标频道
        args = context.args
        if args:
            channel = args[0]
        else:
            channel = self.config.get('bot', {}).get('default_channel')
        
        if not channel:
            await update.message.reply_text(
                "❌ 未指定频道\n用法: /send @channel_name\n或在配置中设置默认频道"
            )
            return
        
        try:
            # 发送消息
            await context.bot.send_message(
                chat_id=channel,
                text=self.current_draft.content,
                parse_mode=self.current_draft.parse_mode if self.current_draft.parse_mode != 'MarkdownV2' else None
            )
            
            # 记录历史
            history = MessageHistory(
                id=f"hist_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                content=self.current_draft.content,
                channel=channel,
                sent_at=datetime.now().isoformat(),
                status='sent'
            )
            self.history.append(history)
            self._save_history()
            
            await update.message.reply_text(f"✅ 消息已发送到 {channel}")
            
        except Exception as e:
            logger.error(f"发送失败: {e}")
            await update.message.reply_text(f"❌ 发送失败: {str(e)}")
    
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/history 命令 - 查看发送历史"""
        if not self.history:
            await update.message.reply_text("📭 没有发送记录")
            return
        
        text = "📤 *发送历史*\n\n"
        for h in self.history[-10:]:
            status_icon = "✅" if h.status == 'sent' else "❌"
            preview = h.content[:30] + "..." if len(h.content) > 30 else h.content
            text += f"{status_icon} `{h.sent_at[5:16]}` → {h.channel}\n   {preview}\n\n"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def cmd_clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/clear 命令 - 清空当前编辑"""
        self.current_draft = None
        await update.message.reply_text("🗑 当前编辑已清空")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息"""
        text = update.message.text
        
        # 创建或更新草稿
        if not self.current_draft:
            self.current_draft = MessageDraft(
                id=f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                content=text,
                parse_mode=self.config.get('editor', {}).get('default_parse_mode', 'Markdown'),
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                tags=[]
            )
        else:
            self.current_draft.content = text
            self.current_draft.updated_at = datetime.now().isoformat()
        
        # 自动保存
        if self.config.get('editor', {}).get('auto_save', True):
            existing = [d for d in self.drafts if d.id == self.current_draft.id]
            if existing:
                existing[0].content = self.current_draft.content
                existing[0].updated_at = self.current_draft.updated_at
            else:
                self.drafts.append(self.current_draft)
            self._save_drafts()
        
        # 显示操作按钮
        keyboard = [
            [InlineKeyboardButton("👁 预览", callback_data="preview"),
             InlineKeyboardButton("💾 保存", callback_data="save")],
            [InlineKeyboardButton("📤 发送", callback_data="send"),
             InlineKeyboardButton("🎨 模板", callback_data="templates")]
        ]
        
        await update.message.reply_text(
            f"✏️ 内容已更新\n长度: {len(text)} 字符\n\n使用按钮或命令继续操作：",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理按钮回调"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "preview":
            if self.current_draft:
                try:
                    await query.edit_message_text(
                        f"👁 *预览*\n\n{self.current_draft.content}",
                        parse_mode=self.current_draft.parse_mode if self.current_draft.parse_mode != 'MarkdownV2' else None
                    )
                except Exception as e:
                    await query.edit_message_text(f"预览错误: {str(e)}\n\n{self.current_draft.content}")
        
        elif data == "save":
            await self.cmd_save(update, context)
        
        elif data == "send":
            await query.edit_message_text("使用 /send @channel 发送消息")
        
        elif data == "templates":
            await self.cmd_list_templates(update, context)
        
        elif data.startswith("use_template:"):
            template_id = data.split(":")[1]
            template = next((t for t in self.templates.get('templates', []) if t['id'] == template_id), None)
            if template:
                self.current_draft = MessageDraft(
                    id=f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    content=template['content'],
                    parse_mode='Markdown',
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                    tags=[template['category']]
                )
                await query.edit_message_text(
                    f"✅ 已加载模板: *{template['name']}*\n\n"
                    f"变量: {', '.join(template.get('variables', []))}\n\n"
                    f"内容预览:\n{template['content'][:200]}...",
                    parse_mode='Markdown'
                )
        
        elif data.startswith("load_draft:"):
            draft_id = data.split(":")[1]
            draft = next((d for d in self.drafts if d.id == draft_id), None)
            if draft:
                self.current_draft = draft
                await query.edit_message_text(
                    f"✅ 已加载草稿\n\n{draft.content[:300]}..."
                )
    
    def run(self):
        """运行 Bot"""
        if not TELEGRAM_AVAILABLE:
            print("❌ 请先安装依赖: pip install python-telegram-bot")
            return
        
        if not self.application:
            print("❌ Bot 未初始化，请检查配置文件中的 token")
            return
        
        print("🚀 启动 Telegram Editor Bot...")
        print("按 Ctrl+C 停止")
        self.application.run_polling()
    
    def run_cli(self):
        """命令行模式（无需 Bot Token）"""
        # 设置 stdout 编码
        import sys
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        
        print("[Telegram Editor CLI 模式]")
        print("=" * 50)
        print("命令: new, preview, save, drafts, templates, send, quit")
        print("=" * 50)
        
        while True:
            try:
                cmd = input("\n> ").strip().lower()
                
                if cmd == "quit":
                    break
                elif cmd == "new":
                    content = input("请输入消息内容:\n")
                    self.current_draft = MessageDraft(
                        id=f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        content=content,
                        parse_mode='Markdown',
                        created_at=datetime.now().isoformat(),
                        updated_at=datetime.now().isoformat(),
                        tags=[]
                    )
                    print(f"[OK] 已创建草稿 (ID: {self.current_draft.id})")
                
                elif cmd == "preview":
                    if self.current_draft:
                        print(f"\n{'='*50}")
                        print(self.current_draft.content)
                        print(f"{'='*50}")
                    else:
                        print("[X] 没有当前草稿")
                
                elif cmd == "save":
                    if self.current_draft:
                        existing = [d for d in self.drafts if d.id == self.current_draft.id]
                        if existing:
                            existing[0].content = self.current_draft.content
                            existing[0].updated_at = datetime.now().isoformat()
                        else:
                            self.drafts.append(self.current_draft)
                        self._save_drafts()
                        print("[OK] 草稿已保存")
                    else:
                        print("[X] 没有可保存的内容")
                
                elif cmd == "drafts":
                    if self.drafts:
                        for d in self.drafts[-5:]:
                            print(f"* {d.id}: {d.content[:50]}...")
                    else:
                        print("[空] 没有草稿")
                
                elif cmd == "templates":
                    for t in self.templates.get('templates', []):
                        print(f"* {t['id']}: {t['name']}")
                
                elif cmd == "send":
                    print("CLI 模式不支持发送，请使用 Bot 模式")
                
                else:
                    print("未知命令")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")
        
        print("\n再见!")


def main():
    """主入口"""
    import sys
    
    editor = TelegramEditor()
    
    # 检查命令行参数
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        editor.run_cli()
    else:
        editor.run()


if __name__ == "__main__":
    main()
