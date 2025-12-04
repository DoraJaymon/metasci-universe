# MacroAnalyzer 故障排查指南

## 常见问题：识别了 0 个国家和机构

### 问题表现

```
[MacroAnalyzer] 加载了 100 篇论文
[MacroAnalyzer] 从现有数据中提取了 275 个作者-机构关系
[MacroAnalyzer] 识别了 0 个国家, 0 个机构  ❌
```

虽然提取了作者-机构关系，但识别的国家和机构数量为 0。

---

## 问题根源

### 数据结构不匹配

MacroAnalyzer 需要使用**两个不同来源**的作者信息：

1. **`work.authors`** - 简化的作者列表
   - 来源：OpenAlex API 简化格式
   - 作者ID格式：短格式 `A5026129552`
   - 字段：`id`, `display_name` (可能为空)
   - **缺点**：无机构信息、无国家信息

2. **`work._raw.authorships`** - 完整的作者-机构信息
   - 来源：数据增强 (通过 `enrich_works_with_institutions`)
   - 作者ID格式：长格式 `https://openalex.org/A2112096792`
   - 字段：`author`, `institutions`, `author_position`, `is_corresponding`, ...
   - **优点**：包含完整的机构信息（名称、国家代码、ROR、类型）

### 问题诊断

原始数据中，这两个字段的**作者ID完全不同**：

```python
# work.authors (5个作者，简化格式)
[
    {"id": "A5026129552", "display_name": ""},
    {"id": "A5033632230", "display_name": ""},
    ...
]

# work._raw.authorships (10个作者，完整格式，数据增强后)
[
    {
        "author": {
            "id": "https://openalex.org/A2112096792",
            "display_name": "Vivek Kumar Singh"
        },
        "institutions": [
            {
                "display_name": "Banaras Hindu University",
                "country_code": "IN"  ← 关键字段
            }
        ]
    },
    ...
]
```

**ID 不匹配**：
- `work.authors`: `A5026129552`, `A5033632230`, ...
- `work._raw.authorships`: `A2112096792`, `A2935711095`, ...

### 问题流程

1. `load_data()` 从 `_raw.authorships` 构建 `author_institutions` 字典
   - 键：`https://openalex.org/A2112096792`
   - 值：`{"country": "IN", "institution": "Banaras Hindu University"}`

2. `_build_statistics()` **之前**遍历 `work.authors` 查找机构信息
   - 查找键：`A5026129552` 或 `https://openalex.org/A5026129552`
   - 结果：**找不到**（ID不同）
   - 结果：识别 0 个国家

---

## 解决方案

### 修复内容

修改了 `macro_analyzer.py` 的 `_build_statistics()` 方法（第190-202行）：

**之前**：
```python
# 使用 work.authors 的ID
authors = work.get('authors', [])
for author in authors:
    author_id = author.get('id', '')
    # 查找失败：ID不匹配
```

**现在**：
```python
# 优先使用 _raw.authorships 的ID
authorships = work.get('_raw', {}).get('authorships', [])

if authorships:
    # 使用 _raw.authorships 中的作者ID
    authors_data = [
        {'id': a.get('author', {}).get('id', '')}
        for a in authorships
    ]
else:
    # 回退到 work.authors（兼容旧数据）
    authors_data = work.get('authors', [])
```

### 效果对比

**修复前**：
```
[MacroAnalyzer] 识别了 0 个国家, 0 个机构  ❌
```

**修复后**：
```
[MacroAnalyzer] 识别了 14 个国家, 26 个机构  ✅
```

---

## 数据增强必要性

### 原始数据缺少什么？

原始 OpenAlex 数据（如 `works_query_all_1bf7ea910a2a.json`）：
- ❌ `_raw` 中**没有** `authorships` 字段
- ❌ 没有机构信息
- ❌ 没有国家信息
- ❌ 作者姓名可能为空

### 数据增强做什么？

使用 `enrich_works_with_institutions()` 函数：

1. 提取每篇论文的 DOI
2. 调用 AuthorQuery API 获取完整作者信息
3. 将结果存入 `work._raw.authorships`
4. 包含：作者姓名、机构名称、国家代码、ROR、机构类型

### 数据增强示例

```python
import asyncio
from MacroAnalysisTool.data_enricher import enrich_works_with_institutions

# 增强数据
enriched_works = await enrich_works_with_institutions(
    works[:100],           # 测试100篇
    verbose=True,
    max_workers=20         # 并发数
)

# 使用增强后的数据
analyzer = MacroAnalyzer(verbose=True)
analyzer.load_data(enriched_works, enrich_institutions=False)
```

### 处理时间估计

- 30 篇：约 1-2 分钟
- 100 篇：约 3-5 分钟
- 1384 篇（全部）：约 30-45 分钟

---

## 使用建议

### 1. 检查数据是否需要增强

```python
# 检查第一篇论文
work = works[0]
has_authorships = '_raw' in work and 'authorships' in work['_raw']

if not has_authorships:
    print("⚠️  数据需要增强！")
else:
    authorships = work['_raw']['authorships']
    if len(authorships) > 0:
        inst = authorships[0].get('institutions', [])
        if len(inst) > 0 and inst[0].get('country_code'):
            print("✅ 数据已增强，包含国家信息")
        else:
            print("⚠️  authorships 存在但缺少国家信息")
```

### 2. 保存增强后的数据

避免重复处理，保存增强后的数据：

```python
import json

# 保存
with open('data/enriched_works.json', 'w', encoding='utf-8') as f:
    json.dump(enriched_works, f, ensure_ascii=False, indent=2)

# 下次直接加载
with open('data/enriched_works.json', 'r', encoding='utf-8') as f:
    enriched_works = json.load(f)
```

### 3. 处理 API 查询失败

如果部分论文的 API 查询失败（网络问题、SSL 错误）：

```python
# 减少并发数
enriched_works = await enrich_works_with_institutions(
    works,
    verbose=True,
    max_workers=5  # 降低并发，提高稳定性
)
```

### 4. 完整工作流程

```python
# 1. 加载原始数据
with open('data/works_cache/works_query_all_1bf7ea910a2a.json', 'r') as f:
    data = json.load(f)
works = data if isinstance(data, list) else data.get('works', [])

# 2. 数据增强（首次运行）
enriched_works = await enrich_works_with_institutions(
    works[:100],  # 先测试小批量
    verbose=True,
    max_workers=20
)

# 3. 初始化分析器
analyzer = MacroAnalyzer(verbose=True)
analyzer.load_data(enriched_works, enrich_institutions=False)

# 4. 查看摘要
analyzer.print_summary()

# 5. 生成可视化
analyzer.countries_productivity(view='notebook')
analyzer.institution_productivity(topn=20, view='notebook')
```

---

## 快速诊断脚本

如果遇到问题，运行以下诊断脚本：

```python
# 检查数据结构
work = enriched_works[0]
print(f"有 _raw.authorships? {'_raw' in work and 'authorships' in work['_raw']}")

if '_raw' in work and 'authorships' in work['_raw']:
    authorships = work['_raw']['authorships']
    print(f"作者数量: {len(authorships)}")

    if len(authorships) > 0:
        first_author = authorships[0]
        institutions = first_author.get('institutions', [])

        if len(institutions) > 0:
            country_code = institutions[0].get('country_code', '')
            print(f"第一个作者的国家代码: {repr(country_code)}")

            if not country_code or country_code == '':
                print("❌ country_code 为空！数据增强可能失败")
            else:
                print("✅ 数据正常")
```

---

## 相关文件

- **数据增强工具**：`data_enricher.py`
- **宏观分析器**：`macro_analyzer.py`
- **测试脚本**：`quick_test_enricher.py`
- **使用示例**：`../../pyNoteBook/demo_macro_analyzer.ipynb`

---

## 版本历史

### v1.1 (2024-11-27)
- ✅ 修复：`_build_statistics()` 现在优先使用 `_raw.authorships` 的作者ID
- ✅ 修复：支持短格式和长格式ID的标准化
- ✅ 改进：兼容没有增强的旧数据格式

### v1.0
- ❌ 问题：ID不匹配导致识别0个国家
