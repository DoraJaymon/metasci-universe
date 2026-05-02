# MetaSci Universe

**Meta Science Tool Universe** - 用于 AI Agent 的元科学研究和科学计量分析工具包。

A meta science tool universe for conducting meta-scientific research and scientometric analysis, designed for AI agent integration.

## 主要特性

- 📊 **数据提取**: 通过 OpenAlex API 和 PostgreSQL 获取论文数据
- 🔍 **论文搜索**: 强大的论文查找和过滤功能
- 👥 **作者分析**: 作者信息检索和文献计量指标分析
- 📚 **引文分析**: RPYS、历史引文网络等高级分析功能
- 🏷️ **主题建模**: 基于 BERTopic 的主题分析和可视化
- 🌐 **网络分析**: 引文网络构建和分析
- 🤖 **AI Agent 友好**: 设计为可被 AI Agent 调用的工具

## 安装

### 方式1: 开发模式安装（推荐用于开发）

```bash
# 克隆仓库
git clone <repository-url>
cd MetaSciToolUniverse

# 使用 uv 安装（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .

# 安装开发依赖
uv pip install -e ".[dev]"
```

### 方式2: 从本地路径安装（推荐用于其他项目调用）

在你的 **openalex_agent** 或其他项目中：

```bash
# 使用 uv（推荐）
uv pip install -e /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse

# 或使用 pip
pip install -e /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse
```

### 方式3: 从 Git 仓库安装

```bash
# 直接从 Git 安装（发布到 Git 后）
pip install git+https://github.com/DoraJaymon/metasci-universe.git

# 或指定分支
pip install git+https://github.com/DoraJaymon/metasci-universe.git@main
```

## 快速开始

### 1. 基本使用

```python
# 导入工具类
from metasci_universe import WorksExtractor, FindWork, AuthorQuery

# 数据提取
extractor = WorksExtractor(email="your.email@example.com")
works = await extractor.query(
    source_name="Nature",
    from_publication_date="2023-01-01",
    limit=100
)

# 论文搜索
finder = FindWork()
result = await finder.find("10.1038/s41586-023-12345-6")

# 作者查询
author_query = AuthorQuery()
author = await author_query.query("10.1038/s41586-023-12345-6")
```

### 2. 引文分析

```python
from metasci_universe import basic_bibliometric_analysis, RPYS

# 基础文献计量分析
analysis = await basic_bibliometric_analysis(works_data)

# RPYS 分析
rpys = RPYS()
results = await rpys.analyze(works_data)
```

### 3. 主题分析

```python
from metasci_universe import TopicModeling

# 主题建模
topic_model = TopicModeling()
topics = topic_model.fit_transform(documents)
```

## 在 OpenAlex Agent 中使用

### 迁移前（硬编码路径）

```python
import sys
sys.path.insert(0, '/home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse/src')

from DataExtractorTool.works_extractor import WorksExtractor
```

### 迁移后（优雅导入）

```python
# 在 openalex_agent 项目中首先安装包
# uv pip install -e /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse

# 然后直接导入
from metasci_universe import WorksExtractor
```

## 数据源配置

### API 模式（小批量数据）

```python
from metasci_universe import WorksExtractor

extractor = WorksExtractor(
    email="your.email@example.com",
    auto_switch=False  # 仅使用 API
)
```

### 数据库模式（大批量数据）

```python
from metasci_universe import WorksExtractor

# 配置数据库连接（在 config/db_config.py 中）
extractor = WorksExtractor(
    query_fn=db_query_function,
    auto_switch=True  # 自动切换 API/数据库
)
```

- **API**: 适用于小批量（< 1000条）或最新数据（2025年4月后）
- **数据库**: 适用于大批量（> 1000条）或历史数据

## 项目结构

```
MetaSciToolUniverse/
├── pyproject.toml           # 包配置文件
├── MANIFEST.in              # 包含非Python文件配置
├── README.md                # 本文档
├── CLAUDE.md                # Claude Code 开发指南
├── config/                  # 配置文件（数据库等）
├── src/                     # 源代码
│   ├── __init__.py         # 包入口，导出主要工具
│   ├── DataExtractorTool/  # 数据提取工具
│   ├── SearchTool/         # 论文搜索工具
│   ├── AuthorTool/         # 作者分析工具
│   ├── CitationAnalysisTool/  # 引文分析工具
│   ├── TopicTool/          # 主题建模工具
│   ├── NetworkAnalysisTool/   # 网络分析工具
│   └── EmbeddingTool/      # 嵌入分析工具
├── docs/                    # 项目文档
├── pyNoteBook/             # Jupyter notebooks（探索和测试）
├── data/                    # 数据缓存
└── outputs/                # 分析结果输出
```

## 开发工作流

遵循 3-Stage 迭代开发 SOP：

1. **探索阶段**（pyNoteBook）：在 Jupyter 中快速试验
2. **模块化阶段**：将成熟功能迁移到 `src/`
3. **工具化阶段**：封装为 Agent 可调用的工具

详见 [CLAUDE.md](./CLAUDE.md) 和 [docs/toolkit_coreSOP.md](./docs/toolkit_coreSOP.md)

## 包管理

```bash
# 使用 uv 添加依赖
uv pip install <package>

# 更新依赖
uv pip install --upgrade <package>

# 查看已安装的包
uv pip list
```

## 文档

- [CLAUDE.md](./CLAUDE.md) - Claude Code 开发指南
- [pyNoteBook/INSTALL.md](./pyNoteBook/INSTALL.md) - 详细安装指南
- [docs/toolkit_background.md](./docs/toolkit_background.md) - 项目背景和痛点
- [docs/toolkit_coreSOP.md](./docs/toolkit_coreSOP.md) - 工具开发 SOP

## 许可证

MIT
