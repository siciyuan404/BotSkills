# Records 数据模型参考

## Resource（资源）

```typescript
interface Resource {
  name: string;                          // 资源名称 (必需)
  category: string;                      // 分类路径, 如 "工具/开发/AI" (必需)
  images: string[];                      // 图片文件名列表
  tags: string[] | Record<string, string>; // 标签
  source_links: Record<string, {         // 下载链接
    link: string;                        // 链接地址
    psw: string;                         // 提取密码
    size: string;                        // 文件大小
  }>;
  uploaded: number;                      // 上传时间戳 (毫秒)
  update_time: number;                   // 更新时间戳 (毫秒)
  introduction?: string;                 // 简介
  resource_information?: Record<string, string | number>; // 扩展信息
  link?: string;                         // 官方链接
  rating?: number;                       // 评分 (0-5)
  comments?: number;                     // 评论数
  download_count?: number;               // 下载次数
  download_limit?: number;               // 下载限制
  other_information?: Record<string, string | number>; // 其他信息
}
```

### 示例 JSON

```json
{
  "name": "Visual Studio Code",
  "category": "工具/开发",
  "images": ["vscode-cover.png", "vscode-ui.png"],
  "tags": ["编辑器", "开发工具", "免费"],
  "source_links": {
    "baidu": {
      "link": "https://pan.baidu.com/s/xxxxx",
      "psw": "abcd",
      "size": "89MB"
    },
    "quark": {
      "link": "https://pan.quark.cn/s/yyyyy",
      "psw": "",
      "size": "89MB"
    }
  },
  "uploaded": 1700000000000,
  "update_time": 1700500000000,
  "introduction": "Visual Studio Code 是由微软开发的免费开源代码编辑器...",
  "resource_information": {
    "版本": "v1.85",
    "语言": "多语言",
    "平台": "Windows/macOS/Linux"
  },
  "link": "https://code.visualstudio.com",
  "rating": 5,
  "download_count": 1234,
  "download_limit": 10
}
```

---

## Categories（分类树）

```typescript
interface CategoryData {
  icon: string;                          // 图标类名 (如 "RiFolder")
  link: string;                          // 外链 URL (可为空)
  items?: Record<string, CategoryData>;  // 子分类 (递归)
}

// 完整分类树
type Categories = Record<string, CategoryData>;
```

### 示例 JSON

```json
{
  "工具": {
    "icon": "RiTools",
    "link": "",
    "items": {
      "开发": {
        "icon": "RiCode",
        "link": "",
        "items": {
          "IDE": { "icon": "RiTerminalBox", "link": "", "items": {} },
          "AI": { "icon": "RiRobot", "link": "", "items": {} }
        }
      },
      "设计": {
        "icon": "RiPalette",
        "link": "",
        "items": {}
      }
    }
  },
  "教程": {
    "icon": "RiBook",
    "link": "",
    "items": {
      "前端": { "icon": "RiHtml5", "link": "", "items": {} },
      "后端": { "icon": "RiServer", "link": "", "items": {} }
    }
  }
}
```

### API 中的路径表示

- **分类树结构** 用嵌套对象表示，键为显示名
- **path 参数** 用字符串数组：`["工具", "开发", "AI"]`
- **资源的 category 字段** 用 `/` 分隔：`"工具/开发/AI"`

---

## List / 榜单数据

### 响应格式

```typescript
interface ListResponse {
  recommend: ListItem[];   // 手动精选
  hot: ListItem[];         // 按 download_count 排序
  latest: ListItem[];      // 按 uploaded 排序
  top: ListItem[];         // 手动精选 (独立于 recommend)
  carousel: string[];      // 轮播图 URL 数组
}

interface ListItem {
  uuid: string;
  name: string;
  category: string;
  images: string[];
  rating?: number;
  download_count?: number;
  update_time?: number;
  // ... 其他 Resource 字段
}
```

### 榜单覆写配置

```typescript
interface ListOverride {
  type: "hot" | "latest";
  pinned: string[];    // 强制置顶的 UUID
  excluded: string[];  // 强制排除的 UUID
  limit: number;       // 返回条数上限
}
```

---

## API Key

### Key 格式

```
rak_<48 hex characters>
例如: rak_a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
```

### 元数据

```typescript
interface ApiKeyListItem {
  id: string;          // Key ID (SHA-256 hash 前缀)
  name: string;        // 创建时指定的名称
  prefix: string;      // Key 前缀 (如 "rak_a1b2")
  createdAt: number;   // 创建时间戳
  lastUsedAt: number;  // 最后使用时间戳
}
```

### 限速

- 每个 Key: **60 请求/60 秒**
- 超过限制返回 `429 Too Many Requests`，带 `retryAfter` 秒数

---

## 站点设置

```typescript
// 键值对存储，value 为任意 JSON
type SiteSettings = Record<string, any>;

// 带元信息的设置
interface SiteSetting {
  key: string;
  value: any;
  description?: string;
  updated_at: number;
}
```
