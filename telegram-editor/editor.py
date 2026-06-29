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
from dataclasses import dataclass, asdict, fields

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


# 配置日志：作为库时不污染 root logger，具体配置在 TelegramEditor 中按 config.yaml 应用
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


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
        # 仅读取已知字段，避免历史数据含未知字段时 TypeError
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class MessageHistory:
    """消息历史记录"""
    id: str
    content: str
    channel: str
    sent_at: str
    status: str  # sent, failed
    error_msg: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'MessageHistory':
        # 仅读取已知字段，保持与 MessageDraft 一致的健壮性
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


class TelegramEditor:
    """Telegram 消息编辑器主类"""

    # 对话状态
    EDITING, PREVIEWING, SELECTING_TEMPLATE, SENDING = range(4)

    # MarkdownV2 中需要转义的特殊字符
    _MDV2_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"

    @staticmethod
    def escape_markdown_v2(text: str) -> str:
        """转义 MarkdownV2 特殊字符，用于纯文本片段。

        注意：仅对非格式片段使用，不要对包含格式语法（如 *bold*）的整段文本使用，
        否则会破坏用户编写的格式。
        """
        return re.sub(f"([{re.escape(TelegramEditor._MDV2_ESCAPE_CHARS)}])", r"\\\1", text)
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self._configure_logging()
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

    def _configure_logging(self):
        """根据 config.yaml 的 logging 段配置本模块 logger，避免污染 root logger。"""
        log_cfg = self.config.get('logging', {}) or {}
        level_name = str(log_cfg.get('level', 'INFO')).upper()
        logger.setLevel(getattr(logging, level_name, logging.INFO))

        # 仅在首次配置时添加 handler，防止重复实例化导致重复输出
        if getattr(logger, '_trae_configured', False):
            return
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_file = log_cfg.get('file')
        if log_file:
            handler: logging.Handler = logging.FileHandler(log_file, encoding='utf-8')
        else:
            handler = logging.StreamHandler()
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger._trae_configured = True  # type: ignore[attr-defined]

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
                    self.history = [MessageHistory.from_dict(h) for h in data.get('history', [])]
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
                    'history': [h.to_dict() for h in history_to_save]
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

    # ==================== 权限校验 ====================

    def _is_authorized(self, update: Update) -> bool:
        """检查发起者是否在管理员列表内。未配置 admin_users 时放行所有人。"""
        admins = self.config.get('bot', {}).get('admin_users') or []
        if not admins:
            return True
        user = update.effective_user
        return user is not None and user.id in admins

    async def _deny_if_unauthorized(self, update: Update) -> bool:
        """未授权时回复拒绝消息并返回 True，调用方应立即 return。"""
        if self._is_authorized(update):
            return False
        if update.callback_query:
            await update.callback_query.answer("⛔ 无权限", show_alert=True)
        elif update.message:
            await update.message.reply_text("⛔ 无权限：你不在此 Bot 的管理员列表中")
        return True

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
        if await self._deny_if_unauthorized(update):
            return
        self.current_draft = None
        await update.message.reply_text(
            "✏️ *创建新消息*\n\n请直接发送消息内容，支持 Markdown 格式。",
            parse_mode='Markdown'
        )
    
    async def cmd_preview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/preview 命令 - 预览消息"""
        if await self._deny_if_unauthorized(update):
            return
        if not self.current_draft:
            await update.message.reply_text("❌ 当前没有编辑中的消息，使用 /new 创建")
            return
        
        try:
            await update.message.reply_text(
                f"👁 *预览消息*\n\n{self.current_draft.content}",
                parse_mode=self.current_draft.parse_mode
            )
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ 预览失败，可能是格式错误：\n{str(e)}\n\n原始内容：\n{self.current_draft.content}"
            )
    
    async def cmd_save(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """/save 命令 - 保存草稿"""
        if await self._deny_if_unauthorized(update):
            return
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
        if await self._deny_if_unauthorized(update):
            return
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
        if await self._deny_if_unauthorized(update):
            return
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
        if await self._deny_if_unauthorized(update):
            return
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
                parse_mode=self.current_draft.parse_mode
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
        if await self._deny_if_unauthorized(update):
            return
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
        if await self._deny_if_unauthorized(update):
            return
        self.current_draft = None
        await update.message.reply_text("🗑 当前编辑已清空")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理文本消息"""
        if await self._deny_if_unauthorized(update):
            return
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
        if await self._deny_if_unauthorized(update):
            return
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "preview":
            if self.current_draft:
                try:
                    await query.edit_message_text(
                        f"👁 *预览*\n\n{self.current_draft.content}",
                        parse_mode=self.current_draft.parse_mode
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
    
    # ==================== CLI 子命令 ====================

    def _send_to_chat_sync(self, chat_id: str, text: str, parse_mode: Optional[str] = None):
        """同步发送消息到指定 chat（CLI 模式使用），独立于 Bot polling。"""
        import asyncio
        token = self.config.get('bot', {}).get('token')
        if not token:
            raise RuntimeError("未配置 Bot Token，请在 config.local.yaml 或环境变量 TELEGRAM_BOT_TOKEN 中设置")
        if not TELEGRAM_AVAILABLE:
            raise RuntimeError("python-telegram-bot 未安装: pip install python-telegram-bot")

        async def _run():
            from telegram import Bot
            bot = Bot(token)
            await bot.initialize()
            try:
                return await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            finally:
                await bot.shutdown()
        return asyncio.run(_run())

    def _record_history(self, content: str, channel: str, status: str, error_msg: Optional[str] = None):
        """记录一条发送历史并持久化。"""
        self.history.append(MessageHistory(
            id=f"hist_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            content=content,
            channel=channel,
            sent_at=datetime.now().isoformat(),
            status=status,
            error_msg=error_msg,
        ))
        self._save_history()

    def cli_send(self, args) -> int:
        """发送消息到单个 chat。"""
        try:
            self._send_to_chat_sync(args.chat_id, args.text, args.parse_mode)
            self._record_history(args.text, args.chat_id, 'sent')
            print(f"✅ 消息已发送到 {args.chat_id}")
            return 0
        except Exception as e:
            self._record_history(args.text, args.chat_id, 'failed', str(e))
            print(f"❌ 发送失败: {e}")
            return 1

    def cli_preview(self, args) -> int:
        """本地预览消息内容（打印文本与解析模式）。"""
        print("=" * 50)
        print(f"解析模式: {args.parse_mode or '纯文本'}")
        print("-" * 50)
        print(args.text)
        print("=" * 50)
        return 0

    def cli_draft(self, args) -> int:
        """草稿管理: save / list / send。"""
        action = args.draft_action
        if action == 'save':
            draft_id = args.name or f"draft_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            # 若已存在同名草稿则覆盖
            self.drafts = [d for d in self.drafts if d.id != draft_id]
            draft = MessageDraft(
                id=draft_id,
                content=args.text,
                parse_mode=args.parse_mode or 'Markdown',
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                tags=[],
            )
            self.drafts.append(draft)
            self._save_drafts()
            print(f"✅ 草稿已保存 (ID: {draft.id})")
            return 0
        elif action == 'list':
            if not self.drafts:
                print("📭 没有保存的草稿")
                return 0
            for d in self.drafts:
                preview = d.content[:50] + ("..." if len(d.content) > 50 else "")
                print(f"- {d.id} [{d.parse_mode}] {preview}")
            return 0
        elif action == 'send':
            draft = next((d for d in self.drafts if d.id == args.name), None)
            if not draft:
                print(f"❌ 未找到草稿: {args.name}")
                return 1
            try:
                self._send_to_chat_sync(args.chat_id, draft.content, draft.parse_mode)
                self._record_history(draft.content, args.chat_id, 'sent')
                print(f"✅ 草稿 {draft.id} 已发送到 {args.chat_id}")
                return 0
            except Exception as e:
                self._record_history(draft.content, args.chat_id, 'failed', str(e))
                print(f"❌ 发送失败: {e}")
                return 1
        print(f"❌ 未知 draft 子命令: {action}")
        return 1

    def cli_broadcast(self, args) -> int:
        """向多个 chat 群发消息。"""
        chat_ids = [c.strip() for c in args.chats.split(',') if c.strip()]
        if not chat_ids:
            print("❌ 未提供有效 chat id")
            return 1
        ok = 0
        for cid in chat_ids:
            try:
                self._send_to_chat_sync(cid, args.text, args.parse_mode)
                self._record_history(args.text, cid, 'sent')
                print(f"✅ {cid}: 发送成功")
                ok += 1
            except Exception as e:
                self._record_history(args.text, cid, 'failed', str(e))
                print(f"❌ {cid}: {e}")
        print(f"完成: {ok}/{len(chat_ids)} 成功")
        return 0 if ok == len(chat_ids) else 1

    def cli_schedule(self, args) -> int:
        """在指定时间发送消息（阻塞等待至发送时刻，Ctrl+C 取消）。"""
        import threading
        try:
            target = datetime.strptime(args.at, "%Y-%m-%d %H:%M")
        except ValueError:
            print("❌ 时间格式错误，应为 'YYYY-MM-DD HH:MM'")
            return 1
        delay = (target - datetime.now()).total_seconds()
        if delay <= 0:
            print("❌ 调度时间必须在未来")
            return 1
        print(f"⏳ 已调度，将在 {args.at} 发送到 {args.chat_id}（等待 {delay:.0f} 秒，Ctrl+C 取消）")
        done = threading.Event()
        result = {}

        def _fire():
            try:
                self._send_to_chat_sync(args.chat_id, args.text, args.parse_mode)
                result['ok'] = True
            except Exception as e:
                result['err'] = str(e)
            finally:
                done.set()

        timer = threading.Timer(delay, _fire)
        timer.start()
        try:
            done.wait()
        except KeyboardInterrupt:
            timer.cancel()
            print("已取消")
            return 1
        if result.get('ok'):
            self._record_history(args.text, args.chat_id, 'sent')
            print("✅ 已发送")
            return 0
        self._record_history(args.text, args.chat_id, 'failed', result.get('err'))
        print(f"❌ 发送失败: {result.get('err')}")
        return 1

    def cli_config(self, args) -> int:
        """查看/修改配置。"""
        if args.config_action == 'show':
            bot_cfg = self.config.get('bot', {})
            token = bot_cfg.get('token', '')
            masked = (token[:4] + '***' + token[-4:]) if len(token) > 8 else ('***' if token else '(未设置)')
            print(f"Bot Token: {masked}")
            print(f"默认频道: {bot_cfg.get('default_channel') or '(未设置)'}")
            admins = bot_cfg.get('admin_users') or []
            print(f"管理员: {admins if admins else '(未限制)'}")
            print(f"默认解析模式: {self.config.get('editor', {}).get('default_parse_mode', 'MarkdownV2')}")
            return 0
        elif args.config_action == 'set-token':
            return self._write_local_config({'bot': {'token': args.value}})
        elif args.config_action == 'set-default-chat':
            return self._write_local_config({'bot': {'default_channel': args.value}})
        print(f"❌ 未知 config 子命令: {args.config_action}")
        return 1

    def _write_local_config(self, patch: Dict) -> int:
        """将补丁合并写入 config.local.yaml（不存在则创建）。"""
        path = 'config.local.yaml'
        data = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️ 读取 config.local.yaml 失败: {e}")
        for k, v in patch.items():
            data.setdefault(k, {}).update(v)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
            print(f"✅ 已写入 {path}")
            return 0
        except Exception as e:
            print(f"❌ 写入失败: {e}")
            return 1

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
        """交互式命令行模式（无需启动 Bot polling）。"""
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
                    channel = self.config.get('bot', {}).get('default_channel')
                    if not channel:
                        channel = input("请输入目标 chat id: ").strip()
                    if not channel:
                        print("[X] 未提供 chat id")
                        continue
                    if not self.current_draft:
                        print("[X] 没有当前草稿")
                        continue
                    try:
                        self._send_to_chat_sync(channel, self.current_draft.content, self.current_draft.parse_mode)
                        self._record_history(self.current_draft.content, channel, 'sent')
                        print(f"[OK] 已发送到 {channel}")
                    except Exception as e:
                        self._record_history(self.current_draft.content, channel, 'failed', str(e))
                        print(f"[X] 发送失败: {e}")

                else:
                    print("未知命令")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"错误: {e}")

        print("\n再见!")


def _build_arg_parser():
    """构建 CLI argparse 解析器。"""
    import argparse

    parser = argparse.ArgumentParser(prog="telegram-editor", description="Telegram 消息编辑与推送 CLI")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("send", help="发送消息到指定 chat")
    p.add_argument("--chat-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--parse-mode", default=None, choices=["Markdown", "MarkdownV2", "HTML"])

    p = sub.add_parser("preview", help="本地预览消息内容")
    p.add_argument("--text", required=True)
    p.add_argument("--parse-mode", default=None, choices=["Markdown", "MarkdownV2", "HTML"])

    p = sub.add_parser("draft", help="草稿管理")
    p.add_argument("draft_action", choices=["save", "list", "send"])
    p.add_argument("--name", help="草稿 ID（send 时必填）")
    p.add_argument("--text", help="草稿内容（save 时必填）")
    p.add_argument("--chat-id", help="目标 chat id（send 时必填）")
    p.add_argument("--parse-mode", default=None, choices=["Markdown", "MarkdownV2", "HTML"])

    p = sub.add_parser("broadcast", help="群发到多个 chat")
    p.add_argument("--chats", required=True, help="逗号分隔的 chat id 列表")
    p.add_argument("--text", required=True)
    p.add_argument("--parse-mode", default=None, choices=["Markdown", "MarkdownV2", "HTML"])

    p = sub.add_parser("schedule", help="定时发送消息")
    p.add_argument("--chat-id", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--at", required=True, help="发送时间，格式 YYYY-MM-DD HH:MM")
    p.add_argument("--parse-mode", default=None, choices=["Markdown", "MarkdownV2", "HTML"])

    p = sub.add_parser("config", help="查看/修改配置")
    p.add_argument("config_action", choices=["show", "set-token", "set-default-chat"])
    p.add_argument("value", nargs="?", help="set-token / set-default-chat 的值")

    return parser


def _ensure_utf8_stdout():
    """尽量让 stdout 支持 utf-8 输出（用于中文/emoji），失败则忽略。"""
    import sys
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]
    except Exception:
        pass


def main():
    """主入口：支持子命令、--cli 交互模式、无参数启动 Bot。"""
    import sys

    # --cli 交互模式（保持向后兼容）
    if len(sys.argv) >= 2 and sys.argv[1] == "--cli":
        _ensure_utf8_stdout()
        TelegramEditor().run_cli()
        return

    parser = _build_arg_parser()
    args = parser.parse_args()

    _ensure_utf8_stdout()
    editor = TelegramEditor()

    if not args.command:
        # 无子命令：启动 Bot
        editor.run()
        return

    # 子命令参数校验
    if args.command == "draft":
        if args.draft_action == "save" and not args.text:
            print("❌ draft save 需要 --text")
            sys.exit(2)
        if args.draft_action == "send" and (not args.name or not args.chat_id):
            print("❌ draft send 需要 --name 和 --chat-id")
            sys.exit(2)
    if args.command == "config" and args.config_action in ("set-token", "set-default-chat") and not args.value:
        print(f"❌ config {args.config_action} 需要提供 value")
        sys.exit(2)

    handlers = {
        "send": editor.cli_send,
        "preview": editor.cli_preview,
        "draft": editor.cli_draft,
        "broadcast": editor.cli_broadcast,
        "schedule": editor.cli_schedule,
        "config": editor.cli_config,
    }
    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        sys.exit(2)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()