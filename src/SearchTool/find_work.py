"""
FindWork - 论文查找工具

通过标题、DOI或ID查找论文

混合策略：
- 标题搜索：优先使用API（快），本地数据库作为fallback
- ID/DOI查询：使用本地数据库（快）
"""

import asyncio
from typing import List, Dict, Callable, Optional


class FindWork:
    """查找论文工具"""

    def __init__(self, query_fn: Callable, use_api: bool = True):
        """
        初始化

        Args:
            query_fn: 异步查询函数，接受SQL字符串，返回结果列表
            use_api: 是否使用API进行标题搜索（推荐开启）
        """
        self.query_fn = query_fn
        self.use_api = use_api

    async def find_by_title(self, title: str, limit: int = 5) -> List[Dict]:
        """
        通过标题查找论文

        策略：
        - 如果use_api=True：使用pyalex API搜索（快速）
        - 如果use_api=False：使用本地数据库（需要GIN索引，否则很慢）

        Args:
            title: 论文标题（支持模糊匹配）
            limit: 最大返回数量

        Returns:
            论文列表，按被引次数降序排列
        """
        if self.use_api:
            # 使用API搜索（快速，不需要索引）
            return await self._find_by_title_api(title, limit)
        else:
            # 使用本地数据库（需要GIN索引，否则很慢）
            return await self._find_by_title_db(title, limit)

    async def _find_by_title_api(self, title: str, limit: int = 5) -> List[Dict]:
        """使用pyalex API搜索论文标题"""
        try:
            from pyalex import Works
            import asyncio

            # pyalex是同步的，在线程中运行
            def search_works():
                works = Works().search(title).get()
                results = []
                for work in works[:limit]:
                    # 转换为统一格式
                    results.append({
                        'id': work.get('id', '').replace('https://openalex.org/', ''),
                        'title': work.get('title', ''),
                        'publication_year': work.get('publication_year'),
                        'cited_by_count': work.get('cited_by_count', 0),
                        'doi': work.get('doi', '').replace('https://doi.org/', '') if work.get('doi') else None,
                    })
                return results

            return await asyncio.to_thread(search_works)

        except ImportError:
            print("警告: pyalex未安装，回退到数据库查询")
            print("安装: uv pip install pyalex")
            return await self._find_by_title_db(title, limit)
        except Exception as e:
            print(f"API查询失败: {e}，回退到数据库查询")
            return await self._find_by_title_db(title, limit)

    async def _find_by_title_db(self, title: str, limit: int = 5) -> List[Dict]:
        """使用本地数据库搜索论文标题（需要GIN索引）"""
        sql = f"""
        SELECT id, title, publication_year, cited_by_count, doi
        FROM works
        WHERE title ILIKE '%{title}%'
        ORDER BY cited_by_count DESC
        LIMIT {limit}
        """
        return await self.query_fn(sql)

    async def find_by_doi(self, doi: str) -> Optional[Dict]:
        """
        通过DOI查找论文

        Args:
            doi: DOI标识符

        Returns:
            论文详情，如果未找到返回None
        """
        sql = f"""
        SELECT id, title, publication_year, cited_by_count, doi
        FROM works
        WHERE doi = '{doi}'
        LIMIT 1
        """
        results = await self.query_fn(sql)
        return results[0] if results else None

    async def get_by_id(self, work_id: str) -> Optional[Dict]:
        """
        通过ID获取论文详情

        Args:
            work_id: 论文ID (短格式如 'W4367833763' 或完整URL)

        Returns:
            论文详情，如果未找到返回None
        """
        # 清理ID格式
        if work_id.startswith('https://'):
            work_id = work_id.split('/')[-1]

        sql = f"""
        SELECT id, title, publication_year, cited_by_count, doi, type
        FROM works
        WHERE id = '{work_id}'
        LIMIT 1
        """
        results = await self.query_fn(sql)
        return results[0] if results else None


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/home/dell/Desktop/openalex-agent')

    async def test_find_work():
        """测试FindWork工具"""
        # 导入数据库配置和asyncpg
        try:
            from db_config import DB_CONFIG
            import asyncpg
        except ImportError as e:
            print(f"导入错误: {e}")
            print("请确保已安装asyncpg: uv pip install asyncpg")
            print("请确保已配置db_config.py")
            return

        # 连接数据库
        try:
            conn = await asyncpg.connect(**DB_CONFIG)
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return

        # 查询函数
        async def query_fn(sql: str):
            records = await conn.fetch(sql)
            return [dict(record) for record in records]

        output = []
        output.append("=" * 60)
        output.append("FindWork 工具测试（混合模式：API + 数据库）")
        output.append("=" * 60)

        # 测试1: 使用API搜索（推荐，快速）
        print("测试1: 使用API搜索标题 'pySciSci'")
        output.append("\n[测试1] find_by_title('pySciSci') - 使用API")

        find_work_api = FindWork(query_fn=query_fn, use_api=True)
        results = await find_work_api.find_by_title("pySciSci", limit=5)
        output.append(f"找到 {len(results)} 篇论文:")

        for i, paper in enumerate(results, 1):
            info = (f"{i}. {paper['title']}\n"
                   f"   ID: {paper['id']}\n"
                   f"   年份: {paper.get('publication_year')}\n"
                   f"   被引: {paper.get('cited_by_count')}次")
            output.append(info)

        # 测试2: 通过ID获取（使用数据库，快速）
        if results:
            work_id = results[0]['id']
            print(f"测试2: 通过ID获取论文 ({work_id})")
            output.append(f"\n[测试2] get_by_id('{work_id}') - 使用数据库")

            paper = await find_work_api.get_by_id(work_id)
            if paper:
                output.append(f"标题: {paper['title']}")
                output.append(f"类型: {paper.get('type')}")

        # 测试3: 通过DOI查找（使用数据库，快速）
        if results and results[0].get('doi'):
            doi = results[0]['doi']
            print(f"测试3: 通过DOI查找 ({doi})")
            output.append(f"\n[测试3] find_by_doi('{doi}') - 使用数据库")

            paper = await find_work_api.find_by_doi(doi)
            if paper:
                output.append(f"找到: {paper['title']}")

        # 说明
        output.append("\n" + "=" * 60)
        output.append("混合策略说明:")
        output.append("=" * 60)
        output.append("• 标题搜索 → API（快速，无需索引）")
        output.append("• ID/DOI查询 → 数据库（快速，有索引）")
        output.append("• 引用关系 → 数据库（快速，API有限制）")

        # 保存结果
        import os
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "output_find_work_测试.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(output))

        print(f"✅ 测试完成，结果已保存到 {output_file}")

        await conn.close()

    # 运行测试
    asyncio.run(test_find_work())
