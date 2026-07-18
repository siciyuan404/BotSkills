#!/usr/bin/env python3
"""
Records API Client — 通过 HTTP API 操作 Records 资源管理系统

配置：
  RECORDS_API_URL  — Records 后端地址 (如 https://records.example.com)
  RECORDS_API_KEY  — API Key, 格式 rak_<48hex>

用法：
  python records_api.py <domain> <action> [options]

  python records_api.py categories list
  python records_api.py categories create --path "工具,开发" --name "AI" --icon "RiRobot"
  python records_api.py resources create --uuid "xxx" --file resource.json
  python records_api.py lists show
  python records_api.py storage url --key "images/x.png" --expires 7200
"""

import os
import sys
import json
import argparse
import uuid as uuid_mod
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode


API_URL = os.environ.get("RECORDS_API_URL", "")
API_KEY = os.environ.get("RECORDS_API_KEY", "")


def _req(method, path, body=None):
    """发送 HTTP 请求并返回 (status, data) 或报错。"""
    if not API_URL:
        sys.exit("错误: RECORDS_API_URL 未设置")
    url = f"{API_URL.rstrip('/')}{path}"
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            content = resp.read()
            if not content:
                return resp.status, None
            return resp.status, json.loads(content)
    except HTTPError as e:
        msg = e.read().decode("utf-8", errors="replace")
        sys.exit(f"HTTP {e.code}: {msg}")
    except URLError as e:
        sys.exit(f"连接失败: {e.reason}")


def cmd_categories(args):
    if args.action == "list":
        _, data = _req("GET", "/api/categories")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "create":
        path = [p.strip() for p in args.path.split(",")] if args.path else []
        body = {"path": path, "name": args.name}
        if args.icon:
            body["icon"] = args.icon
        if args.link:
            body["link"] = args.link
        status, data = _req("POST", "/api/categories", body)
        print(f"[{status}] 创建成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "update":
        path = [p.strip() for p in args.path.split(",")] if args.path else []
        body = {"path": path, "name": args.name}
        if args.icon:
            body["icon"] = args.icon
        if args.link:
            body["link"] = args.link
        status, data = _req("PUT", "/api/categories", body)
        print(f"[{status}] 更新成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "delete":
        path = [p.strip() for p in args.path.split(",")] if args.path else []
        status, data = _req("DELETE", "/api/categories", {"path": path})
        print(f"[{status}] 已删除")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "move":
        from_path = [p.strip() for p in args.from_path.split(",")] if args.from_path else []
        to_path = [p.strip() for p in args.to_path.split(",")] if args.to_path else []
        body = {
            "sourcePath": from_path,
            "targetPath": to_path,
            "position": args.position or "inside",
        }
        status, data = _req("PATCH", "/api/categories", body)
        print(f"[{status}] 移动成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 categories 子命令: {args.action}")


def cmd_resources(args):
    if args.action == "list":
        _, data = _req("GET", "/api/resources")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "get":
        if not args.uuid:
            sys.exit("需要 --uuid")
        _, data = _req("GET", f"/api/resources/{args.uuid}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "create":
        if not args.uuid:
            sys.exit("需要 --uuid")
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                body = json.load(f)
        else:
            sys.exit("需要 --file (资源 JSON 文件)")
        status, data = _req("POST", f"/api/resources/{args.uuid}", body)
        print(f"[{status}] 创建/更新成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "update":
        if not args.uuid:
            sys.exit("需要 --uuid")
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                body = json.load(f)
        elif args.field and args.value is not None:
            val = args.value
            try:
                val = json.loads(args.value)
            except (json.JSONDecodeError, ValueError):
                pass
            body = {args.field: val}
        else:
            sys.exit("需要 --file 或 --field/--value")
        status, data = _req("PATCH", f"/api/resources/{args.uuid}", body)
        print(f"[{status}] 更新成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "delete":
        if not args.uuid:
            sys.exit("需要 --uuid")
        status, data = _req("DELETE", f"/api/resources/{args.uuid}")
        print(f"[{status}] 已删除")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 resources 子命令: {args.action}")


def cmd_storage(args):
    if args.action == "list":
        params = {}
        if args.prefix:
            params["prefix"] = args.prefix
        qs = f"?{urlencode(params)}" if params else ""
        status, data = _req("GET", f"/api/storage{qs}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "url":
        if not args.key:
            sys.exit("需要 --key")
        expires = args.expires or 3600
        # Get presigned URL via JS — not directly available as API endpoint.
        # We simulate by reading from r2 module if source available, otherwise
        # tell user to get it manually.
        print(f"签名 URL 需要通过 R2 SDK 生成。")
        print(f"目标: {API_URL}/api/storage/download/{args.key}")
        print(f"如需直接下载，请在浏览器访问上述地址（需 JWT 登录）。")
        _, data = _req("GET", "/api/storage")
        if data:
            matching = [f for f in data.get("files", []) if args.key in f.get("key", "")]
            if matching:
                for f in matching:
                    print(json.dumps(f, ensure_ascii=False))
            else:
                print(f"未找到匹配 '{args.key}' 的文件，列出全部:")
                print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "remove":
        if not args.key:
            sys.exit("需要 --key")
        status, data = _req("DELETE", f"/api/storage?key={args.key}")
        print(f"[{status}] 已删除")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 storage 子命令: {args.action}")


def cmd_lists(args):
    if args.action == "show":
        _, data = _req("GET", "/api/list")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "override":
        if not args.type:
            sys.exit("需要 --type (hot|latest)")
        body = {"type": args.type}
        if args.pinned is not None:
            body["pinned"] = [p.strip() for p in args.pinned.split(",") if p.strip()]
        if args.excluded is not None:
            body["excluded"] = [p.strip() for p in args.excluded.split(",") if p.strip()]
        if args.limit is not None:
            body["limit"] = int(args.limit)
        status, data = _req("POST", "/api/list/override", body)
        print(f"[{status}] 覆写配置更新成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 lists 子命令: {args.action}")


def cmd_settings(args):
    if args.action == "list":
        meta = "?meta=true" if args.meta else ""
        _, data = _req("GET", f"/api/settings{meta}")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "update":
        if not args.key or args.value is None:
            sys.exit("需要 --key 和 --value")
        val = args.value
        try:
            val = json.loads(args.value)
        except (json.JSONDecodeError, ValueError):
            pass
        status, data = _req("PUT", f"/api/settings/{args.key}", {"value": val})
        print(f"[{status}] 更新成功")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 settings 子命令: {args.action}")


def cmd_apikeys(args):
    if args.action == "list":
        _, data = _req("GET", "/api/apikeys")
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        sys.exit(f"未知 apikeys 子命令: {args.action}")


def cmd_tags(args):
    _, data = _req("GET", "/api/tags")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_gen_uuid(args):
    """生成一个新的 UUID v4"""
    new_uuid = str(uuid_mod.uuid4())
    print(new_uuid)


def cmd_verify(args):
    """验证连通性"""
    status, data = _req("GET", "/api/config")
    print(f"[{status}] 连通成功")
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Records API Client")
    sub = parser.add_subparsers(dest="domain", required=True)

    # categories
    cat = sub.add_parser("categories", help="分类树操作")
    cat.add_argument("action", choices=["list", "create", "update", "delete", "move"])
    cat.add_argument("--path", help="分类路径, 逗号分隔 (如 '工具,开发')")
    cat.add_argument("--from-path", help="移动操作: 源路径")
    cat.add_argument("--to-path", help="移动操作: 目标路径")
    cat.add_argument("--position", choices=["before", "after", "inside"], help="移动位置 (默认 inside)")
    cat.add_argument("--name", help="分类显示名称")
    cat.add_argument("--icon", help="图标名 (如 RiFolder)")
    cat.add_argument("--link", help="链接 URL")

    # resources
    res = sub.add_parser("resources", help="资源操作")
    res.add_argument("action", choices=["list", "get", "create", "update", "delete"])
    res.add_argument("--uuid", help="资源 UUID")
    res.add_argument("--file", help="JSON 文件路径 (创建/更新)")
    res.add_argument("--field", help="字段名 (局部更新)")
    res.add_argument("--value", help="字段值 (局部更新)")

    # storage
    sto = sub.add_parser("storage", help="R2 对象存储操作")
    sto.add_argument("action", choices=["list", "url", "remove"])
    sto.add_argument("--prefix", help="对象键前缀")
    sto.add_argument("--key", help="对象键 (完整路径)")
    sto.add_argument("--expires", type=int, help="签名 URL 过期秒数 (默认 3600)")

    # lists
    lst = sub.add_parser("lists", help="排行榜/列表操作")
    lst.add_argument("action", choices=["show", "override"])
    lst.add_argument("--type", choices=["hot", "latest"], help="榜单类型")
    lst.add_argument("--pinned", help="置顶 UUID 列表, 逗号分隔")
    lst.add_argument("--excluded", help="排除 UUID 列表, 逗号分隔")
    lst.add_argument("--limit", type=int, help="返回条数上限")

    # settings
    setg = sub.add_parser("settings", help="站点配置操作")
    setg.add_argument("action", choices=["list", "update"])
    setg.add_argument("--key", help="配置键名")
    setg.add_argument("--value", help="配置值")
    setg.add_argument("--meta", action="store_true", help="显示元信息描述")

    # apikeys
    apk = sub.add_parser("apikeys", help="API Key 管理 (只读)")
    apk.add_argument("action", choices=["list"])

    # utility
    sub.add_parser("tags", help="列出所有标签")
    sub.add_parser("gen-uuid", help="生成 UUID v4")
    sub.add_parser("verify", help="验证与 Records 后端的连通性")

    args = parser.parse_args()

    if args.domain == "categories":
        cmd_categories(args)
    elif args.domain == "resources":
        cmd_resources(args)
    elif args.domain == "storage":
        cmd_storage(args)
    elif args.domain == "lists":
        cmd_lists(args)
    elif args.domain == "settings":
        cmd_settings(args)
    elif args.domain == "apikeys":
        cmd_apikeys(args)
    elif args.domain == "tags":
        cmd_tags(args)
    elif args.domain == "gen-uuid":
        cmd_gen_uuid(args)
    elif args.domain == "verify":
        cmd_verify(args)


if __name__ == "__main__":
    main()
