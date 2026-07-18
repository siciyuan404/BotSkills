---
name: records-skill
description: >
  Records 资源管理系统远程运维。纯 HTTP API 客户端模式，仅需配置 `$RECORDS_API_BASE`（部署域名）和
  `$RECORDS_API_KEY`（API Key），无需本地项目代码。支持：分类树 CRUD、资源 CRUD、
  Cloudflare R2 存储文件管理、API Key 签发与吊销、榜单（hot/latest/recommend/top）配置、
  站点设置读写。当用户提到 Records、资源管理站、分类树配置、添加/编辑资源、
  R2 存储文件操作、API Key 管理、热门/推荐/最新榜单设置时使用。
---

# Records 资源管理系统 — API 客户端

通过 HTTP API 远程操作 Records 后端。仅需两个配置项：

```bash
export RECORDS_API_BASE="https://your-records.example.com"   # 部署域名，无尾斜杠
export RECORDS_API_KEY="rak_xxxx..."                          # API Key，格式 rak_<48hex>
```

验证连通性：

```bash
curl -s "$RECORDS_API_BASE/api/config" | head -c 200
# 预期返回: { "owner": "mxrain", "repo": "zyt", ... }
```

## 认证

| 方式 | 适用端点 | 说明 |
|------|---------|------|
| `X-API-Key` header | 所有写操作 | `curl -H "X-API-Key: $RECORDS_API_KEY" ...` |
| 无需认证 | GET 读操作 | 分类/资源/榜单/设置 读取公开 |

例外：`/api/storage` 系列端点只接受 JWT Cookie，不支持 API Key。文件直传建议通过浏览器操作，或获取签名 URL 后下载。

## 核心数据模型

### Resource

```json
{
  "name": "VS Code 扩展包",
  "category": "工具/开发",
  "images": ["cover.png", "shot1.png"],
  "tags": ["编辑器", "前端"],
  "source_links": {
    "百度网盘": { "link": "https://pan.baidu.com/s/xxx", "psw": "abcd", "size": "1.2GB" }
  },
  "uploaded": 1700000000000,
  "update_time": 1700000000000,
  "introduction": "精选 VS Code 扩展合集",
  "resource_information": { "版本": "v2.0", "语言": "中文" },
  "rating": 4,
  "download_count": 1234,
  "download_limit": 0
}
```

### Categories

嵌套递归结构，`icon` 使用 RemixIcon 类名：

```json
{
  "工具": { "icon": "RiTools", "link": "", "items": {
    "开发": { "icon": "RiCode", "link": "", "items": {} }
  }},
  "教程": { "icon": "RiBook", "link": "", "items": {} }
}
```

资源通过 `category` 字段（`"工具/开发"`）关联到分类路径。

## 分类管理 API

```
POST   /api/categories      新增分类（正文 JSON）
PUT    /api/categories      更新分类（改名/图标/链接）
DELETE /api/categories      删除分类及子节点
PATCH  /api/categories      移动分类（排序/更换父节点）
GET    /api/categories      读取全部分类树
```

```bash
# 读取分类树
curl -s "$RECORDS_API_BASE/api/categories"

# 根级新增
curl -s -X POST "$RECORDS_API_BASE/api/categories" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":[], "name":"新根分类", "icon":"RiFolder", "link":""}'

# 在"工具"下建子分类
curl -s -X POST "$RECORDS_API_BASE/api/categories" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":["工具"], "name":"AI工具", "icon":"RiRobot", "link":""}'

# 更新分类
curl -s -X PUT "$RECORDS_API_BASE/api/categories" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":["工具","AI工具"], "name":"人工智能工具", "icon":"RiCpu"}'

# 删除分类
curl -s -X DELETE "$RECORDS_API_BASE/api/categories" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"path":["工具","AI工具"]}'

# 移动分类
curl -s -X PATCH "$RECORDS_API_BASE/api/categories" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"sourcePath":["工具","AI工具"], "targetPath":["教程"], "position":"inside"}'
```

`position`: `inside`（作为子节点，默认）| `before`（同级前）| `after`（同级后）

## 资源管理 API

```
GET     /api/resources                         全部资源（Record<uuid, Resource>）
POST    /api/resources-info                    单个资源详情（body: { uuid }）
POST    /api/resources/:uuid                   创建/覆写资源
PATCH   /api/resources/:uuid                   局部更新资源字段
DELETE  /api/resources/:uuid                   删除资源
```

```bash
# 列出全部
curl -s "$RECORDS_API_BASE/api/resources"

# 获取单个
curl -s -X POST "$RECORDS_API_BASE/api/resources-info" \
  -H "Content-Type: application/json" \
  -d '{"uuid": "550e8400-e29b-41d4-a716-446655440000"}'

# 创建资源（用文件传入）
cat > /tmp/new-resource.json << 'JSON'
{
  "name": "新资源",
  "category": "工具/开发/AI",
  "images": [],
  "tags": [],
  "source_links": {},
  "uploaded": 1700000000000,
  "update_time": 1700000000000
}
JSON

curl -s -X POST "$RECORDS_API_BASE/api/resources/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/new-resource.json

# 局部更新
curl -s -X PATCH "$RECORDS_API_BASE/api/resources/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"download_count": 999, "rating": 5}'

# 删除
curl -s -X DELETE "$RECORDS_API_BASE/api/resources/550e8400-e29b-41d4-a716-446655440000" \
  -H "X-API-Key: $RECORDS_API_KEY"
```

## 对象存储（R2）API

```
GET     /api/storage?prefix=<path>    列出文件（需 JWT Cookie）
POST    /api/storage                  上传文件（form-data，需 JWT Cookie）
DELETE  /api/storage?key=<path>       删除文件（需 JWT Cookie）
```

> 存储端点仅接受 JWT Cookie 认证，不支持 `X-API-Key`。在 agent 环境下，
> 操作文件时建议使用获取签名 URL 的方式。

```bash
# 列出 R2 文件
curl -s "$RECORDS_API_BASE/api/storage?prefix=images/" -H "Cookie: token=$JWT_TOKEN"

# 获取文件签名下载 URL（通过调用 lib/storage/r2.ts 的 getFileUrl）
# 生成后可直接 wget/curl 下载
```

## API Key 管理 API

```
GET     /api/apikeys    列出全部 Key（元信息）
POST    /api/apikeys    签发新 Key（body: { name }）
DELETE  /api/apikeys    吊销 Key（body: { id }）
```

```bash
# 列出
curl -s "$RECORDS_API_BASE/api/apikeys" -H "X-API-Key: $RECORDS_API_KEY"

# 签发（返回明文，仅此一次）
curl -s -X POST "$RECORDS_API_BASE/api/apikeys" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "agent-bot"}'

# 吊销
curl -s -X DELETE "$RECORDS_API_BASE/api/apikeys" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": "k1a2b3c4"}'
```

## 榜单与列表 API

```
GET  /api/list              获取全部榜单数据
GET  /api/list/override?type=<hot|latest|recommend|top>  获取 override 配置
POST /api/list/override     配置 override
```

```bash
# 查看榜单呈现
curl -s "$RECORDS_API_BASE/api/list"

# 查看 override 配置
curl -s "$RECORDS_API_BASE/api/list/override?type=hot"

# 配置热榜置顶/排除
curl -s -X POST "$RECORDS_API_BASE/api/list/override" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"hot", "pinned":["uuid1","uuid2"], "excluded":["uuid3"], "limit":50}'
```

榜单类型：

| 榜单 | 排序规则 | 可 override |
|------|---------|-------------|
| `recommend` | 手动精选 UUID 列表 | pinned / excluded |
| `top` | 手动精选 UUID 列表 | pinned / excluded |
| `hot` | `download_count DESC, update_time DESC` | pinned / excluded / limit |
| `latest` | `uploaded DESC` | pinned / excluded / limit |
| `carousel` | 图片 URL 数组，手动配置 | — |

## 站点设置 API

```
GET  /api/settings              全部设置（扁平 key-value）
GET  /api/settings?meta=true    带元信息的设置列表
PUT  /api/settings/:key         更新单项设置
```

```bash
# 读取
curl -s "$RECORDS_API_BASE/api/settings"

# 更新
curl -s -X PUT "$RECORDS_API_BASE/api/settings/siteTitle" \
  -H "X-API-Key: $RECORDS_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"value":"我的资源站"}'
```

## 常见组合场景

### 1. 新增资源（分类不存在时自动创建）

1. `GET /api/categories` 检查分类路径是否存在
2. 若不存在，逐级 POST 创建
3. 用 `uuidgen`、`python3 -c "import uuid; print(uuid.uuid4())"` 或在线工具生成 UUID
4. 构造 Resource JSON → `POST /api/resources/:uuid`
5. 如需上首页推荐 → `POST /api/list/override` 追加到 recommend

### 2. 批量导入资源

- 按行/文件读取源数据
- 逐条映射到 Resource 结构
- 注意 API 限速：每 Key 60次/60秒
- 全部写入后 `GET /api/resources` 验证

### 3. 为资源补充下载链接

1. `POST /api/resources-info` 获取现有数据
2. 合并新字段（不覆盖已有）
3. `PATCH /api/resources/:uuid` 只传变更字段

### 4. 配置首页推荐

1. `GET /api/list` 看当前展现
2. `GET /api/resources` 挑资源
3. `POST /api/list/override` 设置 recommend 的 pinned 列表

## 故障排查

| HTTP状态 | 常见原因 | 处理 |
|----------|---------|------|
| 401 | API Key 无效/过期 | 检查 `RECORDS_API_KEY` 值 |
| 401 on /api/storage | 存储端不支持 X-API-Key | 需 JWT Cookie，改用脚本获取签名 URL |
| 404 | UUID 不存在 | `GET /api/resources` 确认 |
| 429 | 触发限速 | 等待 `retryAfter` 秒，控制并发 |
| 400 | 请求体不符合 schema | 检查字段名/类型/嵌套结构 |

## 注意事项

- **所有写操作需 `X-API-Key` header**，读操作公开
- **`GET /api/resources` 返回 `{ uuid: Resource }`** 对象（非数组）
- **`GET /api/categories` 返回嵌套对象**（非数组）
- **category 字段格式**：`"父分类/子分类"` 用 `/` 分隔
- **path 参数**：分类 API 中的 `path` 是 display name 字符串数组，非 slug
- **限速**：每 Key 60次/60秒
- **签名 URL**：R2 文件签名 URL 默认 3600 秒过期
