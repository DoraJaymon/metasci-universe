# TopicTool - 主题建模工具

基于 BERTopic 的学术论文主题建模工具。

## 特性

- ✅ **使用 BERTopic** 进行先进的主题建模
- ✅ **显示实际主题关键词**（而非 "topic_1" 这样的标签）
- ✅ **简洁清晰的可视化**（类似 `get_top_ngrams()` 风格）
- ✅ **支持 OpenAlex 数据格式**
- ✅ **多种可视化方式**：分布图、时间变化图、热力图
- ✅ **模型保存和加载**
- ✅ **导出主题信息**到 CSV

## 安装依赖

```bash
pip install bertopic sentence-transformers umap-learn plotly
```

## 快速开始

### 1. 基本使用

```python
from src.TopicTool.topic_modeling import TopicModeling

# 创建实例
tm = TopicModeling(verbose=True)

# 加载数据
data = tm.load_data('data/works_cache/works_query_all_1bf7ea910a2a.json')

# 训练模型
tm.fit(
    nr_topics=10,  # 指定10个主题
    min_topic_size=10,
    embedding_model='allenai/scibert_scivocab_uncased'
)

# 查看主题摘要
summary = tm.get_summary()
print(f"识别出 {summary['n_topics']} 个主题")
```

### 2. 可视化

#### 主题分布图（类似 get_top_ngrams 风格）

```python
# 显示 Top 15 主题的文档分布
tm.plot_topics_distribution(
    top_n=15,
    view='browser',  # 在浏览器中打开
    save_path='output/topics_distribution.html'
)
```

**特点**：
- 水平柱状图
- 显示实际关键词（如 "machine learning, algorithm, model"）
- **不使用 "topic_1" 这样的标签**
- Hover 显示详细关键词和分数

#### 主题随时间变化图

```python
tm.plot_topics_over_time(
    view='browser',
    save_path='output/topics_over_time.html'
)
```

#### 主题相似度热力图

```python
tm.plot_topics_heatmap(
    view='browser',
    save_path='output/topics_heatmap.html',
    top_n=20
)
```

### 3. 查看主题详情

```python
# 获取主题标签（使用关键词）
topic_label = tm.get_topic_label(topic_id=0, max_words=5)
print(f"主题标签: {topic_label}")

# 获取主题关键词
keywords = tm.get_topic_words(topic_id=0, n_words=10)
for word, score in keywords:
    print(f"{word}: {score:.4f}")

# 获取代表性文档
rep_docs = tm.get_representative_docs(topic_id=0)
```

### 4. 减少主题数量

```python
# 将主题合并到 5 个
tm.reduce_topics(nr_topics=5)
```

### 5. 保存和加载模型

```python
# 保存模型
tm.save_model('models/my_topic_model')

# 加载模型
tm2 = TopicModeling()
tm2.load_model('models/my_topic_model')
```

### 6. 导出主题信息

```python
# 导出到 CSV
tm.export_topics('output/topics_export.csv')
```

导出的 CSV 包含：
- Topic_ID: 主题 ID
- Topic_Label: 主题标签（关键词）
- Count: 文档数量
- Keywords: 详细关键词列表

## 与 pybibx 的区别

| 特性 | pybibx | TopicTool (本工具) |
|------|--------|-------------------|
| 主题标签 | "Topic 0", "Topic 1" | "machine learning, algorithm, model" |
| 可视化风格 | 默认样式 | 类似 get_top_ngrams 的简洁风格 |
| 柱状图方向 | 垂直 | 水平（更易读） |
| 数据格式 | 需要特定格式 | 直接支持 OpenAlex 格式 |
| 摘要导出 | ❌ | ✅ |

## 示例：完整工作流程

```python
from src.TopicTool.topic_modeling import TopicModeling

# 1. 初始化
tm = TopicModeling(verbose=True)

# 2. 加载数据
tm.load_data('data/works_cache/works_query_all_1bf7ea910a2a.json')

# 3. 训练模型
tm.fit(nr_topics=10, min_topic_size=10)

# 4. 查看摘要
summary = tm.get_summary()
for topic in summary['topics'][:5]:
    print(f"{topic['label']} ({topic['count']} 篇)")

# 5. 可视化
tm.plot_topics_distribution(top_n=10, view='browser')
tm.plot_topics_over_time(view='browser')
tm.plot_topics_heatmap(top_n=10, view='browser')

# 6. 导出结果
tm.export_topics('output/topics.csv')
tm.save_model('models/topic_model')
```

## 运行测试

```bash
python src/TopicTool/testpy/test_topic_modeling.py
```

测试将：
1. 加载 Scientometrics 期刊数据（2021-2024）
2. 训练主题模型（10个主题）
3. 生成多种可视化
4. 导出主题信息
5. 保存模型

输出文件位于：`src/TopicTool/test_output/`

## API 参考

### TopicModeling 类

#### 方法

- `load_data(data_path)`: 加载 OpenAlex 格式数据
- `fit(...)`: 训练主题模型
- `get_topic_label(topic_id, max_words)`: 获取主题标签（关键词）
- `reduce_topics(nr_topics)`: 减少主题数量
- `plot_topics_distribution(...)`: 绘制主题分布图
- `plot_topics_over_time(...)`: 绘制主题随时间变化图
- `plot_topics_heatmap(...)`: 绘制主题相似度热力图
- `get_topic_words(topic_id, n_words)`: 获取主题关键词
- `get_representative_docs(topic_id)`: 获取代表性文档
- `get_summary()`: 获取主题建模摘要
- `export_topics(output_path)`: 导出主题信息到 CSV
- `save_model(save_path)`: 保存模型
- `load_model(load_path)`: 加载模型

## 参数说明

### fit() 参数

- `texts`: 文本列表（可选，默认使用 load_data 加载的数据）
- `nr_topics`: 主题数量（None 表示自动确定）
- `min_topic_size`: 最小主题大小（默认 10）
- `embedding_model`: 嵌入模型名称（默认 'allenai/scibert_scivocab_uncased'）
- `language`: 语言（默认 'english'）
- `calculate_probabilities`: 是否计算概率（默认 True）

### plot_topics_distribution() 参数

- `top_n`: 显示前 N 个主题（默认 15）
- `view`: 'browser' 或 'notebook'（默认 'notebook'）
- `save_path`: 保存路径（可选）

## 技术栈

- **BERTopic**: 主题建模核心
- **Sentence-Transformers**: 文本嵌入
- **UMAP**: 降维
- **Plotly**: 交互式可视化
- **pandas**: 数据处理

## 注意事项

1. **首次运行会下载模型**：
   - `allenai/scibert_scivocab_uncased` (~420MB)
   - 可能需要几分钟

2. **计算资源**：
   - 大数据集（>5000篇）可能需要较长时间
   - 建议使用 GPU（如果可用）

3. **数据格式**：
   - 需要包含 `title` 和 `abstract_inverted_index` 字段
   - OpenAlex 格式开箱即用

## 故障排查

### 问题：模型下载失败

```python
# 解决方案：手动指定本地模型
tm.fit(embedding_model='/path/to/local/model')
```

### 问题：内存不足

```python
# 解决方案：减少数据量或增加 min_topic_size
tm.fit(min_topic_size=50)  # 增加最小主题大小
```

### 问题：主题过多/过少

```python
# 解决方案：指定主题数量
tm.fit(nr_topics=10)  # 明确指定10个主题

# 或者训练后减少
tm.reduce_topics(nr_topics=5)
```

## 未来改进

- [ ] 支持中文文本
- [ ] 添加更多预训练模型选项
- [ ] 支持增量更新
- [ ] 添加主题演化分析
- [ ] 支持自定义停用词表

## 参考文献

- BERTopic: [https://github.com/MaartenGr/BERTopic](https://github.com/MaartenGr/BERTopic)
- SciBERT: [https://github.com/allenai/scibert](https://github.com/allenai/scibert)
