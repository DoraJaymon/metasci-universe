# MacroAnalyzer 错误修复总结

本文档记录了 MacroAnalyzer 开发过程中遇到的关键问题和修复方案。

---

## Bug 1: 识别了 0 个国家和机构

### 问题表现

```
[MacroAnalyzer] 从现有数据中提取了 275 个作者-机构关系
[MacroAnalyzer] 识别了 0 个国家, 0 个机构  ❌
```

虽然提取了作者-机构关系，但最终统计时识别不到任何国家和机构。

### 根本原因

**作者ID不匹配**：`work.authors` 和 `work._raw.authorships` 使用了不同的作者ID。

#### 数据结构差异

```python
# work.authors (原始简化数据，5个作者)
[
    {"id": "A5026129552", "display_name": ""},
    {"id": "A5033632230", "display_name": ""},
    ...
]

# work._raw.authorships (数据增强后，10个作者)
[
    {
        "author": {
            "id": "https://openalex.org/A2112096792",
            "display_name": "Vivek Kumar Singh"
        },
        "institutions": [
            {"display_name": "Banaras Hindu University", "country_code": "IN"}
        ]
    },
    ...
]
```

**关键发现**：
- 作者ID **完全不同**（不是格式差异，是不同的人）
- 作者数量不同（5 vs 10）
- `work.authors` 只是简化的作者列表，不完整

#### 错误流程

1. `load_data()` 从 `_raw.authorships` 构建 `author_institutions` 字典
   - 键：`https://openalex.org/A2112096792`
   - 值：`{"country": "IN", "institution": "..."}`

2. `_build_statistics()` **遍历 `work.authors`** 查找机构信息
   - 查找键：`A5026129552` 或 `https://openalex.org/A5026129552`
   - 结果：**找不到**（ID不是同一个人）
   - 最终：识别 0 个国家

### 修复方案

修改 `_build_statistics()` 方法，**优先使用 `_raw.authorships` 中的作者ID**。

#### 修复代码（第190-202行）

```python
# 优先使用 _raw.authorships（如果存在），否则回退到 authors
authorships = work.get('_raw', {}).get('authorships', [])

if authorships:
    # 使用 _raw.authorships 中的作者ID（与机构信息来源一致）
    authors_data = [
        {'id': a.get('author', {}).get('id', '')}
        for a in authorships
    ]
else:
    # 回退到 work.authors（兼容没有增强的旧数据）
    authors_data = work.get('authors', [])

# 后续查找逻辑使用 authors_data
for author in authors_data:
    author_id = author.get('id', '')
    # ... 查找机构信息
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

### 关键教训

1. ⚠️ **同一份数据中的不同字段可能来自不同来源**
2. ⚠️ **确保数据源的一致性**：构建字典和查询字典必须使用相同的ID
3. ⚠️ **数据增强后，优先使用增强后的完整数据**

---

## Bug 2: 国家地图没有颜色

### 问题表现

生成的国家地图显示正常，但所有国家都是灰色，没有根据论文数量显示颜色。

### 根本原因

**国家代码格式不匹配**：数据使用 ISO-2 代码，但 Plotly 要求 ISO-3 代码。

#### 格式差异

```python
# 我们的数据（来自 OpenAlex API）
country_code: "US", "CN", "GB", "IN", "BR"  # ISO-2 (2字母)

# Plotly choropleth 要求
locationmode='ISO-3': "USA", "CHN", "GBR", "IND", "BRA"  # ISO-3 (3字母)
```

#### Plotly 支持的 locationmode

```python
locationmode 可选值：
  - 'ISO-3': 3字母国家代码（USA, CHN, GBR）
  - 'country names': 完整国家名称
  - 'USA-states': 美国各州
  - 'geojson-id': GeoJSON ID

❌ 不支持 'ISO-2'
```

#### 错误流程

1. 数据包含 ISO-2 代码：`["US", "CN", "GB", ...]`
2. Choropleth 配置：`locationmode='ISO-3'`
3. Plotly 尝试匹配：`"US"` → 找不到（期望 `"USA"`）
4. 结果：所有国家无法匹配 → 显示为灰色

### 修复方案

#### 方案 1: 安装 pycountry 库

```bash
uv pip install pycountry
```

#### 方案 2: 添加转换函数

在 `countries_productivity()` 方法中添加（第313-323行）：

```python
# 转换国家代码：ISO-2 (US, CN) → ISO-3 (USA, CHN)
def convert_to_iso3(iso2_code):
    """将 ISO-2 国家代码转换为 ISO-3"""
    try:
        country = pycountry.countries.get(alpha_2=iso2_code)
        return country.alpha_3 if country else iso2_code
    except:
        return iso2_code  # 如果转换失败，保持原样

df['country_iso3'] = df['country'].apply(convert_to_iso3)
df['country_name'] = df['country']  # 保留原始代码用于显示
```

#### 方案 3: 修改 Choropleth 配置

```python
# 之前（错误）
fig.add_trace(go.Choropleth(
    locations=year_df['country'],      # ISO-2 代码
    locationmode='ISO-3',              # 期望 ISO-3 ❌ 不匹配
    ...
))

# 之后（正确）
fig.add_trace(go.Choropleth(
    locations=year_df['country_iso3'],  # 转换后的 ISO-3 代码
    locationmode='ISO-3',               # ✅ 匹配
    text=year_df['country_name'],       # 显示原始代码
    ...
))
```

### 转换示例

| ISO-2 (输入) | ISO-3 (输出) | 国家名称 |
|--------------|--------------|----------|
| US           | USA          | United States |
| CN           | CHN          | China |
| GB           | GBR          | United Kingdom |
| IN           | IND          | India |
| BR           | BRA          | Brazil |
| DE           | DEU          | Germany |
| JP           | JPN          | Japan |

### 效果对比

**修复前**：
- 地图显示正常
- 所有国家都是灰色
- 无法看出数据差异

**修复后**：
- 地图显示正常
- 不同国家根据论文数量显示不同颜色
- 鼠标悬停显示详细信息

### 关键教训

1. ⚠️ **API 返回的数据格式与可视化库要求可能不一致**
2. ⚠️ **检查文档**：Plotly choropleth 不支持 ISO-2
3. ⚠️ **数据预处理**：在可视化前转换数据格式
4. ✅ **使用标准库**：`pycountry` 提供可靠的国家代码转换

---

## Bug 3: Jupyter Notebook 不加载修改后的代码

### 问题表现

修改了 `.py` 文件后，在 Notebook 中重新运行代码，但问题依然存在。

### 根本原因

**Jupyter Kernel 缓存了模块**：Python 导入模块后会缓存在 `sys.modules` 中，即使源文件修改，Kernel 仍使用内存中的旧版本。

#### Python 模块导入机制

```python
# 第一次导入
import macro_analyzer  # 从磁盘加载，缓存到 sys.modules

# 修改 macro_analyzer.py 文件...

# 再次导入（在同一个 Python 进程中）
import macro_analyzer  # ❌ 从 sys.modules 返回缓存版本，不重新加载！
```

### 修复方案

#### 方案 1: 重启 Jupyter Kernel（最彻底）

在 Notebook 菜单中：
- **Kernel → Restart Kernel**
- 或 **Kernel → Restart & Run All**

#### 方案 2: 强制重新加载模块（推荐）

在导入代码前添加：

```python
import sys

# 删除缓存的模块
if 'MacroAnalysisTool.macro_analyzer' in sys.modules:
    del sys.modules['MacroAnalysisTool.macro_analyzer']
if 'MacroAnalysisTool.data_enricher' in sys.modules:
    del sys.modules['MacroAnalysisTool.data_enricher']

# 重新导入（会从磁盘重新加载）
from MacroAnalysisTool.macro_analyzer import MacroAnalyzer
from MacroAnalysisTool.data_enricher import enrich_works_with_institutions
```

#### 方案 3: 使用 importlib.reload()

```python
import importlib
import MacroAnalysisTool.macro_analyzer

# 重新加载模块
importlib.reload(MacroAnalysisTool.macro_analyzer)
```

### Notebook Cell 修改

修改了 `demo_macro_analyzer.ipynb` 的 Cell 2（导入库）：

```python
import json
import sys
from pathlib import Path

# 添加项目路径
project_root = Path.cwd().parent
sys.path.insert(0, str(project_root / 'src'))

# 强制重新加载模块（确保使用最新修复的代码）
if 'MacroAnalysisTool.macro_analyzer' in sys.modules:
    del sys.modules['MacroAnalysisTool.macro_analyzer']
if 'MacroAnalysisTool.data_enricher' in sys.modules:
    del sys.modules['MacroAnalysisTool.data_enricher']

from MacroAnalysisTool.macro_analyzer import MacroAnalyzer
from MacroAnalysisTool.data_enricher import enrich_works_with_institutions

print("✅ 导入成功（已重新加载模块）")
```

### 关键教训

1. ⚠️ **修改 .py 文件后，必须重新加载模块**
2. ⚠️ **Jupyter Notebook 的 Kernel 是长期运行的 Python 进程**
3. ✅ **开发时在导入前清理 sys.modules**
4. ✅ **或者养成修改代码后重启 Kernel 的习惯**

---

## 通用调试技巧

### 1. 数据结构检查

当遇到"识别不到"或"找不到"的问题时：

```python
# 检查数据是否存在
work = works[0]
print(f"有 _raw.authorships? {'_raw' in work and 'authorships' in work['_raw']}")

# 检查数据内容
if '_raw' in work and 'authorships' in work['_raw']:
    authorships = work['_raw']['authorships']
    print(f"作者数量: {len(authorships)}")
    if len(authorships) > 0:
        first_author = authorships[0]
        print(json.dumps(first_author, indent=2, ensure_ascii=False))
```

### 2. ID 匹配验证

当涉及字典查找时：

```python
# 检查键是否存在
author_id = "A5026129552"
print(f"在字典中? {author_id in author_institutions}")

# 检查字典内容
for i, (key, value) in enumerate(list(author_institutions.items())[:3]):
    print(f"{i+1}. 键: {key}")
    print(f"   值: {value}")
```

### 3. 数据格式验证

当可视化出问题时：

```python
# 检查数据格式
print(f"数据类型: {type(data)}")
print(f"数据长度: {len(data)}")
print(f"数据示例: {data[:3]}")

# 检查编码格式
for item in data[:5]:
    print(f"{item}: 长度={len(item)}, 类型={type(item)}")
```

### 4. 逐步缩小范围

从简单到复杂：

```python
# 1. 先测试 1 篇论文
test_works = works[:1]

# 2. 测试成功后增加到 10 篇
test_works = works[:10]

# 3. 最后处理全部数据
test_works = works[:1384]
```

### 5. 使用 verbose 模式

开启详细输出了解执行过程：

```python
analyzer = MacroAnalyzer(verbose=True)
analyzer.load_data(enriched_works, enrich_institutions=False)

# 会输出：
# [MacroAnalyzer] 加载了 100 篇论文
# [MacroAnalyzer] 从现有数据中提取了 284 个作者-机构关系
# [MacroAnalyzer] 识别了 14 个国家, 26 个机构
```

---

## 预防措施

### 1. 数据源一致性

```python
# ✅ 好的做法：数据源一致
authorships = work['_raw']['authorships']
author_institutions = {a['author']['id']: {...} for a in authorships}
# 后续使用 authorships 中的 ID 查找

# ❌ 坏的做法：数据源不一致
author_institutions = {a['author']['id']: {...} for a in work['_raw']['authorships']}
# 但查找时使用 work['authors'] 中的 ID
```

### 2. 格式转换集中处理

```python
# ✅ 好的做法：在数据处理阶段统一转换
df['country_iso3'] = df['country'].apply(convert_to_iso3)
# 后续所有地方都使用转换后的格式

# ❌ 坏的做法：在多处分散转换
# 容易遗漏某些地方，导致不一致
```

### 3. 添加数据验证

```python
def load_data(self, works, enrich_institutions=False):
    """加载数据"""
    # 验证数据格式
    if not isinstance(works, list):
        raise ValueError("works 必须是列表")

    if len(works) == 0:
        raise ValueError("works 列表为空")

    # 检查必要字段
    first_work = works[0]
    if '_raw' not in first_work or 'authorships' not in first_work['_raw']:
        print("⚠️  数据缺少 _raw.authorships，需要先进行数据增强")

    # ... 继续处理
```

### 4. 单元测试

```python
def test_country_code_conversion():
    """测试国家代码转换"""
    assert convert_to_iso3("US") == "USA"
    assert convert_to_iso3("CN") == "CHN"
    assert convert_to_iso3("GB") == "GBR"
    print("✅ 国家代码转换测试通过")

def test_author_id_matching():
    """测试作者ID匹配"""
    work = enriched_works[0]
    authorships = work['_raw']['authorships']
    first_author_id = authorships[0]['author']['id']

    assert first_author_id in author_institutions
    print("✅ 作者ID匹配测试通过")
```

---

## 相关文档

- **故障排查指南**: `TROUBLESHOOTING.md` - 常见问题和诊断方法
- **使用示例**: `../../pyNoteBook/demo_macro_analyzer.ipynb` - 完整工作流程
- **测试脚本**: `quick_test_enricher.py` - 端到端测试

---

## 总结

### 三大核心问题

1. **数据源不一致** → 确保构建和查询使用相同的ID
2. **格式不匹配** → 检查API数据与库要求的格式差异
3. **模块缓存** → Jupyter Notebook 修改代码后要重新加载

### 调试黄金法则

1. **从小数据开始**：先测试 1-10 篇论文
2. **逐步验证**：检查每个环节的输入输出
3. **打印关键信息**：使用 verbose 模式和 print 调试
4. **对比期望与实际**：数据格式、字段名、ID 格式等
5. **查阅文档**：了解库的要求和限制

### 开发建议

- ✅ 使用类型提示和文档字符串
- ✅ 添加数据验证和友好的错误提示
- ✅ 提供 verbose 模式用于调试
- ✅ 编写测试脚本验证关键功能
- ✅ 记录常见问题和解决方案（本文档）
