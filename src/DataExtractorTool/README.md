# DataExtractorTool - 论文数据提取工具

## 工具列表

### 1. WorksExtractor - 智能论文数据提取工具

**文件**: `works_extractor.py`

**功能**: 从 OpenAlex 获取论文数据，支持智能切换数据源（API/数据库）

#### 核心特性

✅ **智能数据源切换**
- 小批量（< 1000条）→ PyAlex API
- 大批量（≥ 1000条）→ PostgreSQL 数据库
- 最新数据（≥ 2025-04）→ 强制使用 API

✅ **丰富的过滤条件**
- 关键词搜索
- 主题（topic）
- 年份范围
- 作者、机构、国家
- 期刊/来源
- 论文类型
- 开放获取状态
- 被引次数范围

✅ **统一的输出格式**
- 标准化的数据结构
- 同时返回元数据和原始数据
- 支持自定义字段选择

## 安装依赖

```bash
# 核心依赖
uv pip install pyalex asyncpg

# 可选：如果只使用API模式
uv pip install pyalex
```

## 配置

编辑 `config/db_config.py`：

```python
# PyAlex API 邮箱配置（推荐设置，获得更快的 API 响应）
PYALEX_EMAIL = "your-email@example.com"

# PostgreSQL 数据库配置（可选，用于大批量数据查询）
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'openalex',
    'user': 'your_username',
    'password': 'your_password'
}
```

**重要**:
- `PYALEX_EMAIL`: 设置后可获得更快的 API 响应速度（官方推荐）
- `DB_CONFIG`: 仅在需要大批量数据查询时配置

## 使用示例

### 基础用法（仅 API）

```python
from works_extractor import WorksExtractor
import asyncio

async def main():
    # 创建提取器（自动从配置文件读取邮箱）
    extractor = WorksExtractor()

    # 提取科学计量学领域论文
    result = await extractor.fetch_works(
        keywords="scientometrics",
        publication_year=(2020, 2023),
        work_type="article",
        cited_by_count=">10",
        limit=100
    )

    print(f"找到 {result['total']} 篇论文")
    print(f"数据源: {result['source']}")

    # 遍历结果
    for work in result['works'][:5]:
        print(f"- {work['title']} ({work['publication_year']})")
        print(f"  被引: {work['cited_by_count']}次")

asyncio.run(main())
```

### 高级用法（API + 数据库）

```python
import asyncpg
from works_extractor import WorksExtractor

async def main():
    # 配置数据库
    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'openalex',
        'user': 'your_user',
        'password': 'your_password'
    }

    # 连接数据库
    conn = await asyncpg.connect(**DB_CONFIG)

    async def query_fn(sql: str):
        records = await conn.fetch(sql)
        return [dict(r) for r in records]

    # 创建提取器（混合模式，自动从配置读取邮箱）
    extractor = WorksExtractor(
        query_fn=query_fn,
        auto_switch=True
    )

    # 大批量数据会自动使用数据库
    result = await extractor.fetch_works(
        keywords="machine learning",
        publication_year=(2018, 2022),
        cited_by_count=">50",
        limit=5000  # 自动切换到数据库
    )

    print(f"数据源: {result['source']}")  # 输出: database
    print(f"执行时间: {result['execution_time']:.2f}秒")

    await conn.close()

asyncio.run(main())
```

## 运行测试

### 方式1: 直接运行脚本

```bash
cd MetaSciToolUniverse/src/DataExtractorTool

# 运行测试（仅API模式）
python works_extractor.py

# 如果配置了数据库，测试会自动使用混合模式
```

### 方式2: 配置数据库后测试

1. 在 `MetaSciToolUniverse/config/` 创建 `db_config.py`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'openalex',
    'user': 'your_username',
    'password': 'your_password'
}
```

2. 运行测试:

```bash
python works_extractor.py
```

## 测试用例说明

测试脚本会自动执行以下测试：

### 测试 1: 科学计量学领域（API 模式）
- 关键词: "scientometrics"
- 年份: 2020-2023
- 论文类型: article
- 被引次数: > 10
- 数量: 100篇
- 预期数据源: API

### 测试 2: AI for Education 领域（API 模式）
- 关键词: "artificial intelligence education"
- 年份: 2022-2024
- 论文类型: article
- 被引次数: > 5
- 数量: 50篇
- 预期数据源: API

### 测试 3: 大批量数据（数据库模式，需配置数据库）
- 关键词: "machine learning"
- 年份: 2018-2022
- 论文类型: article
- 被引次数: > 50
- 数量: 5000篇
- 预期数据源: database

### 测试 4: 最新数据（强制 API 模式）
- 关键词: "large language model"
- 年份: > 2023
- 论文类型: article
- 数量: 30篇
- 预期数据源: API（强制）

## 输出说明

测试完成后会在 `src/DataExtractorTool/test_output/` 目录生成：

1. **文本报告**: `test_results_YYYYMMDD_HHMMSS.txt`
   - 测试摘要
   - Top论文列表
   - 统计信息

2. **JSON数据**: `test_data_YYYYMMDD_HHMMSS.json`
   - 完整的论文数据
   - 元数据信息
   - 便于后续分析

**输出目录结构**:
```
DataExtractorTool/
├── works_extractor.py
├── quick_test.py
├── README.md
└── test_output/              ← 测试输出保存在这里
    ├── test_results_20251117_123456.txt
    └── test_data_20251117_123456.json
```

## 辅助搜索功能（Helper Search）

### 问题背景

用户通常不知道精确的 `topic_id`、`author_id`、`institution_id` 或 `source_id`，这些 OpenAlex ID 需要事先查询才能使用。

### 解决方案

WorksExtractor 提供了辅助搜索方法，让用户可以通过**名称**搜索，获取候选 ID 列表，然后再用于精确过滤。

### 可用的搜索方法

#### 1. `search_topics(query, limit=10)`
搜索主题/学科领域

```python
# 搜索主题
topics = await extractor.search_topics("scientometrics", limit=5)
# 返回: [{"id": "T10001", "name": "Scientometrics", "description": "...", "works_count": 12345}, ...]

# 使用主题 ID 查询论文
result = await extractor.fetch_works(topic_id=topics[0]["id"], limit=100)
```

#### 2. `search_authors(query, limit=10)`
搜索作者

```python
# 搜索作者
authors = await extractor.search_authors("Geoffrey Hinton", limit=5)
# 返回: [{"id": "A1234567", "name": "Geoffrey Hinton", "works_count": 250, ...}, ...]

# 使用作者 ID 查询论文
result = await extractor.fetch_works(author_id=authors[0]["id"], limit=100)
```

#### 3. `search_institutions(query, limit=10)`
搜索机构

```python
# 搜索机构
institutions = await extractor.search_institutions("Stanford University", limit=5)
# 返回: [{"id": "I1234567", "name": "Stanford University", "country": "US", ...}, ...]

# 使用机构 ID 查询论文
result = await extractor.fetch_works(institution_id=institutions[0]["id"], limit=100)
```

#### 4. `search_sources(query, limit=10)`
搜索期刊/来源

```python
# 搜索期刊
sources = await extractor.search_sources("Nature", limit=5)
# 返回: [{"id": "S1234567", "name": "Nature", "type": "journal", ...}, ...]

# 使用期刊 ID 查询论文
result = await extractor.fetch_works(source_id=sources[0]["id"], limit=100)
```

#### 5. `smart_search(query_type, query, auto_select=False)`
统一搜索接口

```python
# 方式 1: 获取候选列表
topics = await extractor.smart_search("topic", "machine learning")

# 方式 2: 自动选择第一个结果
topic_id = await extractor.smart_search("topic", "machine learning", auto_select=True)

# query_type 可选值: "topic", "author", "institution", "source"
```

### 完整工作流程示例

```python
from works_extractor import WorksExtractor
import asyncio

async def main():
    extractor = WorksExtractor()

    # 步骤 1: 搜索主题
    topic_id = await extractor.smart_search("topic", "artificial intelligence", auto_select=True)

    # 步骤 2: 搜索机构
    institution_id = await extractor.smart_search("institution", "MIT", auto_select=True)

    # 步骤 3: 组合查询
    result = await extractor.fetch_works(
        topic_id=topic_id,
        institution_id=institution_id,
        cited_by_count=">100",
        publication_year=(2020, 2024),
        limit=50
    )

    print(f"找到 {result['total']} 篇论文")

asyncio.run(main())
```

### 运行辅助搜索示例

```bash
# 查看完整的辅助搜索示例（包含 6 个场景）
python src/DataExtractorTool/example_helper_search.py
```

该示例包含：
- 主题搜索示例
- 作者搜索示例
- 机构搜索示例
- 期刊搜索示例
- smart_search 使用示例
- 完整工作流程示例

## 参数说明

### fetch_works() 参数

#### 通用查询参数
- `keywords` (str): 关键词搜索
- `topic_id` (str): 主题ID，如 'T10028'
- `publication_year` (int|str|tuple): 年份过滤
  - 单个: 2023
  - 范围: (2020, 2023) 或 "2020-2023"
  - 不等式: ">2020", "<2023"

#### 高级过滤参数
- `author_id` (str): 作者ID
- `institution_id` (str): 机构ID
- `country_code` (str): 国家代码（US, CN等）
- `source_id` (str): 期刊/来源ID
- `work_type` (str): 论文类型（article, book-chapter等）
- `is_oa` (bool): 是否开放获取
- `cited_by_count` (int|str|tuple): 被引次数过滤

#### 结果控制参数
- `limit` (int): 最大返回数量（默认200）
- `sort_by` (str): 排序（默认 "cited_by_count:desc"）
- `fields` (List[str]): 返回字段列表

#### 数据源控制
- `force_api` (bool): 强制使用API
- `force_db` (bool): 强制使用数据库

## 常见问题

### Q1: 如何只使用API模式？

**A**: 不传入 `query_fn` 参数即可：

```python
extractor = WorksExtractor(email="your@email.com")
```

### Q2: 大批量数据一定会用数据库吗？

**A**: 是的，当 `limit >= 1000` 且 `auto_switch=True` 时，会自动切换到数据库。可以设置 `force_api=True` 强制使用API。

### Q3: 为什么最新数据要用API？

**A**: 本地数据库可能不包含2025年4月之后的数据，API可以获取最新发表的论文。

### Q4: 如何获取更多字段？

**A**: 使用 `fields` 参数：

```python
result = await extractor.fetch_works(
    keywords="AI",
    fields=["id", "title", "publication_year", "cited_by_count", "abstract"]
)
```

### Q5: 测试失败怎么办？

**A**: 检查以下几点：
1. 是否安装了 pyalex: `uv pip install pyalex`
2. 网络连接是否正常
3. 如果使用数据库，检查配置是否正确
4. 查看错误日志，确定具体问题

### Q6: 我不知道 topic_id 或 author_id 怎么办？

**A**: 使用辅助搜索功能！你可以通过名称搜索来获取 ID：

```python
# 搜索主题
topics = await extractor.search_topics("machine learning")
topic_id = topics[0]["id"]  # 获取第一个结果的 ID

# 或者使用 smart_search 自动选择
topic_id = await extractor.smart_search("topic", "machine learning", auto_select=True)

# 然后用于查询
result = await extractor.fetch_works(topic_id=topic_id, limit=100)
```

详细示例：`python src/DataExtractorTool/example_helper_search.py`

## 下一步开发

- [ ] 添加更多查询过滤条件
- [ ] 支持批量ID查询
- [ ] 添加结果缓存机制
- [ ] 支持异步批量处理
- [ ] 集成到 Agent MCP 工具
