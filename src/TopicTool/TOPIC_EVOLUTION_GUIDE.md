# TopicAnalyzer - 主题演化可视化

## 快速开始

```python
from TopicTool import TopicAnalyzer
import json

# 加载数据
with open('data/works_cache/works_query_all_1bf7ea910a2a.json') as f:
    works = json.load(f)

# 创建分析器
analyzer = TopicAnalyzer()
analyzer.load_data(works)

# 主题演化堆叠面积图（借鉴 PyBibX 的 plot_evolution_year_complement）
analyzer.plot_evolution_complement(topn=10)

# 主题分布柱状图（借鉴 PyBibX 的 get_top_ngrams 风格）
analyzer.plot_top_topics(topn=20)
```

## 主要特点

### 1. plot_evolution_complement - 主题演化堆叠面积图

借鉴 PyBibX 的 `plot_evolution_year_complement` 方法：

**特点**:
- ✅ 堆叠面积图（streamgraph）
- ✅ 显示实际主题名称（不是 topic_1, topic_2）
- ✅ 交互式 Plotly 图表
- ✅ 支持自定义主题列表
- ✅ 可保存为 HTML

**使用**:
```python
# Top 10 主题
analyzer.plot_evolution_complement(topn=10)

# 自定义主题
custom_topics = [
    'Bibliometric Analysis and Research Evaluation',
    'Natural Language Processing'
]
analyzer.plot_evolution_complement(custom_topics=custom_topics)

# 保存为 HTML
analyzer.plot_evolution_complement(topn=10, save_html='evolution.html')
```

### 2. plot_top_topics - 主题分布柱状图

借鉴 PyBibX 的 `get_top_ngrams` 风格：

**特点**:
- ✅ 水平柱状图
- ✅ 颜色渐变显示频率
- ✅ 清晰的主题名称

**使用**:
```python
# Top 20 主题
analyzer.plot_top_topics(topn=20)

# 保存为 HTML
analyzer.plot_top_topics(topn=20, save_html='distribution.html')
```

## 改进点（相比 PyBibX）

1. **更清晰的主题名称**: 始终显示实际主题名称，不会出现 topic_1, topic_2
2. **更好的数据适配**: 直接使用 OpenAlex topics，无需格式转换
3. **更灵活的自定义**: 支持自定义主题列表和标题

## 完整示例

```python
import json
from TopicTool import TopicAnalyzer

# 加载数据
with open('data/works_cache/works_query_all_1bf7ea910a2a.json') as f:
    works = json.load(f)

# 创建并加载数据
analyzer = TopicAnalyzer(verbose=True)
analyzer.load_data(works)

# 打印摘要
analyzer.print_summary()

# 可视化
analyzer.plot_evolution_complement(topn=10)
analyzer.plot_top_topics(topn=20)

# 获取数据
df = analyzer.get_topic_evolution_data(topn=10)
df.to_csv('topic_data.csv')
```

## 测试

```bash
cd MetaSciToolUniverse/src/TopicTool/testpy
python test_topic_evolution.py
```
