"""
快速测试 data_enricher - 使用 API 获取机构信息

推荐方式：使用 AuthorQuery API，避免数据库问题
"""

import asyncio
import json
import sys
from pathlib import Path

# 添加项目路径
_project_root = Path(__file__).parent.parent.parent
_src_path = _project_root / 'src'
sys.path.insert(0, str(_project_root))
sys.path.insert(0, str(_src_path))

from MacroAnalysisTool.data_enricher import enrich_works_with_institutions
from MacroAnalysisTool.macro_analyzer import MacroAnalyzer


async def main():
    """完整的测试流程"""
    print("\n" + "="*70)
    print("MacroAnalyzer 完整测试 - 使用 API 获取机构信息（推荐方式）")
    print("="*70)

    # 1. 加载测试数据
    print("\n[1/4] 加载测试数据...")
    data_path = _project_root / 'data/works_cache/works_query_all_1bf7ea910a2a.json'

    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    works = data if isinstance(data, list) else data.get('works', [])
    print(f"✅ 加载了 {len(works)} 篇论文")

    # 2. 使用 data_enricher 增强数据（测试少量数据）
    print("\n[2/4] 使用 API 获取机构信息（测试 30 篇论文）...")
    test_works = works[:30]

    enriched_works = await enrich_works_with_institutions(
        test_works,
        verbose=True,
        max_workers=20  # 并发数
    )

    # 3. 使用 MacroAnalyzer 分析
    print("\n[3/4] 使用 MacroAnalyzer 分析...")
    analyzer = MacroAnalyzer(verbose=True)
    analyzer.load_data(enriched_works, enrich_institutions=False)

    # 4. 查看结果
    print("\n[4/4] 分析结果...")
    analyzer.print_summary()

    # 5. 测试可视化（可选）
    print("\n[5/5] 测试生成统计数据...")
    try:
        country_stats = analyzer.get_country_statistics()
        print(f"\n✅ 成功生成国家统计数据")
        print(f"国家数量: {len(country_stats.columns)}")
        print(f"年份范围: {country_stats.index.min()} - {country_stats.index.max()}")

        # 显示 top 5 国家
        country_totals = country_stats.sum().sort_values(ascending=False)
        print(f"\nTop 5 国家:")
        for i, (country, count) in enumerate(country_totals.head(5).items(), 1):
            print(f"  {i}. {country}: {count} 篇")

        institution_stats = analyzer.get_institution_statistics(topn=10)
        print(f"\n✅ 成功生成机构统计数据")
        print(f"机构数量: {len(institution_stats.columns)}")

        # 显示 top 5 机构
        inst_totals = institution_stats.sum().sort_values(ascending=False)
        print(f"\nTop 5 机构:")
        for i, (inst, count) in enumerate(inst_totals.head(5).items(), 1):
            inst_name = inst if len(inst) <= 50 else inst[:47] + "..."
            print(f"  {i}. {inst_name}: {count} 篇")

    except Exception as e:
        print(f"⚠️  统计失败: {e}")

    print("\n" + "="*70)
    print("✅ 测试完成!")
    print("="*70)
    print("\n💡 提示: 这个方法使用 API 获取数据，不依赖数据库，更稳定！")
    print("💡 如需处理全部 1384 篇论文，请调整 test_works = works[:1384]")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
