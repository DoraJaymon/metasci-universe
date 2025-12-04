"""
GetCitations - 智能引用查询工具

混合查询策略（精细化控制）：
- 第1层 → 使用 PyAlex API（获取最新数据）
- 第2层 → 如果第1层数量≤300，继续使用API；否则使用PostgreSQL
- 第3层及以上 → 使用 PostgreSQL（快速、无限制）

# GetCitationsTool 使用说明

## 功能

获取论文的引用关系，支持：
1. **引文分析** - 统计引用关系、引用趋势
2. **文献追踪** - 前向/后向文献雪球采样
3. **知识流动** - 追踪概念传播、知识继承脉络

## 智能切换策略

- ✅ **第1层** → PyAlex API
- ✅ **第2层** → 第1层数量≤300时继续用API，否则用PostgreSQL
- ✅ **第3层及以上** → PostgreSQL

**依赖**: 必须安装 pyalex 包
"""

import asyncio
from typing import List, Dict, Callable
from pyalex import Works

class GetCitations:
    """获取论文引用关系的智能工具（混合API+数据库）"""

    def __init__(self, query_fn: Callable, per_paper_limit: int = 40, use_api: bool = True):
        """
        初始化

        Args:
            query_fn: 异步查询函数，接受SQL字符串，返回结果列表
            per_paper_limit: 每篇论文最多取多少个引用（防止引用爆炸，推荐40）
            use_api: 是否启用API（第一层查询优先使用API）
        """
        self.query_fn = query_fn
        self.per_paper_limit = per_paper_limit
        self.use_api = use_api

    async def _get_citations_via_api(
        self,
        work_id: str,
        direction: str = "forward",
        limit: int = 200
    ) -> List[Dict]:
        """
        通过PyAlex API获取引用

        Args:
            work_id: 论文ID (短格式)
            direction: 'forward' (被谁引用) 或 'backward' (引用了谁)
            limit: 最大结果数

        Returns:
            引用ID列表 [{'id': 'W123', 'level': 1}, ...]
        """
        def fetch_citations():
            work_url = f"https://openalex.org/{work_id}"

            if direction == "forward":
                # 获取引用该论文的文献
                works = Works().filter(cites=work_url).get(per_page=limit)
                results = []
                for w in works[:limit]:
                    wid = w.get('id', '').replace('https://openalex.org/', '')
                    if wid:
                        results.append({'id': wid, 'level': 1})
                return results
            else:
                # 获取该论文引用的文献
                work = Works()[work_url]
                ref_ids = [ref.replace('https://openalex.org/', '')
                          for ref in work.get('referenced_works', [])]
                return [{'id': rid, 'level': 1} for rid in ref_ids[:limit]]

        return await asyncio.to_thread(fetch_citations)

    async def _get_layer2_via_api(
        self,
        layer1_ids: List[str],
        direction: str = "forward"
    ) -> List[Dict]:
        """
        通过API获取第二层引用（基于第一层的ID列表）

        Args:
            layer1_ids: 第一层的论文ID列表
            direction: 'forward' 或 'backward'

        Returns:
            第二层引用列表 [{'id': 'W123', 'level': 2}, ...]
        """
        def fetch_layer2():
            all_layer2 = []
            seen = set(layer1_ids)  # 去重

            for work_id in layer1_ids:
                work_url = f"https://openalex.org/{work_id}"

                if direction == "forward":
                    # 获取引用该论文的文献
                    works = Works().filter(cites=work_url).get(per_page=100)
                    for w in works[:100]:
                        wid = w.get('id', '').replace('https://openalex.org/', '')
                        if wid and wid not in seen:
                            all_layer2.append({'id': wid, 'level': 2})
                            seen.add(wid)
                else:
                    # 获取该论文引用的文献
                    work = Works()[work_url]
                    ref_ids = [ref.replace('https://openalex.org/', '')
                              for ref in work.get('referenced_works', [])]
                    for rid in ref_ids:
                        if rid not in seen:
                            all_layer2.append({'id': rid, 'level': 2})
                            seen.add(rid)

            return all_layer2

        return await asyncio.to_thread(fetch_layer2)

    async def get_forward_citations(
        self,
        work_id: str,
        depth: int = 1,
        max_results: int = 1000
    ) -> Dict:
        """
        获取前向引用（谁引用了这篇论文）

        智能策略：
        - 第1层 → 使用PyAlex API
        - 第2层 → 如果第1层数量≤300，继续用API；否则用数据库
        - 第3层及以上 → 使用本地数据库

        Args:
            work_id: 论文ID (短格式，如 'W4367833763')
            depth: 查询深度 (1-5)
            max_results: 最大结果数

        Returns:
            {"citations": [...], "total": int, "by_level": {1: int, 2: int, ...}}
        """
        # 清理ID格式（如果用户传入URL）
        work_id = self._clean_id(work_id)

        # 策略1: 第1层使用API
        if depth == 1 and self.use_api:
            api_results = await self._get_citations_via_api(work_id, "forward", max_results)
            if api_results:
                by_level = {1: len(api_results)}
                return {
                    "citations": api_results,
                    "total": len(api_results),
                    "by_level": by_level,
                    "direction": "forward",
                    "source": "api"
                }

        # 策略2: 第2层智能判断
        if depth == 2 and self.use_api:
            # 先获取第1层
            layer1_results = await self._get_citations_via_api(work_id, "forward", 200)
            if layer1_results:
                layer1_count = len(layer1_results)

                # 如果第1层数量<=300，继续用API获取第2层
                if layer1_count <= 300:
                    layer1_ids = [item['id'] for item in layer1_results]
                    layer2_results = await self._get_layer2_via_api(layer1_ids, "forward")

                    all_results = layer1_results + layer2_results
                    by_level = {
                        1: len(layer1_results),
                        2: len(layer2_results)
                    }

                    return {
                        "citations": all_results,
                        "total": len(all_results),
                        "by_level": by_level,
                        "direction": "forward",
                        "source": "api"
                    }
                # 否则，切换到数据库（继续往下执行）

        # 策略3: 使用本地数据库（depth==1且API失败，或depth==2估算量过大，或depth>=3）
        if depth == 1:
            # 单层查询（限制结果数）
            sql = f"""
            SELECT work_id as id, 1 as level
            FROM works_referenced_works
            WHERE referenced_work_id = '{work_id}'
            LIMIT {min(max_results, self.per_paper_limit)}
            """
        else:
            # 多层递归查询
            # 策略：限制第1层数量，防止高引论文导致第2层爆炸
            sql = f"""
            WITH RECURSIVE first_layer AS (
                -- 第1层：限制为per_paper_limit个，优先选择被引多的
                SELECT wrw.work_id as id
                FROM works_referenced_works wrw
                LEFT JOIN works w ON wrw.work_id = w.id
                WHERE wrw.referenced_work_id = '{work_id}'
                ORDER BY COALESCE(w.cited_by_count, 0) DESC
                LIMIT {self.per_paper_limit}
            ),
            citation_tree AS (
                -- 第1层结果
                SELECT id, 1 as level FROM first_layer

                UNION

                -- 第2+层：递归查询
                SELECT DISTINCT wrw.work_id as id, ct.level + 1 as level
                FROM works_referenced_works wrw
                JOIN citation_tree ct ON wrw.referenced_work_id = ct.id
                WHERE ct.level < {depth}
            )
            SELECT DISTINCT id, level
            FROM citation_tree
            ORDER BY level, id
            LIMIT {max_results}
            """

        results = await self.query_fn(sql)

        # 统计各层数量
        by_level = {}
        for r in results:
            level = r['level']
            by_level[level] = by_level.get(level, 0) + 1

        return {
            "citations": results,
            "total": len(results),
            "by_level": by_level,
            "direction": "forward",
            "source": "database"
        }

    async def get_backward_citations(
        self,
        work_id: str,
        depth: int = 1,
        max_results: int = 1000
    ) -> Dict:
        """
        获取后向引用（这篇论文引用了谁）

        智能策略：
        - 第1层 → 使用PyAlex API
        - 第2层 → 如果第1层数量≤300，继续用API；否则用数据库
        - 第3层及以上 → 使用本地数据库

        Args:
            work_id: 论文ID (短格式)
            depth: 查询深度 (1-5)
            max_results: 最大结果数
        """
        work_id = self._clean_id(work_id)

        # 策略1: 第1层使用API
        if depth == 1 and self.use_api:
            api_results = await self._get_citations_via_api(work_id, "backward", max_results)
            if api_results:
                by_level = {1: len(api_results)}
                return {
                    "citations": api_results,
                    "total": len(api_results),
                    "by_level": by_level,
                    "direction": "backward",
                    "source": "api"
                }

        # 策略2: 第2层智能判断
        if depth == 2 and self.use_api:
            # 先获取第1层
            layer1_results = await self._get_citations_via_api(work_id, "backward", 200)
            if layer1_results:
                layer1_count = len(layer1_results)

                # 如果第1层数量<=300，继续用API获取第2层
                if layer1_count <= 300:
                    layer1_ids = [item['id'] for item in layer1_results]
                    layer2_results = await self._get_layer2_via_api(layer1_ids, "backward")

                    all_results = layer1_results + layer2_results
                    by_level = {
                        1: len(layer1_results),
                        2: len(layer2_results)
                    }

                    return {
                        "citations": all_results,
                        "total": len(all_results),
                        "by_level": by_level,
                        "direction": "backward",
                        "source": "api"
                    }
                # 否则，切换到数据库（继续往下执行）

        # 策略3: 使用本地数据库（depth==1且API失败，或depth==2估算量过大，或depth>=3）
        if depth == 1:
            # 单层查询（限制结果数）
            sql = f"""
            SELECT referenced_work_id as id, 1 as level
            FROM works_referenced_works
            WHERE work_id = '{work_id}'
            LIMIT {min(max_results, self.per_paper_limit)}
            """
        else:
            # 多层递归查询
            # 策略：限制第1层数量，优先选择被引多的参考文献
            sql = f"""
            WITH RECURSIVE first_layer AS (
                -- 第1层：限制为per_paper_limit个，优先选择重要的参考文献
                SELECT wrw.referenced_work_id as id
                FROM works_referenced_works wrw
                LEFT JOIN works w ON wrw.referenced_work_id = w.id
                WHERE wrw.work_id = '{work_id}'
                ORDER BY COALESCE(w.cited_by_count, 0) DESC
                LIMIT {self.per_paper_limit}
            ),
            reference_tree AS (
                -- 第1层结果
                SELECT id, 1 as level FROM first_layer

                UNION

                -- 第2+层：递归查询
                SELECT DISTINCT wrw.referenced_work_id as id, rt.level + 1 as level
                FROM works_referenced_works wrw
                JOIN reference_tree rt ON wrw.work_id = rt.id
                WHERE rt.level < {depth}
            )
            SELECT DISTINCT id, level
            FROM reference_tree
            ORDER BY level, id
            LIMIT {max_results}
            """

        results = await self.query_fn(sql)

        by_level = {}
        for r in results:
            level = r['level']
            by_level[level] = by_level.get(level, 0) + 1

        return {
            "citations": results,
            "total": len(results),
            "by_level": by_level,
            "direction": "backward",
            "source": "database"
        }

    async def get_both_citations(
        self,
        work_id: str,
        depth: int = 1,
        max_results: int = 1000
    ) -> Dict:
        """获取双向引用"""
        forward = await self.get_forward_citations(work_id, depth, max_results // 2)
        backward = await self.get_backward_citations(work_id, depth, max_results // 2)

        return {
            "forward": forward,
            "backward": backward,
            "total": forward["total"] + backward["total"]
        }

    async def enrich_with_metadata(self, citation_ids: List[str]) -> List[Dict]:
        """
        批量获取论文元数据

        Args:
            citation_ids: 论文ID列表

        Returns:
            包含标题、年份、被引次数等信息的论文列表
        """
        if not citation_ids:
            return []

        # 批量查询，每次最多100个
        all_papers = []
        for i in range(0, len(citation_ids), 100):
            batch = citation_ids[i:i+100]
            ids_str = "','".join(batch)

            sql = f"""
            SELECT id, title, publication_year, cited_by_count, doi, type
            FROM works
            WHERE id IN ('{ids_str}')
            """

            papers = await self.query_fn(sql)
            all_papers.extend(papers)

        return all_papers

    def _clean_id(self, work_id: str) -> str:
        """清理ID格式，将URL转为短ID"""
        if work_id.startswith('https://openalex.org/'):
            return work_id.split('/')[-1]
        return work_id








# ==================== 测试代码 ====================
if __name__ == "__main__":
    import sys
    sys.path.insert(0, '/home/dell/Desktop/openalex-agent')

    async def test_get_citations():
        """
        测试GetCitations工具（混合API+数据库）

        测试用例：检索论文"Beyond Citations: Measuring Novel Scientific Ideas
        and their Impact in Publication Text"的两层前后向引用
        """
        # 导入依赖
        try:
            from db_config import DB_CONFIG
            import asyncpg
            from pyalex import Works
        except ImportError as e:
            print(f"导入错误: {e}")
            print("请确保已安装: uv pip install asyncpg pyalex")
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
        output.append("=" * 80)
        output.append("GetCitations 工具测试 - 混合API+数据库策略")
        output.append("=" * 80)

        # 步骤1: 查找目标论文
        print("步骤1: 查找目标论文...")
        test_title = "Beyond Citations: Measuring Novel Scientific Ideas and their Impact in Publication Text"
        output.append(f"\n目标论文: {test_title}")

        # 使用API查找
        try:
            works = Works().search(test_title).get()
            test_work = works[0] if works else None
            if test_work:
                test_work_id = test_work['id'].replace('https://openalex.org/', '')
                pub_year = test_work.get('publication_year')
                output.append(f"论文ID: {test_work_id}")
                output.append(f"发表年份: {pub_year}")
                output.append(f"被引次数: {test_work.get('cited_by_count')}")

                # 如果是2024年之后的论文，使用备用测试ID（确保有数据）
                if pub_year and pub_year >= 2024:
                    print(f"论文发表于{pub_year}年，本地数据库可能无数据，使用备用测试论文")
                    test_work_id = "W4367833763"  # pySciSci (2023年，有充足数据)
                    output.append(f"\n注意: 原论文过新，切换到备用测试论文ID: {test_work_id}")
                    # 获取备用论文信息
                    backup_work = Works()['https://openalex.org/' + test_work_id]
                    output.append(f"备用论文: {backup_work.get('title')}")
                    output.append(f"发表年份: {backup_work.get('publication_year')}")
                    output.append(f"被引次数: {backup_work.get('cited_by_count')}")
            else:
                print("未找到目标论文，使用备用测试ID")
                test_work_id = "W4367833763"  # 备用测试ID
                output.append(f"使用备用论文ID: {test_work_id}")
        except Exception as e:
            print(f"API查询失败: {e}，使用备用测试ID")
            test_work_id = "W4367833763"
            output.append(f"使用备用论文ID: {test_work_id}")

        # 创建工具实例（启用API混合模式）
        get_citations = GetCitations(
            query_fn=query_fn,
            per_paper_limit=40,
            use_api=True  # 启用API混合策略
        )

        # 测试2: 前向引用（两层）
        print("\n步骤2: 获取前向引用（深度2）...")
        output.append("\n" + "=" * 80)
        output.append("[测试] 前向引用（谁引用了这篇论文）- 深度2")
        output.append("=" * 80)

        forward_2 = await get_citations.get_forward_citations(test_work_id, depth=2, max_results=1000)
        output.append(f"数据源: {forward_2.get('source', 'unknown')}")
        output.append(f"总计: {forward_2['total']} 篇")
        output.append(f"分层统计: {forward_2['by_level']}")

        # 获取各层的元数据并显示标题
        for level in sorted(forward_2['by_level'].keys()):
            level_citations = [c for c in forward_2['citations'] if c['level'] == level]
            citation_ids = [c['id'] for c in level_citations[:10]]  # 每层最多显示10篇

            if citation_ids:
                papers = await get_citations.enrich_with_metadata(citation_ids)
                output.append(f"\n第{level}层论文（共{len(level_citations)}篇，显示前{len(papers)}篇）:")
                for i, paper in enumerate(papers, 1):
                    title = paper.get('title') or 'N/A'
                    if len(title) > 70:
                        title = title[:70] + "..."
                    output.append(f"  {i}. {title}")
                    output.append(f"     年份: {paper.get('publication_year')} | 被引: {paper.get('cited_by_count')}次")

        # 测试3: 后向引用（两层）
        print("\n步骤3: 获取后向引用（深度2）...")
        output.append("\n" + "=" * 80)
        output.append("[测试] 后向引用（这篇论文引用了谁）- 深度2")
        output.append("=" * 80)

        backward_2 = await get_citations.get_backward_citations(test_work_id, depth=2, max_results=1000)
        output.append(f"数据源: {backward_2.get('source', 'unknown')}")
        output.append(f"总计: {backward_2['total']} 篇")
        output.append(f"分层统计: {backward_2['by_level']}")

        # 获取各层的元数据并显示标题
        for level in sorted(backward_2['by_level'].keys()):
            level_citations = [c for c in backward_2['citations'] if c['level'] == level]
            citation_ids = [c['id'] for c in level_citations[:10]]  # 每层最多显示10篇

            if citation_ids:
                papers = await get_citations.enrich_with_metadata(citation_ids)
                output.append(f"\n第{level}层论文（共{len(level_citations)}篇，显示前{len(papers)}篇）:")
                for i, paper in enumerate(papers, 1):
                    title = paper.get('title') or 'N/A'
                    if len(title) > 70:
                        title = title[:70] + "..."
                    output.append(f"  {i}. {title}")
                    output.append(f"     年份: {paper.get('publication_year')} | 被引: {paper.get('cited_by_count')}次")

        # 总结
        output.append("\n" + "=" * 80)
        output.append("测试总结")
        output.append("=" * 80)
        output.append("混合查询策略:")
        output.append("  • 第一层查询 → PyAlex API（快速，获取最新数据）")
        output.append("  • 深度>=2 或 数量>100 → 本地PostgreSQL（快速、无限制）")
        output.append(f"\n前向引用总计: {forward_2['total']} 篇（{forward_2['by_level']}）")
        output.append(f"后向引用总计: {backward_2['total']} 篇（{backward_2['by_level']}）")

        # 保存结果
        import os
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, "output_get_citations_两层前后向引用.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(output))

        print(f"\n✅ 测试完成，结果已保存到 {output_file}")

        await conn.close()

    # 运行测试
    asyncio.run(test_get_citations())
