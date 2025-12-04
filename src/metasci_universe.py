"""
MetaSci Universe - Meta Science Tool Universe

用于 AI Agent 的元科学研究和科学计量分析工具包。
A meta science tool universe for conducting meta-scientific research and scientometric analysis.

这是一个便捷的包装器模块，提供统一的导入接口。
"""

__version__ = "0.1.0"

# 核心工具 - 始终可用（基本安装）
from DataExtractorTool import WorksExtractor
from SearchTool import FindWork
from AuthorTool import AuthorQuery, query_authors
from CitationAnalysisTool import (
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
    from MacroAnalysisTool import MacroAnalyzer
    __all__.append("MacroAnalyzer")
except ImportError:
    MacroAnalyzer = None

try:
    from TopicTool import TopicModeling, TopicAnalyzer
    __all__.extend(["TopicModeling", "TopicAnalyzer"])
except ImportError:
    TopicModeling = None
    TopicAnalyzer = None
