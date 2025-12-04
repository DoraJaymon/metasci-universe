# AuthorTool - 统一作者查询工具

**v0.4.0** - 统一接口 + 智能路由 + 三级detail模式

---

## 🚀 核心特性

✅ **单一接口** - `AuthorQuery` 类处理所有查询
✅ **智能路由** - 批量查询(≥200)自动用数据库，找不到回退API
✅ **灵活输入** - 支持DOI(单/多) 或 作者ID(单/多)
✅ **三级输出** - basic(快) / summary(标准) / full(完整)
✅ **名字搜索** - 模糊匹配，按相关度排序

---

## 📖 快速开始

### 基本使用

```python
from src.AuthorTool import AuthorQuery
import asyncio

async def main():
    aq = AuthorQuery(verbose=True)

    # 查询单篇论文第一作者（标准信息）
    author = await aq.query("10.1016/j.joi.2017.08.007")
    print(f"{author['display_name']}: {author['works_count']} 论文")

asyncio.run(main())
```

---

## 💡 三级 detail_level 模式

| 模式 | 查询作者档案 | 包含字段 | 速度 | 适用场景 |
|------|------------|---------|------|---------|
| `basic` | ❌ 否 | 姓名、ORCID、机构 | ⚡ 快（1次API） | 快速预览、大批量 |
| `summary` | ✅ 是 | + works_count, cited_by_count | 🐢 慢（n+1次） | 标准查询（默认） |
| `full` | ✅ 是 | + h-index, topics, counts_by_year | 🐢 慢（n+1次） | 深入分析 |

---

## 📚 使用示例

### 1. 基本信息（快速预览）

```python
# Basic 模式：速度快10倍
authors = await aq.query(
    "10.1016/j.joi.2017.08.007",
    all_authors=True,
    detail_level='basic'
)

for author in authors:
    print(f"{author['display_name']} - {author['primary_affiliation']}")
```

### 2. 标准信息（文献计量指标）

```python
# Summary 模式：默认，包含 works_count, cited_by_count
author = await aq.query("10.1016/j.joi.2017.08.007")

print(f"论文数: {author['works_count']}")
print(f"引用数: {author['cited_by_count']}")
```

### 3. 完整信息（深入分析）

```python
# Full 模式：包含 h-index, topics 等所有字段
author = await aq.query(
    "10.1016/j.joi.2017.08.007",
    detail_level='full'
)

print(f"H-index: {author['summary_stats']['h_index']}")
print(f"主题: {author['topics'][0]['display_name']}")
```

### 4. 获取所有共同作者

```python
# 获取论文的所有作者
authors = await aq.query(
    "10.1016/j.joi.2017.08.007",
    all_authors=True
)

for i, author in enumerate(authors, 1):
    print(f"{i}. {author['display_name']} ({author['author_position_type']})")
```

### 5. 指定位置作者

```python
# 查询第二作者
second_author = await aq.query(
    "10.1016/j.joi.2017.08.007",
    author_position=2
)
```

### 6. 批量查询

```python
# 批量查询（≥200自动用数据库）
dois = [...]  # 300个DOI
results = await aq.query(dois, batch_threshold=200)
```

### 7. 按名字搜索

```python
# 模糊搜索，按相关度和引用数排序
authors = await aq.search_by_name("Aria", limit=10)

for author in authors:
    print(f"{author['display_name']}: {author['works_count']} 论文")
```

### 8. 自定义字段

```python
# 只返回需要的字段
author = await aq.query(
    "10.1016/j.joi.2017.08.007",
    fields=['display_name', 'works_count', 'cited_by_count']
)
```

---

## 🎯 API 参考

### AuthorQuery 类

```python
class AuthorQuery(email=None, verbose=False)
```

### query() 方法

```python
async def query(
    identifiers: str | List[str],     # DOI 或 作者ID
    author_position: int = 1,         # 作者位置（1=第一作者）
    all_authors: bool = False,        # 返回所有共同作者
    detail_level: str = 'summary',    # 'basic' | 'summary' | 'full'
    fields: List[str] = None,         # 自定义字段
    batch_threshold: int = 200,       # 批量阈值
    force_source: str = None          # 'api' | 'db' | None
) -> Dict | List[Dict]
```

**参数说明:**
- `identifiers`: DOI 或 作者ID（单个或列表）
- `author_position`: 作者位置（仅DOI有效，1=第一作者）
- `all_authors`: 返回所有共同作者（仅DOI有效）
- `detail_level`:
  - `'basic'`: 基本信息（快）
  - `'summary'`: 标准信息（默认）
  - `'full'`: 完整信息
- `fields`: 自定义字段列表（覆盖 detail_level）
- `batch_threshold`: 批量查询阈值（默认200）
- `force_source`: 强制数据源（api/db/None）

### search_by_name() 方法

```python
async def search_by_name(
    name: str,                        # 作者名字
    limit: int = 10,                  # 返回数量
    detail_level: str = 'summary',    # 输出详细程度
    fields: List[str] = None,         # 自定义字段
    use_db: bool = True               # 使用数据库
) -> List[Dict]
```

---

## 🔍 摘要字段列表

`detail_level='summary'` 返回的核心字段：

```python
[
    'id',                          # OpenAlex ID
    'display_name',                # 作者姓名
    'orcid',                       # ORCID
    'works_count',                 # 论文数
    'cited_by_count',              # 引用数
    'author_position_in_paper',    # 在论文中的位置
    'author_position_type',        # 位置类型 (first/middle/last)
    'is_corresponding',            # 是否通讯作者
    'primary_affiliation',         # 主要机构
    'primary_affiliation_country', # 机构国家
    'data_source',                 # 数据源 (api/database)
    'query_timestamp'              # 查询时间
]
```

---

## 📊 性能对比

### detail_level 性能测试（单篇论文2作者）

| 模式 | API 调用 | 查询时间 | 加速比 |
|------|---------|---------|-------|
| `basic` | 1次 | ~0.5秒 | **10x** |
| `summary` | 3次 | ~2.5秒 | 1x |
| `full` | 3次 | ~2.5秒 | 1x |

---

## 🔄 智能路由策略

```
查询数量 < batch_threshold (默认200)
  ↓
使用 API（数据最新）

查询数量 ≥ batch_threshold
  ↓
使用数据库（速度快）
  ↓
如果找不到，回退到 API
```

---

## 🗂️ 文件结构

```
src/AuthorTool/
├── __init__.py          # 导出 AuthorQuery 和 query_authors
├── author_query.py      # 统一查询类（主接口）
├── _internal.py         # 内部依赖函数（不对外）
└── testpy/              # 测试文件
    ├── test_author_query.py
    └── test_new_features.py
```

---

## 🧪 测试

```bash
# 基础测试
python src/AuthorTool/testpy/test_author_query.py

# 新功能测试
python src/AuthorTool/testpy/test_new_features.py
```

---

## 💼 使用场景建议

| 场景 | 推荐配置 |
|------|---------|
| **快速预览大量论文** | `detail_level='basic'`, `all_authors=True` |
| **标准文献计量分析** | `detail_level='summary'`（默认） |
| **深入研究分析** | `detail_level='full'` |
| **查找特定研究者** | `search_by_name()` |
| **批量处理** | 设置 `batch_threshold` 或 `force_source='db'` |

---

## 📝 版本历史

### v0.4.0 (2025-11-25)
- ✨ 重构为统一接口，只导出 `AuthorQuery`
- ✨ 移除 `quick_mode`，改为三级 `detail_level`
- ✨ 新增 `all_authors` 参数
- ✨ 新增 `search_by_name()` 方法
- 🗑️ 移除旧函数导出
- 📦 精简文件结构（3个py文件）

### v0.3.0
- 统一查询类

### v0.2.0
- 数据库支持

### v0.1.0
- 初始版本

---

## 🎓 完整示例

```python
from src.AuthorTool import AuthorQuery
import asyncio

async def demo():
    aq = AuthorQuery(verbose=True)

    # 场景1: 快速预览（basic）
    print("\n=== 场景1: 快速预览 ===")
    authors = await aq.query(
        "10.1016/j.joi.2017.08.007",
        all_authors=True,
        detail_level='basic'
    )
    for author in authors:
        print(f"{author['display_name']} - {author['primary_affiliation']}")

    # 场景2: 标准查询（summary）
    print("\n=== 场景2: 标准查询 ===")
    author = await aq.query("10.1016/j.joi.2017.08.007")
    print(f"论文数: {author['works_count']}, 引用数: {author['cited_by_count']}")

    # 场景3: 深入分析（full）
    print("\n=== 场景3: 深入分析 ===")
    author = await aq.query("10.1016/j.joi.2017.08.007", detail_level='full')
    print(f"H-index: {author['summary_stats']['h_index']}")

    # 场景4: 按名字搜索
    print("\n=== 场景4: 按名字搜索 ===")
    results = await aq.search_by_name("Aria", limit=5)
    for author in results:
        print(f"{author['display_name']}: {author['works_count']} 论文")

    # 场景5: 批量查询
    print("\n=== 场景5: 批量查询 ===")
    dois = ["10.1016/j.joi.2017.08.007", "10.1007/s11192-009-0146-3"]
    results = await aq.query(dois)
    for author in results:
        print(f"{author['display_name']} - {author['source_doi']}")

asyncio.run(demo())
```

---

**完成！AuthorTool 现在更简洁、更强大、更易用 🎉**
