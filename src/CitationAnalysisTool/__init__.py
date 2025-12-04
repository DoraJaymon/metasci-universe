"""
CitationAnalysisTool - 文献计量分析工具包

提供基本的文献计量分析功能，包括：
- 年度科学产出分析
- 高产作者分析
- 高被引论文分析
- 最相关来源/期刊分析
- 最常见关键词/主题分析
- RPYS (Reference Publication Year Spectroscopy) 引用出版年份谱分析
- Historical Citation Network (历史直接引用网络) 分析
"""

from .bibliometric_analyzer import basic_bibliometric_analysis
from .rpys import RPYS, rpys_analysis
from .historical_citation_network import (
    HistoricalCitationNetwork,
    analyze_historical_citations
)

__all__ = [
    'basic_bibliometric_analysis',
    'RPYS',
    'rpys_analysis',
    'HistoricalCitationNetwork',
    'analyze_historical_citations'
]
__version__ = '0.3.0'
