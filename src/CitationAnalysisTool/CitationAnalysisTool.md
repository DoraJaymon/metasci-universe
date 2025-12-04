# CitationAnalysisTool - 引文分析工具集

对学术论文数据进行文献计量分析和引文网络分析的综合工具集。

## 目录

1. [简介](#简介)
2. [安装](#安装)
3. [基本文献计量分析](#基本文献计量分析)
4. [RPYS 分析](#rpys-分析)
5. [历史直接引用网络 (HCN)](#历史直接引用网络-hcn)
6. [测试](#测试)
7. [参考文献](#参考文献)

---

## 简介

CitationAnalysisTool 提供三大核心功能模块:

### 1. 基本文献计量分析
- 年度科学产出 (Annual Scientific Production)
- 高产作者 (Most Productive Authors)
- 高被引论文 (Most Cited Papers)
- 最相关来源 (Most Relevant Sources)
- 最常见关键词 (Most Frequent Keywords)

### 2. RPYS (Reference Publication Year Spectroscopy)
通过分析被引文献的出版年份分布,识别研究领域的历史根源和重要文献年份。

### 3. Historical Citation Network (HCN)
分析文献集合内部的直接引用关系,识别领域基石文献(通过 LCS)和知识流动路径。

---

## 安装

### 基础依赖

```bash
cd MetaSciToolUniverse
uv pip install -e .
```

### 可选依赖

```bash
# RPYS PyBibX 交互式可视化
pip install plotly scipy

# 网络分析
pip install networkx matplotlib
```

---

## 基本文献计量分析

### 快速开始

```python
from DataExtractorTool.works_extractor import WorksExtractor
from CitationAnalysisTool import basic_bibliometric_analysis

# 1. 获取论文数据
extractor = WorksExtractor()
result = await extractor.fetch_works(
    keywords="machine learning",
    publication_year=(2020, 2024),
    limit=500
)

# 2. 执行文献计量分析(一行代码搞定!)
analysis = basic_bibliometric_analysis(
    works=result['works'],
    top_authors=20,
    top_papers=20,
    top_sources=20,
    top_keywords=30
)

# 3. 查看结果
print(f"年度产出: {analysis['annual_production']}")
print(f"高产作者: {analysis['most_productive_authors']}")
print(f"高被引论文: {analysis['most_cited_papers']}")
```

### API 文档

#### `basic_bibliometric_analysis()`

**参数:**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `works` | `List[Dict]` | 必填 | 论文数据列表 |
| `top_authors` | `int` | 20 | 返回前N位高产作者 |
| `top_papers` | `int` | 20 | 返回前N篇高被引论文 |
| `top_sources` | `int` | 20 | 返回前N个相关来源 |
| `top_keywords` | `int` | 30 | 返回前N个关键词 |

**输入数据格式:**

```python
{
    "id": "W123456789",
    "title": "论文标题",
    "publication_year": 2023,
    "cited_by_count": 100,
    "authors": [{"id": "A123", "name": "Author Name"}, ...],
    "source": {"id": "S123", "name": "Journal Name", "type": "journal"},
    "topics": [{"id": "T123", "name": "Topic Name", "score": 0.9}, ...]
}
```

**返回值:**

```python
{
    "annual_production": {
        "total_papers": 500,
        "year_range": [2020, 2024],
        "annual_data": [
            {"year": 2024, "n_papers": 120, "total_citations": 3500, "avg_citations": 29.17},
            ...
        ]
    },
    "most_productive_authors": {
        "total_authors": 2500,
        "authors": [
            {"id": "A123", "name": "Author Name", "n_papers": 15, "h_index": 12},
            ...
        ]
    },
    "most_cited_papers": {...},
    "most_relevant_sources": {...},
    "most_frequent_keywords": {...}
}
```

### 使用场景

1. **文献综述** - 快速了解某领域的研究现状
2. **学术评估** - 评估作者/期刊/机构的学术影响力
3. **研究趋势分析** - 识别研究热点和趋势
4. **期刊选择** - 为投稿选择合适的期刊

---

## RPYS 分析

### 核心原理

**RPYS (Reference Publication Year Spectroscopy)** 通过分析被引文献的出版年份分布,识别研究领域的历史根源。

核心假设:在某个研究领域的文献集合中,被频繁引用的特定年份的文献往往代表了该领域的重要历史发展节点或奠基性工作。

**关键指标:**
- **引用频次 (Citations)**: 每个年份被引用的总次数
- **偏离中位数 (Deviation from Median)**: 实际引用次数与周围年份中位数的差值
- **峰值 (Peaks)**: 显著高于周围年份的引用峰值

**中位数计算方法:**
- **Centered Median (居中中位数)**: 使用 (t-2, t-1, t, t+1, t+2) 5年的中位数
- **Backward Median (向后中位数)**: 使用 (t-4, t-3, t-2, t-1, t) 5年的中位数

### 快速开始

```python
from CitationAnalysisTool import rpys_analysis

# 准备数据(需包含 referenced_works_details 字段)
works = [
    {
        "id": "https://openalex.org/W123",
        "title": "Paper Title",
        "publication_year": 2023,
        "referenced_works_details": [
            {
                "id": "https://openalex.org/W456",
                "publication_year": 2000,
                "title": "Reference Title"
            },
            ...
        ]
    },
    ...
]

# 执行 RPYS 分析
result = rpys_analysis(
    works=works,
    timespan=(1950, 2020),      # 分析年份范围
    median_window="centered",    # 中位数窗口类型
    verbose=True
)

# 查看结果
print(result["statistics"])
print(result["rpys_table"])

# 显示图表
import matplotlib.pyplot as plt
result["figure"]
plt.show()
```

### 参数说明

```python
def rpys_analysis(
    works: List[Dict],
    timespan: Optional[Tuple[int, int]] = None,  # 年份范围
    median_window: str = "centered",              # "centered" 或 "backward"
    top_refs_per_year: int = 3,                   # 每年显示的top引用文献数量
    verbose: bool = True
) -> Dict:
```

### 返回结果

```python
{
    "rpys_table": pd.DataFrame,           # RPYS 数据表
    "references_by_year": Dict,           # 每年的top引用文献
    "citation_details": pd.DataFrame,     # 所有引用记录
    "statistics": {
        "total_papers": 100,
        "total_references": 500,
        "peak_years": [1950, 1980, ...],
        "median_window": "centered"
    },
    "figure": matplotlib.figure.Figure    # 可视化图表
}
```

### 可视化风格

RPYS 支持两种可视化风格:

#### 1. 默认风格 (Matplotlib)

```python
from CitationAnalysisTool.rpys import RPYS

rpys = RPYS(verbose=True)
works = await rpys.prepare_data(keywords='scientometrics', limit=100)
result = rpys.analyze(works)

# 默认风格
rpys.plot(result, style='default', save_path='rpys_default.png')
```

**特点:**
- 静态图表,适合学术发表
- 黑色曲线:每年的被引次数
- 红色曲线:与5年中位数的偏差(峰值表示重要年份)

#### 2. PyBibX 风格 (Plotly 交互式)

```python
# PyBibX 风格
rpys.plot(result, style='pybibx', view='browser', save_html='rpys_interactive.html')
```

**特点:**
- 交互式图表,适合探索和演示
- 时间范围选择器(10年/20年/50年/全部)
- 悬停显示详细信息
- 红色柱子高亮峰值年份
- 支持导出为 HTML 文件

**PyBibX 风格参数:**

```python
rpys.plot(
    result,
    style='pybibx',
    view='browser',          # 'browser' 或 'notebook'
    show_peaks=True,         # 是否显示峰值标记
    peaks_only=False,        # 是否只显示峰值年份
    save_html='rpys.html'    # 保存为 HTML 文件
)
```

### 完整示例:使用真实数据

```python
from DataExtractorTool import WorksExtractor
from CitationAnalysisTool import rpys_analysis
from pyalex import Works

# 1. 获取论文数据
extractor = WorksExtractor()
result = await extractor.fetch_works(
    keywords="scientometrics",
    publication_year=(2020, 2023),
    limit=100
)
works = result['works']

# 2. 收集所有被引文献ID
all_ref_ids = []
for work in works:
    all_ref_ids.extend(work.get('referenced_works', []))
unique_ref_ids = list(set(all_ref_ids))

# 3. 批量获取被引文献详情
ref_details_list = []
batch_size = 50

for i in range(0, len(unique_ref_ids), batch_size):
    batch_ids = unique_ref_ids[i:i+batch_size]
    batch_results = Works().filter(openalex_id='|'.join(batch_ids)).get()
    ref_details_list.extend(batch_results)

# 4. 添加详细信息到原始数据
ref_dict = {ref['id']: ref for ref in ref_details_list}

for work in works:
    work['referenced_works_details'] = [
        ref_dict[ref_id]
        for ref_id in work.get('referenced_works', [])
        if ref_id in ref_dict
    ]

# 5. 执行 RPYS 分析
rpys_result = rpys_analysis(
    works=works,
    median_window="centered",
    verbose=True
)

# 6. 保存结果
rpys_result['rpys_table'].to_csv('rpys_table.csv', index=False)
rpys_result['figure'].savefig('rpys_plot.png', dpi=300, bbox_inches='tight')
```

### 使用数据库查询(大批量数据)

```python
import asyncpg
from DataExtractorTool import WorksExtractor
from CitationAnalysisTool import rpys_analysis

# 1. 连接数据库
conn = await asyncpg.connect(**DB_CONFIG)

# 2. 获取论文数据
async def query_fn(sql: str):
    records = await conn.fetch(sql)
    return [dict(r) for r in records]

extractor = WorksExtractor(query_fn=query_fn)
result = await extractor.fetch_works(
    keywords="machine learning",
    publication_year=(2015, 2023),
    limit=5000  # 大批量数据
)
works = result['works']

# 3. 从数据库批量获取被引文献详情
all_ref_ids = []
for work in works:
    all_ref_ids.extend(work.get('referenced_works', []))
unique_ref_ids = list(set(all_ref_ids))

query = """
    SELECT id, publication_year, display_name as title, cited_by_count
    FROM works
    WHERE id = ANY($1::text[])
"""
ref_details = await conn.fetch(query, unique_ref_ids)
ref_details_list = [dict(r) for r in ref_details]

# 4. 添加详细信息并执行分析
ref_dict = {ref['id']: ref for ref in ref_details_list}
for work in works:
    work['referenced_works_details'] = [
        ref_dict[ref_id]
        for ref_id in work.get('referenced_works', [])
        if ref_id in ref_dict
    ]

rpys_result = rpys_analysis(works, verbose=True)
await conn.close()
```

### RPYS 可视化说明

RPYS 图表包含两条曲线:

1. **黑色曲线**: 每年的被引次数(原始数据)
   - 显示历史上每个年份被当前研究领域引用的次数

2. **红色曲线**: 与5年中位数的偏差
   - 峰值表示重要的历史文献年份
   - 正偏差 = 该年份被引次数高于周围年份的中位数
   - 负偏差 = 该年份被引次数低于周围年份的中位数

**峰值的意义**: 红色曲线的峰值表示该年份在研究领域历史上具有特殊重要性,通常对应:
- 奠基性理论的提出
- 重要方法的发明
- 领域范式的转变
- 经典文献的发表

### RPYS 注意事项

1. **数据要求**:
   - 必须包含 `referenced_works_details` 字段
   - 每个被引文献需要有准确的出版年份

2. **数据获取**:
   - 小批量 (<1000 被引文献): 使用 OpenAlex API
   - 大批量 (>1000 被引文献): 建议使用本地数据库

3. **性能考虑**:
   - 获取被引文献详情需要额外的 API 调用或数据库查询
   - 建议先缓存被引文献信息,避免重复查询

4. **年份范围**:
   - 建议设置合理的 timespan,避免分析过多噪音数据
   - 通常分析最近50-70年的被引文献即可

---

## 历史直接引用网络 (HCN)

### 核心概念

**Historical Citation Network** 基于 Eugene Garfield 的理论,分析文献集合内部的直接引用关系。

#### LCS vs GCS

| 指标 | 全称 | 定义 | 意义 |
|------|------|------|------|
| **LCS** | Local Citation Score | 论文在**数据集内部**的被引次数 | 领域影响力 |
| **GCS** | Global Citation Score | 论文在**全局**的被引次数 | 总体影响力 |

**示例:**
```
数据集:100篇关于"scientometrics"的论文

论文A:
- GCS = 500(全球被引500次)
- LCS = 15(在这100篇论文中被引用15次)

论文B:
- GCS = 50(全球被引50次)
- LCS = 30(在这100篇论文中被引用30次) ← 在这个领域更重要
```

**意义:**
- **LCS 高** = 在该研究领域内影响力大(领域基石)
- **GCS 高但LCS低** = 知名但可能不是该领域核心
- **LCS和GCS都高** = 该领域的经典文献

### 快速开始

```python
from src.CitationAnalysisTool import HistoricalCitationNetwork

# 准备数据
works = [
    {
        'id': 'W123',
        'title': 'Paper A',
        'publication_year': 2020,
        'cited_by_count': 100,  # GCS
        'referenced_works': ['W456', 'W789']
    },
    {
        'id': 'W456',
        'title': 'Paper B',
        'publication_year': 2019,
        'cited_by_count': 50,
        'referenced_works': []
    },
    ...
]

# 创建分析器
hcn = HistoricalCitationNetwork(works)

# 提取内部引用
citations_df = hcn.extract_internal_citations()

# 计算 LCS
lcs_df = hcn.calculate_lcs()

# 识别关键文献(按LCS排序)
key_papers = hcn.identify_key_papers(top_n=10)

# 完整分析
results = hcn.analyze()
print(results['summary'])

# 可视化
hcn.plot_network(top_n=20, layout='temporal')
```

### 一键分析

```python
from src.CitationAnalysisTool import analyze_historical_citations

results = analyze_historical_citations(
    works,
    top_n=20,
    plot=True,
    verbose=True
)
```

### 主要功能

#### 1. 提取内部引用

```python
citations_df = hcn.extract_internal_citations()
# 返回 DataFrame: citing_id | cited_id | citing_year | cited_year
```

#### 2. 计算 LCS

```python
lcs_df = hcn.calculate_lcs()
# 返回 DataFrame: work_id | lcs | gcs | title | year
```

#### 3. 识别关键文献

```python
# 按 LCS 排序(领域影响力)
key_papers_lcs = hcn.identify_key_papers(top_n=10, criterion='lcs')

# 按 GCS 排序(总体影响力)
key_papers_gcs = hcn.identify_key_papers(top_n=10, criterion='gcs')

# 按 LCS/GCS 比率排序(领域特异性)
key_papers_ratio = hcn.identify_key_papers(top_n=10, criterion='lcs/gcs')
```

#### 4. 构建引用网络

```python
# 构建邻接矩阵
matrix, work_ids = hcn.build_network_matrix()

# 获取NetworkX图对象
G = hcn.get_citation_graph(top_n=30, min_lcs=1)

# 网络分析
print(f"节点数: {G.number_of_nodes()}")
print(f"边数: {G.number_of_edges()}")
print(f"密度: {nx.density(G):.4f}")
```

#### 5. 可视化

```python
# 时间轴布局(X轴=年份)
hcn.plot_network(
    top_n=20,
    layout='temporal',
    figsize=(16, 10),
    save_path='network_temporal.png'
)

# 弹簧布局(力导向)
hcn.plot_network(top_n=20, layout='spring')

# 环形布局
hcn.plot_network(top_n=20, layout='circular')
```

**可视化特点:**
- 节点大小 = LCS(局部影响力)
- 节点颜色 = 发表年份
- 箭头方向 = 引用方向(A → B 表示A引用B)
- 标签 = 标题缩写 + 年份 + LCS

#### 6. 完整分析

```python
results = hcn.analyze()

# 结果包含:
{
    'summary': {
        'total_papers': 100,
        'papers_with_lcs': 16,
        'total_internal_citations': 25,
        'avg_lcs': 0.25,
        'max_lcs': 3
    },
    'key_papers': [...],
    'network_stats': {
        'nodes': 16,
        'edges': 10,
        'density': 0.0417
    },
    'temporal_evolution': [
        {
            'year': 2020,
            'n_papers': 80,
            'avg_lcs': 0.3,
            'avg_citation_age': 2.5
        },
        ...
    ]
}
```

### 应用场景

#### 1. 识别领域基石文献

```python
key_papers = hcn.identify_key_papers(top_n=20, criterion='lcs')

print("该领域的基石文献:")
for _, paper in key_papers.iterrows():
    print(f"LCS={paper['lcs']}, GCS={paper['gcs']}")
    print(f"  {paper['title']} ({paper['year']})")
```

#### 2. 发现知识流动路径

```python
import networkx as nx

G = hcn.get_citation_graph(min_lcs=1)

if nx.is_directed_acyclic_graph(G):
    longest_path = nx.dag_longest_path(G)
    print("最长的知识传承链:")
    for i, node_idx in enumerate(longest_path):
        attrs = G.nodes[node_idx]
        print(f"{i+1}. {attrs['title'][:50]}... ({attrs['year']})")
```

#### 3. 领域核心 vs 外围分析

```python
lcs_df = hcn.calculate_lcs()
lcs_df['lcs_gcs_ratio'] = lcs_df['lcs'] / (lcs_df['gcs'] + 1)

# 领域特异性文献(高LCS/GCS比率)
field_specific = lcs_df.nlargest(10, 'lcs_gcs_ratio')

# 全局知名但领域外围(高GCS但低LCS)
global_famous = lcs_df[(lcs_df['gcs'] > 100) & (lcs_df['lcs'] < 2)]
```

### 数据要求

每篇论文必须包含以下字段:

```python
{
    'id': str,                      # 必需:唯一标识符
    'title': str,                   # 必需:标题
    'publication_year': int,        # 必需:发表年份
    'cited_by_count': int,          # 可选:全局被引次数(GCS)
    'referenced_works': List[str],  # 可选:引用文献ID列表
}
```

---

## 测试

### 运行测试

```bash
# 进入项目目录
cd MetaSciToolUniverse

# 基本文献计量分析测试
python src/CitationAnalysisTool/testpy/test_bibliometric.py

# RPYS 测试
python src/CitationAnalysisTool/testpy/test_rpys.py

# HCN 测试
python src/CitationAnalysisTool/testpy/test_historical_citation_network.py
```

### Jupyter Notebook 示例

查看以下 Notebook 获取完整的交互式演示:

- `pyNoteBook/01_data_acquisition_and_biblioanalysis.ipynb` - RPYS 演示
- `pyNoteBook/02_bibliometric_analysis_demo.ipynb` - 基本文献计量分析演示

### 测试数据

测试数据和结果保存在 `src/CitationAnalysisTool/data/` 目录:

```
src/CitationAnalysisTool/data/
├── bibliometric_test_results/    # 基本文献计量分析结果
├── rpys_cache/                    # RPYS 缓存数据
├── hcn_citations.csv              # HCN 引用关系
├── hcn_lcs.csv                    # HCN LCS 数据
└── hcn_network_temporal.png       # HCN 网络图
```

---

## 参考文献

### RPYS 相关

1. **Marx, W., Bornmann, L., Barth, A., & Leydesdorff, L. (2014).**
   Detecting the historical roots of research fields by reference publication year spectroscopy (RPYS).
   *Journal of the Association for Information Science and Technology*, 65(4), 751-764.

2. **Thor, A., Bornmann, L., Marx, W., & Mutz, R. (2018).**
   Identifying single influential publications in a research field: new analysis opportunities of the CRExplorer.
   *Scientometrics*, 116(1), 591-608.

### 文献计量学方法

3. **Aria, M., & Cuccurullo, C. (2017).**
   bibliometrix: An R-tool for comprehensive science mapping analysis.
   *Journal of Informetrics*, 11(4), 959-975.

### HCN 相关

4. **Garfield, E. (2004).**
   Historiographic mapping of knowledge domains literature.
   *Journal of Information Science*, 30(2), 119-145.

### 相关资源

- bibliometrix R package: https://github.com/massimoaria/bibliometrix
- PyBibX: https://github.com/nils-herrmann/pybibx

---

## 版本历史

### v0.3.0 (2025-11-22)
- ✨ 新增 Historical Citation Network (HCN) 分析
- ✅ 实现 LCS 计算和网络可视化
- ✅ 实现时间演化分析

### v0.2.0 (2025-11-24)
- ✨ 集成 RPYS PyBibX 风格可视化
- ✅ 支持交互式 Plotly 图表
- ✅ 添加时间范围选择器和滑块

### v0.1.0 (2025-11-17)
- ✨ 初始版本
- ✅ 实现5个基本文献计量指标
- ✅ 实现 RPYS 核心算法

---

## 许可

MIT License

---

**MetaSciToolUniverse** - 科学计量学工具集
