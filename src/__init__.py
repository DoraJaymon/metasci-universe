"""
MetaSci Universe - Meta Science Tool Universe

用于 AI Agent 的元科学研究和科学计量分析工具包。
A meta science tool universe for conducting meta-scientific research and scientometric analysis.

主要工具模块：
- DataExtractorTool: 论文数据提取工具 (OpenAlex API + PostgreSQL)
- SearchTool: 论文查找和搜索工具
- AuthorTool: 作者信息分析工具
- CitationAnalysisTool: 引文分析和文献计量工具
- MacroAnalysisTool: 国家和机构生产力宏观分析工具 (需要: pip install metasci-universe[all])
- TopicTool: 基于BERTopic的主题建模工具 (需要: pip install metasci-universe[all])
- NetworkAnalysisTool: 引文网络分析工具
- EmbeddingTool: 论文嵌入和相似度分析工具
"""

__version__ = "0.1.0"

# 核心工具 - 始终可用（基本安装）
from .DataExtractorTool import WorksExtractor
from .SearchTool import FindWork
from .AuthorTool import AuthorQuery, query_authors
from .CitationAnalysisTool import (
    basic_bibliometric_analysis,
    RPYS,
    rpys_analysis,
    HistoricalCitationNetwork,
    analyze_historical_citations
)

__all__ = [
    # 版本
    "__version__",

    # 数据提取
    "WorksExtractor",

    # 搜索工具
    "FindWork",

    # 作者工具
    "AuthorQuery",
    "query_authors",

    # 引文分析
    "basic_bibliometric_analysis",
    "RPYS",
    "rpys_analysis",
    "HistoricalCitationNetwork",
    "analyze_historical_citations",
]

# 可选工具 - 需要 pip install metasci-universe[all]
try:
    from .MacroAnalysisTool import MacroAnalyzer
    __all__.append("MacroAnalyzer")
except ImportError:
    MacroAnalyzer = None

try:
    from .TopicTool import TopicModeling, TopicAnalyzer
    __all__.extend(["TopicModeling", "TopicAnalyzer"])
except ImportError:
    TopicModeling = None
    TopicAnalyzer = None
