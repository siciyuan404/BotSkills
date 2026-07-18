# Records API 端点完整参考

> 所有路径相对于 `RECORDS_API_URL`，例如 `$RECORDS_API_URL/api/categories`。
> 标记 `🔒` 的需要 `X-API-Key` 或 JWT Cookie 认证。
> 标记 `🍪` 的仅支持 JWT Cookie 认证。

---

## 分类树 /api/categories

> ⚠️ `link` 字段特殊行为：
> - **POST 时传了也无效**，服务端始终以 `/<name>` 自动生成
> - **PUT 时传了被忽略**，无法通过 API 修改 link
> - 前端路由为 `/category/<link>`，手动改动会导致 404

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/categories` | 公开 | — | `Record<string, CategoryData>` 嵌套树 |
| POST | `/api/categories` | 🔒 | `{path, name, icon?}` | 创建的节点（link 自动生成） |
| PUT | `/api/categories` | 🔒 | `{path, name, icon?}` | 更新后的节点（link 不可改） |
| DELETE | `/api/categories` | 🔒 | `{path}` | 删除确认（级联删除） |
| PATCH | `/api/categories` | 🔒 | `{sourcePath, targetPath, position}` | 移动确认 |

## 资源 /api/resources

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/resources` | 公开 | — | `Record<uuid, Resource>` |
| GET | `/api/resources/[id]` | 公开 | — | `Resource` 或 404 |
| POST | `/api/resources/[id]` | 🔒 | `Resource` 对象 | 创建确认 |
| PATCH | `/api/resources/[id]` | 🔒 | `Partial<Resource>` | 更新确认 |
| DELETE | `/api/resources/[id]` | 🔒 | — | 删除确认 |

## 资源信息 /api/resources-info

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/resources-info?uuid=xxx` | 公开 | — | `Resource` 或 404 |
| POST | `/api/resources-info` | 🔒 | `{uuid}` | `Resource` |

## 排行榜 /api/list

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/list` | 公开 | — | `{recommend, hot, latest, top, carousel}` |
| GET | `/api/list/override?type=hot` | 公开 | — | `{pinned, excluded, limit}` |
| POST | `/api/list/override` | 🔒 | `{type, pinned?, excluded?, limit?}` | 更新确认 |

## 对象存储 /api/storage

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/storage?prefix=xxx` | 🍪 | — | `{files: ObjectInfo[]}` |
| POST | `/api/storage` | 🍪 | Form: `file`, `key?` | 上传确认 |
| DELETE | `/api/storage?key=xxx` | 🍪 | — | 删除确认 |
| GET | `/api/storage/download/[...key]` | 🍪 | — | 文件流 + Content-Disposition |

## API Key /api/apikeys

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/apikeys` | 🔒 | — | `{keys: ApiKeyListItem[]}` |
| POST | `/api/apikeys` | 🔒 | `{name}` | `{success, key, meta}` (201) |
| DELETE | `/api/apikeys` | 🔒 | `{id}` | 吊销确认 |
| GET | `/api/apikeys/[id]/reveal` | 🔒 | — | `{plaintext}` |

## 站点设置 /api/settings

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/settings` | 公开 | — | `Record<key, value>` |
| GET | `/api/settings?meta=true` | 公开 | — | `Record<key, {value, description}>` |
| GET | `/api/settings/[key]` | 公开 | — | 单项或 404 |
| PUT | `/api/settings/[key]` | 🔒 | `{value, description?}` | 更新确认 |

## 标签 /api/tags

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/tags` | 公开 | — | `Record<string, Tag>` |

## 认证 /api/verify

| 方法 | 路径 | 认证 | 请求体 | 返回 |
|------|------|------|--------|------|
| GET | `/api/verify` | Cookie | — | `{valid: true}` 或 401 |
| POST | `/api/verify` | 公开 | `{password}` 或 `{token}` 或 `{refreshToken}` | 设置 cookie |

## 其他

| 方法 | 路径 | 认证 | 返回 |
|------|------|------|------|
| GET | `/api/config` | 公开 | `{owner, repo}` |
| GET | `/api/icons?page=1&pageSize=60` | 公开 | 分页图标列表 |
| GET | `/api/mcp` | 🔒 | `{services: McpService[]}` |
| POST | `/api/mcp` | 🔒 | 创建/更新 MCP 服务 |
| DELETE | `/api/mcp` | 🔒 | 删除 MCP 服务 |
