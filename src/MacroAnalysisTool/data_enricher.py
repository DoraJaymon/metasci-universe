"""
数据增强工具 - 为 MacroAnalyzer 准备包含机构信息的数据

使用 AuthorTool 为 works 数据添加作者的机构信息，使其可以用于宏观分析。
"""

import asyncio
from typing import List, Dict, Optional
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from src.AuthorTool import AuthorQuery


async def enrich_works_with_institutions(
    works: List[Dict],
    verbose: bool = True,
    max_workers: int = 50  # 并发数
) -> List[Dict]:
    """
    为 works 数据增强机构信息

    使用 AuthorQuery 批量获取作者的机构信息，并添加到 _raw.authorships 字段中。

    Args:
        works: OpenAlex 论文数据列表
        verbose: 是否打印详细信息
        max_workers: 最大并发数

    Returns:
        增强后的 works 数据列表（添加了 _raw.authorships 字段）

    Example:
        >>> import asyncio
        >>> import json
        >>>
        >>> # 加载数据
        >>> with open('data/works_cache/works_query_all_1bf7ea910a2a.json', 'r') as f:
        >>>     data = json.load(f)
        >>>
        >>> # 增强数据
        >>> enriched_works = asyncio.run(enrich_works_with_institutions(data['works'][:100]))
        >>>
        >>> # 使用增强后的数据
        >>> from MacroAnalysisTool import MacroAnalyzer
        >>> analyzer = MacroAnalyzer()
        >>> analyzer.load_data(enriched_works, enrich_institutions=False)
    """
    if verbose:
        print(f"\n{'='*60}")
        print("数据增强工具 - 添加机构信息")
        print(f"{'='*60}")
        print(f"待处理论文数: {len(works)}")

    # 初始化 AuthorQuery
    aq = AuthorQuery(verbose=verbose)

    # 收集所有 DOI
    dois = []
    doi_to_work = {}

    for work in works:
        doi = work.get('doi')
        if doi:
            # 移除 https://doi.org/ 前缀
            clean_doi = doi.replace('https://doi.org/', '')
            dois.append(clean_doi)
            doi_to_work[clean_doi] = work

    if verbose:
        print(f"有效 DOI 数量: {len(dois)}")

    # 分批处理（避免一次性查询太多）
    batch_size = max_workers
    total_batches = (len(dois) + batch_size - 1) // batch_size

    if verbose:
        print(f"分 {total_batches} 批处理，每批 {batch_size} 个")

    enriched_count = 0

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(dois))
        batch_dois = dois[start_idx:end_idx]

        if verbose:
            print(f"\n[批次 {batch_idx + 1}/{total_batches}] 处理 DOI {start_idx + 1}-{end_idx}...")

        # 为每个 DOI 创建查询任务（获取所有作者的基本信息）
        tasks = []
        for doi in batch_dois:
            task = aq.query(
                doi,
                all_authors=True,  # 获取所有作者
                detail_level='basic'  # 只获取基本信息（速度快）
            )
            tasks.append(task)

        # 并发执行
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理结果
        for doi, result in zip(batch_dois, results):
            # 跳过错误
            if isinstance(result, Exception):
                if verbose:
                    print(f"  ⚠️  {doi} 查询失败: {result}")
                continue

            # 确保结果是列表
            if not isinstance(result, list):
                result = [result]

            # 获取对应的 work
            work = doi_to_work.get(doi)
            if not work:
                continue

            # 确保有 _raw 字段
            if '_raw' not in work:
                work['_raw'] = {}

            # 构建 authorships 数据
            authorships = []
            for author_data in result:
                # 使用 openalex_id 而不是 id（basic 模式返回的字段）
                author_id = author_data.get('openalex_id') or author_data.get('id') or ''

                authorship = {
                    'author': {
                        'id': author_id,  # 使用正确的字段
                        'display_name': author_data.get('display_name', ''),
                        'orcid': author_data.get('orcid', '')
                    },
                    'author_position': author_data.get('author_position_type', ''),
                    'is_corresponding': author_data.get('is_corresponding', False),
                    'raw_affiliation_string': author_data.get('raw_affiliation_string', ''),
                    'institutions': []
                }

                # 添加机构信息
                affiliation = author_data.get('primary_affiliation')
                if affiliation:
                    # 尝试从不同字段获取国家代码
                    country = (
                        author_data.get('primary_affiliation_country') or
                        author_data.get('country_code') or
                        ''
                    )

                    institution = {
                        'id': author_data.get('primary_affiliation_ror', ''),
                        'display_name': affiliation,
                        'country_code': country,  # 可能仍然是空字符串
                        'type': author_data.get('primary_affiliation_type', '')
                    }
                    authorship['institutions'].append(institution)

                authorships.append(authorship)

            # 添加到 work._raw
            work['_raw']['authorships'] = authorships
            enriched_count += 1

        if verbose:
            print(f"  ✅ 批次完成，已增强 {enriched_count}/{len(dois)} 篇论文")

    if verbose:
        print(f"\n{'='*60}")
        print(f"✅ 数据增强完成!")
        print(f"成功增强: {enriched_count}/{len(dois)} 篇论文")
        print(f"{'='*60}\n")

    return works


async def enrich_and_save(
    input_path: str,
    output_path: str,
    max_works: Optional[int] = None,
    verbose: bool = True
):
    """
    加载数据、增强、并保存

    Args:
        input_path: 输入 JSON 文件路径
        output_path: 输出 JSON 文件路径
        max_works: 最大处理论文数（用于测试）
        verbose: 是否打印详细信息

    Example:
        >>> import asyncio
        >>> asyncio.run(enrich_and_save(
        >>>     'data/works_cache/works_query_all_1bf7ea910a2a.json',
        >>>     'data/works_cache/works_enriched.json',
        >>>     max_works=100  # 先测试100篇
        >>> ))
    """
    import json

    # 加载数据
    if verbose:
        print(f"加载数据: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    works = data if isinstance(data, list) else data.get('works', [])

    # 限制数量（如果指定）
    if max_works:
        works = works[:max_works]

    # 增强数据
    enriched_works = await enrich_works_with_institutions(works, verbose=verbose)

    # 保存数据
    if verbose:
        print(f"保存数据: {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enriched_works, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"✅ 数据已保存到: {output_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='为 works 数据增强机构信息')
    parser.add_argument('input', help='输入 JSON 文件路径')
    parser.add_argument('output', help='输出 JSON 文件路径')
    parser.add_argument('--max-works', type=int, help='最大处理论文数（用于测试）')
    parser.add_argument('--quiet', action='store_true', help='静默模式')

    args = parser.parse_args()

    asyncio.run(enrich_and_save(
        args.input,
        args.output,
        max_works=args.max_works,
        verbose=not args.quiet
    ))
