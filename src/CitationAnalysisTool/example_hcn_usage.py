"""
Historical Citation Network 使用示例

展示如何使用历史直接引用网络分析工具
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_project_root))

from src.CitationAnalysisTool import (
    HistoricalCitationNetwork,
    analyze_historical_citations
)
from src.DataExtractorTool.works_extractor import WorksExtractor


async def example1_basic_usage():
    """示例1: 基础使用"""
    print("=" * 80)
    print("示例 1: 基础使用 - 分析 scientometrics 领域")
    print("=" * 80 + "\n")

    # 获取数据
    extractor = WorksExtractor()
    result = await extractor.fetch_works(
        keywords="bibliometrics",
        publication_year=(2020, 2023),
        limit=50,
        sort_by="cited_by_count:desc"
    )

    works = result['works']
    print(f"获取到 {len(works)} 篇论文\n")

    # 创建分析器
    hcn = HistoricalCitationNetwork(works, verbose=True)

    # 计算LCS
    lcs_df = hcn.calculate_lcs()

    print("\n前10篇高LCS论文:")
    print("-" * 80)
    for i, row in lcs_df.head(10).iterrows():
        print(f"{i+1}. LCS={row['lcs']}, GCS={row['gcs']}")
        print(f"   {row['title'][:70]}...")
        print()


async def example2_identify_key_papers():
    """示例2: 识别关键文献"""
    print("=" * 80)
    print("示例 2: 识别领域基石文献")
    print("=" * 80 + "\n")

    # 获取数据
    extractor = WorksExtractor()
    result = await extractor.fetch_works(
        keywords="machine learning",
        publication_year=(2021, 2023),
        limit=100
    )

    works = result['works']

    # 分析
    hcn = HistoricalCitationNetwork(works, verbose=False)

    # 按LCS识别（领域影响力）
    print("领域基石文献（按LCS）：")
    print("-" * 80)
    key_papers_lcs = hcn.identify_key_papers(top_n=5, criterion='lcs')
    for i, row in key_papers_lcs.iterrows():
        print(f"{i+1}. LCS={row['lcs']}, GCS={row['gcs']}")
        print(f"   {row['title'][:70]}... ({row['year']})")
        print()

    # 按LCS/GCS识别（领域特异性）
    print("\n领域特异性文献（按LCS/GCS比率）：")
    print("-" * 80)
    key_papers_ratio = hcn.identify_key_papers(top_n=5, criterion='lcs/gcs')
    for i, row in key_papers_ratio.iterrows():
        ratio = row.get('lcs_gcs_ratio', row['lcs'] / (row['gcs'] + 1))
        print(f"{i+1}. LCS={row['lcs']}, GCS={row['gcs']}, 比率={ratio:.3f}")
        print(f"   {row['title'][:70]}...")
        print()


async def example3_network_analysis():
    """示例3: 网络分析"""
    print("=" * 80)
    print("示例 3: 引用网络分析")
    print("=" * 80 + "\n")

    # 获取数据
    extractor = WorksExtractor()
    result = await extractor.fetch_works(
        topic_name="information science",
        publication_year=(2020, 2022),
        limit=80
    )

    works = result['works']

    # 分析
    hcn = HistoricalCitationNetwork(works, verbose=False)

    # 获取NetworkX图
    import networkx as nx

    G = hcn.get_citation_graph(top_n=20, min_lcs=1)

    print(f"网络统计:")
    print(f"  节点数: {G.number_of_nodes()}")
    print(f"  边数: {G.number_of_edges()}")
    print(f"  密度: {nx.density(G):.4f}")
    print(f"  平均度: {sum(dict(G.degree()).values()) / G.number_of_nodes():.2f}")

    # 中心性分析
    if G.number_of_edges() > 0:
        print(f"\n中心性分析（前5个节点）:")

        # 度中心性
        degree_centrality = nx.degree_centrality(G)
        top_degree = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:5]

        print("\n度中心性最高的节点:")
        for node, centrality in top_degree:
            attrs = G.nodes[node]
            print(f"  - {attrs['title'][:50]}... (中心性: {centrality:.3f})")

        # 介数中心性
        betweenness = nx.betweenness_centrality(G)
        top_betweenness = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)[:5]

        print("\n介数中心性最高的节点:")
        for node, centrality in top_betweenness:
            attrs = G.nodes[node]
            print(f"  - {attrs['title'][:50]}... (中心性: {centrality:.3f})")

    print()


async def example4_temporal_evolution():
    """示例4: 时间演化分析"""
    print("=" * 80)
    print("示例 4: 时间演化分析")
    print("=" * 80 + "\n")

    # 获取数据
    extractor = WorksExtractor()
    result = await extractor.fetch_works(
        keywords="artificial intelligence",
        publication_year=(2020, 2023),
        limit=100
    )

    works = result['works']

    # 分析
    hcn = HistoricalCitationNetwork(works, verbose=False)
    results = hcn.analyze()

    print("时间演化统计:")
    print("-" * 80)
    print(f"{'年份':<8} {'论文数':<10} {'平均LCS':<12} {'平均GCS':<12} {'引用年龄':<12}")
    print("-" * 80)

    for stat in results['temporal_evolution']:
        print(f"{stat['year']:<8} "
              f"{stat['n_papers']:<10} "
              f"{stat['avg_lcs']:<12.2f} "
              f"{stat['avg_gcs']:<12.1f} "
              f"{stat['avg_citation_age']:<12.1f}")

    print()


async def example5_quick_analysis():
    """示例5: 一键分析"""
    print("=" * 80)
    print("示例 5: 一键分析 + 可视化")
    print("=" * 80 + "\n")

    # 获取数据
    extractor = WorksExtractor()
    result = await extractor.fetch_works(
        keywords="deep learning",
        publication_year=(2021, 2023),
        limit=60
    )

    works = result['works']

    # 一键分析
    results = analyze_historical_citations(
        works,
        top_n=15,
        plot=False,  # 设为 True 可绘图
        verbose=True
    )

    print("\n分析结果汇总:")
    print("-" * 80)
    for key, value in results['summary'].items():
        print(f"  {key}: {value}")

    print("\n网络统计:")
    print("-" * 80)
    for key, value in results['network_stats'].items():
        print(f"  {key}: {value}")

    print()


async def example6_compare_fields():
    """示例6: 对比不同领域"""
    print("=" * 80)
    print("示例 6: 对比不同研究领域的引用模式")
    print("=" * 80 + "\n")

    extractor = WorksExtractor()

    # 领域1: Machine Learning
    result1 = await extractor.fetch_works(
        keywords="machine learning",
        publication_year=(2021, 2023),
        limit=50
    )

    # 领域2: Scientometrics
    result2 = await extractor.fetch_works(
        keywords="scientometrics",
        publication_year=(2021, 2023),
        limit=50
    )

    # 分析两个领域
    hcn1 = HistoricalCitationNetwork(result1['works'], verbose=False)
    hcn2 = HistoricalCitationNetwork(result2['works'], verbose=False)

    results1 = hcn1.analyze()
    results2 = hcn2.analyze()

    # 对比
    print(f"{'指标':<35} {'Machine Learning':<20} {'Scientometrics':<20}")
    print("-" * 75)

    metrics = ['total_papers', 'papers_with_lcs', 'total_internal_citations',
               'avg_lcs', 'max_lcs', 'internal_citation_rate']

    for metric in metrics:
        val1 = results1['summary'][metric]
        val2 = results2['summary'][metric]

        if isinstance(val1, float):
            print(f"{metric:<35} {val1:<20.2f} {val2:<20.2f}")
        else:
            print(f"{metric:<35} {val1:<20} {val2:<20}")

    print()


async def main():
    """运行所有示例"""
    print("\n" + "=" * 80)
    print(" Historical Citation Network 使用示例")
    print("=" * 80 + "\n")

    try:
        # 示例 1: 基础使用
        await example1_basic_usage()

        # 示例 2: 识别关键文献
        await example2_identify_key_papers()

        # 示例 3: 网络分析
        await example3_network_analysis()

        # 示例 4: 时间演化
        await example4_temporal_evolution()

        # 示例 5: 一键分析
        await example5_quick_analysis()

        # 示例 6: 对比领域
        await example6_compare_fields()

        print("=" * 80)
        print(" 所有示例完成！")
        print("=" * 80)

    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 运行所有示例
    asyncio.run(main())

    # 或者运行单个示例
    # asyncio.run(example1_basic_usage())
