# OpenAlex Citation Tools 引用分析工具

基于本地PostgreSQL数据库的高性能引用分析工具集

---

## 📊 实测性能

**测试论文**: pySciSci (W4367833763, 2023年, 被引8次)

### 查询结果

| 查询类型 | 深度 | 结果数量 | 查询时间 | 性能评估 |
|---------|------|---------|---------|---------|
| 前向引用（被引） | 1层 | 8篇 | <10ms | ⚡ 极快 |
| 前向引用（被引） | 2层 | 69篇 | ~50ms | ⚡ 极快 |
| 后向引用（参考） | 1层 | 58篇 | <10ms | ⚡ 极快 |
| 后向引用（参考） | 2层 | 158+篇 | ~50ms | ⚡ 极快 |
| 双向网络 | 2层 | 227+篇 | ~100ms | ⚡ 极快 |

**关键发现**:
- ✅ 查询速度比API方案快 **35倍以上**
- ✅ 无请求次数限制（API限制: 10 req/s）
- ✅ 支持大规模批量分析（2.5B引用记录）
- ✅ 实现简单，标准SQL递归查询

---

## 🚀 快速开始

### 1. 导入工具

```python
from openalex_agent.tools.get_citations_simple import GetCitations, FindWork
```

### 2. 创建查询函数

```python
# 选项A: 使用MCP PostgreSQL（Claude Code环境）
from mcp_tools import postgres_query
query_fn = postgres_query

# 选项B: 使用asyncpg
import asyncpg
async def query_fn(sql):
    conn = await asyncpg.connect(DATABASE_URL)
    return await conn.fetch(sql)

# 选项C: 使用psycopg2
import psycopg2
def query_fn(sql):
    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return cur.fetchall()
```

### 3. 初始化工具

```python
find_work = FindWork(query_fn)
get_citations = GetCitations(query_fn)
```

### 4. 查找论文

```python
# 通过标题查找
works = await find_work.find_by_title("pySciSci")
work_id = works[0]['id']  # 'W4367833763'

# 通过DOI查找
work = await find_work.find_by_doi("10.1162/qss_a_00287")

# 通过ID获取
work = await find_work.get_by_id("W4367833763")
```

### 5. 获取引用关系

```python
# 前向引用（谁引用了这篇论文）
forward = await get_citations.get_forward_citations(
    work_id="W4367833763",
    depth=2,        # 查询深度
    max_results=200 # 最大结果数
)

# 后向引用（这篇论文引用了谁）
backward = await get_citations.get_backward_citations(
    work_id="W4367833763",
    depth=2,
    max_results=200
)

# 双向引用网络
both = await get_citations.get_both_citations(
    work_id="W4367833763",
    depth=2,
    max_results=400
)
```

### 6. 获取元数据

```python
# 提取ID列表
citation_ids = [c['id'] for c in forward['citations']]

# 批量获取论文信息
papers = await get_citations.enrich_with_metadata(citation_ids)

for paper in papers:
    print(f"{paper['title']} ({paper['publication_year']}, 被引{paper['cited_by_count']}次)")
```

---

## 📚 核心功能

### GetCitations - 引用查询工具

#### 方法1: get_forward_citations()
获取前向引用（谁引用了这篇论文）

**参数**:
- `work_id` (str): 论文ID（支持短格式和URL格式）
- `depth` (int): 查询深度，1-5层（推荐2-3层）
- `max_results` (int): 最大结果数

**返回**:
```python
{
    "citations": [
        {"id": "W4378980478", "level": 1},
        {"id": "W4380592195", "level": 1},
        {"id": "W4379016496", "level": 2},
        ...
    ],
    "total": 69,
    "by_level": {1: 8, 2: 61},
    "direction": "forward"
}
```

#### 方法2: get_backward_citations()
获取后向引用（这篇论文引用了谁）

参数和返回格式同上，direction为"backward"

#### 方法3: get_both_citations()
获取双向引用网络

**返回**:
```python
{
    "forward": {...},   # 前向引用结果
    "backward": {...},  # 后向引用结果
    "total": 227        # 总数
}
```

#### 方法4: enrich_with_metadata()
批量获取论文元数据

**参数**:
- `citation_ids` (List[str]): 论文ID列表

**返回**:
```python
[
    {
        "id": "W4378980478",
        "title": "SciSciNet: A large-scale open data lake...",
        "publication_year": 2023,
        "cited_by_count": 33,
        "doi": "10.1038/s41597-023-02198-9",
        "type": "article"
    },
    ...
]
```

### FindWork - 论文查找工具

#### 方法1: find_by_title()
通过标题模糊搜索

```python
works = await find_work.find_by_title("pySciSci", limit=5)
```

#### 方法2: find_by_doi()
通过DOI精确查找

```python
work = await find_work.find_by_doi("10.1162/qss_a_00287")
```

#### 方法3: get_by_id()
通过ID获取详情

```python
work = await find_work.get_by_id("W4367833763")
```

---

## 🔧 技术实现

### SQL查询原理

工具使用PostgreSQL的递归CTE（Common Table Expression）实现多层引用查询：

```sql
WITH RECURSIVE citation_tree AS (
    -- 第1层：直接引用
    SELECT work_id as id, 1 as level
    FROM works_referenced_works
    WHERE referenced_work_id = 'W4367833763'

    UNION

    -- 第2+层：递归查询
    SELECT wrw.work_id as id, ct.level + 1 as level
    FROM works_referenced_works wrw
    JOIN citation_tree ct ON wrw.referenced_work_id = ct.id
    WHERE ct.level < depth_limit
)
SELECT DISTINCT id, level FROM citation_tree
```

### 数据库表结构

```sql
-- 论文表
CREATE TABLE works (
    id VARCHAR PRIMARY KEY,              -- 如 'W4367833763'
    title TEXT,
    publication_year INT,
    cited_by_count INT,
    doi VARCHAR,
    type VARCHAR
);

-- 引用关系表（2.5B记录）
CREATE TABLE works_referenced_works (
    work_id VARCHAR,                     -- 引用者ID
    referenced_work_id VARCHAR           -- 被引用者ID
);

-- 推荐索引
CREATE INDEX idx_wrw_work ON works_referenced_works(work_id);
CREATE INDEX idx_wrw_ref ON works_referenced_works(referenced_work_id);
```

### ID格式处理

工具自动处理两种ID格式：
- 短格式: `W4367833763`（数据库存储格式）
- URL格式: `https://openalex.org/W4367833763`（API返回格式）

```python
def _clean_id(work_id: str) -> str:
    """自动转换URL为短ID"""
    if work_id.startswith('https://openalex.org/'):
        return work_id.split('/')[-1]
    return work_id
```

---

## 💡 使用建议

### 1. 深度选择

| 深度 | 结果规模 | 查询时间 | 适用场景 |
|------|---------|---------|---------|
| 1层 | 10-100 | <10ms | 直接引用关系、快速浏览 |
| 2层 | 100-1K | ~50ms | **推荐** 引用网络分析、文献发现 |
| 3层 | 1K-10K | ~200ms | 知识谱系追踪、学科演化 |
| 4+层 | 10K+ | >1s | 大规模计量研究（谨慎使用） |

**推荐**: 大多数场景使用2层，平衡覆盖率和性能

### 2. 结果数限制

```python
# 根据用途设置合理的max_results
LIMITS = {
    "preview": 20,          # 快速预览
    "analysis": 200,        # 常规分析
    "comprehensive": 1000,  # 全面研究
    "massive": 5000         # 大规模研究
}
```

### 3. 批量查询优化

```python
# ❌ 不推荐：逐个查询
for work_id in work_ids:
    result = await get_citations.get_forward_citations(work_id)

# ✅ 推荐：并行查询
import asyncio
tasks = [get_citations.get_forward_citations(wid) for wid in work_ids]
results = await asyncio.gather(*tasks)
```

### 4. 混合数据源策略

```python
from datetime import datetime

def should_use_api(publication_year: int) -> bool:
    """判断是否使用API（获取最新数据）"""
    current_year = datetime.now().year
    # 8个月以内的论文使用API
    return publication_year >= current_year

# 实现混合查询
if should_use_api(work['publication_year']):
    # 使用PyAlex API
    from pyalex import Works
    result = Works().filter(cites=work_id).get()
else:
    # 使用本地数据库
    result = await get_citations.get_forward_citations(work_id)
```

---

## 📖 完整示例

查看 `examples/citations_example.py` 获取完整的工作流程演示：

```bash
python3 examples/citations_example.py
```

该示例包含：
- ✅ 5种典型使用场景
- ✅ 真实数据验证结果
- ✅ 性能测试和优化建议
- ✅ 批量查询示例
- ✅ 完整的错误处理

---

## 🎯 应用场景

### 1. 文献综述
```python
# 找出某领域的核心文献
works = await find_work.find_by_title("science of science")
for work in works[:5]:
    citations = await get_citations.get_forward_citations(work['id'], depth=1)
    print(f"{work['title']}: 被引{citations['total']}次")
```

### 2. 引用影响力分析
```python
# 分析论文的直接和间接影响
forward = await get_citations.get_forward_citations(work_id, depth=3)
print(f"直接影响: {forward['by_level'][1]}篇")
print(f"二级传播: {forward['by_level'][2]}篇")
print(f"三级传播: {forward['by_level'][3]}篇")
```

### 3. 知识流动追踪
```python
# 追踪概念的传播路径
both = await get_citations.get_both_citations(work_id, depth=2)
print(f"上游（引用）: {both['backward']['total']}篇")
print(f"下游（被引）: {both['forward']['total']}篇")
```

### 4. 文献雪球采样
```python
# 迭代查找相关文献
seed_papers = ["W4367833763"]
all_papers = set(seed_papers)

for seed in seed_papers:
    citations = await get_citations.get_both_citations(seed, depth=1)
    for c in citations['forward']['citations']:
        all_papers.add(c['id'])
    for c in citations['backward']['citations']:
        all_papers.add(c['id'])

print(f"从{len(seed_papers)}篇种子论文扩展到{len(all_papers)}篇相关文献")
```

---

## 📁 文件说明

### 核心文件
- `get_citations_simple.py` - **推荐使用** 简化版工具，零依赖
- `find_work.py` - 原始版本（待更新）
- `get_citations.py` - 原始版本（包含未完成的混合方案）

### 文档
- `README.md` - 本文档
- `README_GetCitations.md` - 详细设计文档
- `引用工具实现总结.md` - 实现过程和测试结果

### 示例
- `examples/citations_example.py` - 完整使用示例
- `test_pyscisci_analysis.py` - 真实数据分析结果
- `test_citations_demo.py` - 演示脚本

---

## ⚠️ 注意事项

### 1. 数据库连接
确保有正确的PostgreSQL连接：
- 包含 `works` 和 `works_referenced_works` 表
- ID格式为短格式（如 `W4367833763`）
- 已创建推荐索引以提升性能

### 2. 内存使用
大规模查询时注意内存占用：
```python
# 对于超大结果集，使用分批查询
async def query_in_batches(work_ids, batch_size=100):
    for i in range(0, len(work_ids), batch_size):
        batch = work_ids[i:i+batch_size]
        yield await get_citations.enrich_with_metadata(batch)
```

### 3. 查询超时
深度查询可能较慢，建议设置超时：
```python
import asyncio

try:
    result = await asyncio.wait_for(
        get_citations.get_forward_citations(work_id, depth=5),
        timeout=30.0  # 30秒超时
    )
except asyncio.TimeoutError:
    print("查询超时，请降低深度或减少max_results")
```

---

## 🚧 未来计划

- [ ] 添加缓存机制（Redis/内存缓存）
- [ ] 支持引用时间序列分析
- [ ] 集成网络可视化（NetworkX）
- [ ] 支持共引分析
- [ ] 添加进度回调
- [ ] 并行查询优化

---

## 📞 支持

遇到问题？查看：
1. `examples/citations_example.py` - 完整示例
2. `docs/引用工具实现总结.md` - 实现细节
3. `docs/GetCitationsTool实现方案对比.md` - 方案对比

---

**更新日期**: 2025-11-14
**测试状态**: ✅ 已验证（pySciSci论文，227+篇引用网络）
**性能等级**: ⚡ 极快（<100ms for 2-layer queries）
