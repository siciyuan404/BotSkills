#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Telegram Editor 测试套件。

不依赖真实 Bot Token 与网络，覆盖数据类健壮性、MarkdownV2 转义、
CLI 参数解析、权限校验逻辑与草稿覆盖逻辑。
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = 0
failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"[OK] {name}")
    else:
        failed += 1
        print(f"[X] {name}")


# ==================== 测试 1: 模块导入 ====================
print("=" * 50)
print("测试 1: 模块导入")
print("=" * 50)
try:
    from editor import TelegramEditor, MessageDraft, MessageHistory, _build_arg_parser
    check("类与解析器导入成功", True)
except Exception as e:
    check(f"导入失败: {e}", False)
    sys.exit(1)

try:
    import telegram  # noqa: F401
    check("python-telegram-bot 可用", True)
except ImportError:
    print("[!] python-telegram-bot 未安装（仅影响 Bot 模式，不影响本测试）")


# ==================== 测试 2: MessageDraft.from_dict 忽略未知字段 ====================
print("\n" + "=" * 50)
print("测试 2: MessageDraft.from_dict 健壮性")
print("=" * 50)
d = MessageDraft.from_dict({
    "id": "x", "content": "c", "parse_mode": "Markdown",
    "created_at": "t1", "updated_at": "t2", "tags": [],
    "unknown_field": "should_be_ignored", "author": 123,
})
check("未知字段被忽略且不抛错", d.id == "x" and d.content == "c")
check("已知字段正确填充", d.parse_mode == "Markdown" and d.tags == [])


# ==================== 测试 3: 序列化往返一致性 ====================
print("\n" + "=" * 50)
print("测试 3: 序列化往返")
print("=" * 50)
d2 = MessageDraft(id="d2", content="hi", parse_mode="HTML",
                 created_at="a", updated_at="b", tags=["t"])
check("draft 往返一致", MessageDraft.from_dict(d2.to_dict()).to_dict() == d2.to_dict())

h = MessageHistory(id="h1", content="c", channel="ch",
                   sent_at="s", status="sent", error_msg="err")
check("history 往返一致", MessageHistory.from_dict(h.to_dict()).to_dict() == h.to_dict())
check("history.from_dict 忽略未知字段",
      MessageHistory.from_dict({**h.to_dict(), "extra": 1}).id == "h1")


# ==================== 测试 4: escape_markdown_v2 ====================
print("\n" + "=" * 50)
print("测试 4: escape_markdown_v2")
print("=" * 50)
esc = TelegramEditor.escape_markdown_v2("a.b-c_d")
check("转义句点", "\\." in esc)
check("转义连字符", "\\-" in esc)
check("转义下划线", "\\_" in esc)
check("不破坏普通字母", "a" in esc and "b" in esc)
check("无特殊字符时不改动", TelegramEditor.escape_markdown_v2("abc") == "abc")


# ==================== 测试 5: CLI 参数解析 ====================
print("\n" + "=" * 50)
print("测试 5: CLI 参数解析器")
print("=" * 50)
ap = _build_arg_parser()
args = ap.parse_args(["send", "--chat-id", "123", "--text", "hi", "--parse-mode", "HTML"])
check("send 参数解析", args.command == "send" and args.chat_id == "123" and args.text == "hi" and args.parse_mode == "HTML")
args = ap.parse_args(["broadcast", "--chats", "1,2,3", "--text", "x"])
check("broadcast 参数解析", args.chats == "1,2,3" and args.text == "x")
args = ap.parse_args(["schedule", "--chat-id", "1", "--text", "x", "--at", "2099-01-01 10:00"])
check("schedule 参数解析", args.at == "2099-01-01 10:00")
args = ap.parse_args(["draft", "save", "--name", "n1", "--text", "t"])
check("draft save 参数解析", args.draft_action == "save" and args.name == "n1")
args = ap.parse_args(["draft", "list"])
check("draft list 参数解析", args.draft_action == "list")
args = ap.parse_args(["config", "show"])
check("config show 参数解析", args.config_action == "show")
args = ap.parse_args(["config", "set-token", "TOK"])
check("config set-token 参数解析", args.config_action == "set-token" and args.value == "TOK")


# ==================== 测试 6: 配置加载与权限校验 ====================
print("\n" + "=" * 50)
print("测试 6: 配置加载与权限校验")
print("=" * 50)
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


class _FakeUser:
    def __init__(self, uid):
        self.id = uid


class _FakeUpdate:
    def __init__(self, uid):
        self.effective_user = _FakeUser(uid)
        self.callback_query = None
        self.message = None


with tempfile.TemporaryDirectory() as td:
    orig = os.getcwd()
    os.chdir(td)
    try:
        editor = TelegramEditor(CONFIG_PATH)
        check("配置加载成功", isinstance(editor.config, dict))
        check("bot 配置段存在", "token" in editor.config.get("bot", {}))
        check("editor 配置段存在", "default_parse_mode" in editor.config.get("editor", {}))
        check("admin_users 字段存在", "admin_users" in editor.config.get("bot", {}))

        # 未配置 admin 时放行所有人
        editor.config['bot']['admin_users'] = []
        check("无 admin 配置时放行", editor._is_authorized(_FakeUpdate(999999)) is True)

        # 配置 admin 后仅放行列表内用户
        editor.config['bot']['admin_users'] = [111]
        check("非 admin 被拒", editor._is_authorized(_FakeUpdate(999999)) is False)
        check("admin 放行", editor._is_authorized(_FakeUpdate(111)) is True)
    finally:
        os.chdir(orig)


# ==================== 测试 7: draft save 覆盖同名草稿 ====================
print("\n" + "=" * 50)
print("测试 7: draft save 覆盖同名草稿")
print("=" * 50)


class _Args:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


with tempfile.TemporaryDirectory() as td:
    orig = os.getcwd()
    os.chdir(td)
    try:
        editor = TelegramEditor(CONFIG_PATH)
        editor.cli_draft(_Args(draft_action="save", name="dup", text="v1", parse_mode=None))
        editor.cli_draft(_Args(draft_action="save", name="dup", text="v2", parse_mode=None))
        dup = [d for d in editor.drafts if d.id == "dup"]
        check("同名草稿仅保留一个", len(dup) == 1)
        check("草稿内容已更新为 v2", dup[0].content == "v2")

        # list 返回 0 且不报错
        rc = editor.cli_draft(_Args(draft_action="list"))
        check("draft list 正常返回", rc == 0)

        # send 不存在的草稿返回 1
        rc = editor.cli_draft(_Args(draft_action="send", name="nope", chat_id="1"))
        check("send 不存在草稿返回失败码", rc == 1)
    finally:
        os.chdir(orig)


# ==================== 测试 8: preview / config show 不依赖网络 ====================
print("\n" + "=" * 50)
print("测试 8: preview / config show")
print("=" * 50)
with tempfile.TemporaryDirectory() as td:
    orig = os.getcwd()
    os.chdir(td)
    try:
        editor = TelegramEditor(CONFIG_PATH)
        rc = editor.cli_preview(_Args(text="hello", parse_mode="Markdown"))
        check("preview 返回 0", rc == 0)
        rc = editor.cli_config(_Args(config_action="show"))
        check("config show 返回 0", rc == 0)
    finally:
        os.chdir(orig)


print("\n" + "=" * 50)
print(f"结果: {passed} 通过, {failed} 失败")
print("=" * 50)
sys.exit(1 if failed else 0)
