"""
AuthorTool - 作者分析工具包 (统一接口)

提供作者相关的分析功能，包括：
- 作者传记信息检索（API + 数据库）
- 作者文献计量指标分析
- 作者机构隶属关系分析
- 按名字搜索作者

数据源：
- API: 适用于小批量、最新数据
- Database: 适用于大批量、历史数据、批量查询
- 智能路由：自动选择最优数据源

使用示例：
    from src.AuthorTool import AuthorQuery
    import asyncio

    async def main():
        aq = AuthorQuery(verbose=True)

        # 查询单篇论文第一作者（标准信息）
        result = await aq.query("10.1016/j.joi.2017.08.007")

        # 查询所有共同作者（基本信息，速度快）
        authors = await aq.query(
            "10.1016/j.joi.2017.08.007",
            all_authors=True,
            detail_level='basic'
        )

        # 查询所有共同作者（完整信息）
        authors = await aq.query(
            "10.1016/j.joi.2017.08.007",
            all_authors=True,
            detail_level='full'
        )

        # 按名字搜索
        results = await aq.search_by_name("Massimo Aria", limit=10)

    asyncio.run(main())
"""

# 新版统一查询类
from .author_query import AuthorQuery, query_authors

__all__ = [
    'AuthorQuery',     # 统一查询类（推荐）
    'query_authors',   # 便捷函数
]

__version__ = '0.4.0'
