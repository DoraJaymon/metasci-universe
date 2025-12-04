"""
辅助搜索功能示例 - Helper Search Examples

展示如何使用 WorksExtractor 的辅助搜索功能来发现 OpenAlex 实体 ID

使用场景：用户通常不知道精确的 topic_id, author_id, institution_id 等，
需要先通过名称搜索找到候选项，然后再用于精确过滤。
"""

import asyncio
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

# 添加 src 目录到路径
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from DataExtractorTool.works_extractor import WorksExtractor


async def example_topic_search():
    """示例 1: 搜索主题"""
    print("\n" + "=" * 70)
    print("示例 1: 搜索主题（Topic）")
    print("=" * 70)

    extractor = WorksExtractor()

    # 场景：用户想研究"科学计量学"领域，但不知道 topic_id
    print("\n🔍 搜索主题: 'scientometrics'")
    topics = await extractor.search_topics("scientometrics", limit=5)

    print(f"\n找到 {len(topics)} 个相关主题:\n")
    for i, topic in enumerate(topics, 1):
        print(f"{i}. {topic['name']}")
        print(f"   ID: {topic['id']}")
        print(f"   描述: {topic['description'][:100]}..." if len(topic['description']) > 100 else f"   描述: {topic['description']}")
        print(f"   论文数: {topic['works_count']:,}")
        print()

    # 使用第一个主题 ID 进行论文查询
    if topics:
        topic_id = topics[0]['id']
        print(f"📄 使用主题 '{topics[0]['name']}' (ID: {topic_id}) 查询论文...\n")

        result = await extractor.fetch_works(
            topic_id=topic_id,
            publication_year=(2022, 2024),
            limit=10
        )

        print(f"✅ 找到 {result['total']} 篇论文")
        print(f"   数据源: {result['source']}")
        print(f"\n前 3 篇论文:")
        for i, work in enumerate(result['works'][:3], 1):
            title = work['title'][:60] + "..." if len(work['title']) > 60 else work['title']
            print(f"  {i}. {title}")
            print(f"     年份: {work['publication_year']} | 被引: {work['cited_by_count']}次")


async def example_author_search():
    """示例 2: 搜索作者"""
    print("\n" + "=" * 70)
    print("示例 2: 搜索作者（Author）")
    print("=" * 70)

    extractor = WorksExtractor()

    # 场景：用户想找某个作者的论文，但不知道精确的 author_id
    print("\n🔍 搜索作者: 'Loet Leydesdorff'")
    authors = await extractor.search_authors("Loet Leydesdorff", limit=5)

    print(f"\n找到 {len(authors)} 个相关作者:\n")
    for i, author in enumerate(authors, 1):
        print(f"{i}. {author['name']}")
        print(f"   ID: {author['id']}")
        print(f"   机构: {author['affiliation']}")
        print(f"   论文数: {author['works_count']} | 被引: {author['cited_by_count']:,}")
        print()

    # 使用第一个作者 ID 进行论文查询
    if authors:
        author_id = authors[0]['id']
        print(f"📄 查询作者 '{authors[0]['name']}' 的论文...\n")

        result = await extractor.fetch_works(
            author_id=author_id,
            publication_year=">2020",
            limit=10
        )

        print(f"✅ 找到 {result['total']} 篇论文")
        print(f"   数据源: {result['source']}")
        print(f"\n最新 3 篇论文:")
        for i, work in enumerate(result['works'][:3], 1):
            title = work['title'][:60] + "..." if len(work['title']) > 60 else work['title']
            print(f"  {i}. {title}")
            print(f"     年份: {work['publication_year']} | 被引: {work['cited_by_count']}次")


async def example_institution_search():
    """示例 3: 搜索机构"""
    print("\n" + "=" * 70)
    print("示例 3: 搜索机构（Institution）")
    print("=" * 70)

    extractor = WorksExtractor()

    # 场景：用户想找某个大学的论文
    print("\n🔍 搜索机构: 'Tsinghua University'")
    institutions = await extractor.search_institutions("Tsinghua University", limit=3)

    print(f"\n找到 {len(institutions)} 个相关机构:\n")
    for i, inst in enumerate(institutions, 1):
        print(f"{i}. {inst['name']}")
        print(f"   ID: {inst['id']}")
        print(f"   国家: {inst['country']} | 类型: {inst['type']}")
        print(f"   论文数: {inst['works_count']:,}")
        print()

    # 使用第一个机构 ID 进行论文查询
    if institutions:
        institution_id = institutions[0]['id']
        print(f"📄 查询机构 '{institutions[0]['name']}' 在机器学习领域的论文...\n")

        result = await extractor.fetch_works(
            institution_id=institution_id,
            keywords="machine learning",
            publication_year=(2023, 2024),
            limit=10
        )

        print(f"✅ 找到 {result['total']} 篇论文")
        print(f"   数据源: {result['source']}")


async def example_source_search():
    """示例 4: 搜索期刊/来源"""
    print("\n" + "=" * 70)
    print("示例 4: 搜索期刊/来源（Source）")
    print("=" * 70)

    extractor = WorksExtractor()

    # 场景：用户想找某个期刊上的论文
    print("\n🔍 搜索期刊: 'Scientometrics'")
    sources = await extractor.search_sources("Scientometrics", limit=5)

    print(f"\n找到 {len(sources)} 个相关期刊:\n")
    for i, source in enumerate(sources, 1):
        print(f"{i}. {source['name']}")
        print(f"   ID: {source['id']}")
        print(f"   类型: {source['type']} | 出版商: {source['publisher']}")
        print(f"   论文数: {source['works_count']:,}")
        print()

    # 使用第一个期刊 ID 进行论文查询
    if sources:
        source_id = sources[0]['id']
        print(f"📄 查询期刊 '{sources[0]['name']}' 的最新论文...\n")

        result = await extractor.fetch_works(
            source_id=source_id,
            publication_year=">2022",
            limit=10,
            sort_by="publication_year:desc"
        )

        print(f"✅ 找到 {result['total']} 篇论文")
        print(f"   数据源: {result['source']}")


async def example_smart_search():
    """示例 5: 使用 smart_search 统一接口"""
    print("\n" + "=" * 70)
    print("示例 5: 使用 smart_search() 统一接口")
    print("=" * 70)

    extractor = WorksExtractor()

    # 方式 1: 获取候选列表
    print("\n📋 方式 1: 获取候选列表")
    print("🔍 搜索主题: 'artificial intelligence'")
    topics = await extractor.smart_search("topic", "artificial intelligence", auto_select=False)

    print(f"\n找到 {len(topics)} 个候选主题:")
    for i, topic in enumerate(topics[:3], 1):
        print(f"  {i}. {topic['name']} (ID: {topic['id']})")

    # 方式 2: 自动选择第一个结果
    print("\n\n🎯 方式 2: 自动选择第一个结果")
    print("🔍 搜索作者: 'Andrew Ng'")
    author_id = await extractor.smart_search("author", "Andrew Ng", auto_select=True)

    print(f"\n自动选择的作者 ID: {author_id}")

    if author_id:
        result = await extractor.fetch_works(
            author_id=author_id,
            publication_year=">2020",
            limit=5
        )
        print(f"\n✅ 找到该作者的 {result['total']} 篇论文（2020年后）")


async def example_complete_workflow():
    """示例 6: 完整工作流程 - 从搜索到查询"""
    print("\n" + "=" * 70)
    print("示例 6: 完整工作流程")
    print("=" * 70)
    print("\n场景：查找清华大学在人工智能领域的高被引论文\n")

    extractor = WorksExtractor()

    # 第 1 步：搜索主题
    print("步骤 1️⃣: 搜索主题 'artificial intelligence'")
    topic_id = await extractor.smart_search("topic", "artificial intelligence", auto_select=True)
    print(f"       → 选择主题 ID: {topic_id}\n")

    # 第 2 步：搜索机构
    print("步骤 2️⃣: 搜索机构 'Tsinghua University'")
    institution_id = await extractor.smart_search("institution", "Tsinghua University", auto_select=True)
    print(f"       → 选择机构 ID: {institution_id}\n")

    # 第 3 步：组合查询
    print("步骤 3️⃣: 组合查询（主题 + 机构 + 被引次数）\n")

    result = await extractor.fetch_works(
        topic_id=topic_id,
        institution_id=institution_id,
        cited_by_count=">50",
        publication_year=(2020, 2024),
        limit=20,
        sort_by="cited_by_count:desc"
    )

    print(f"✅ 找到 {result['total']} 篇符合条件的论文")
    print(f"   数据源: {result['source']}")
    print(f"   执行时间: {result['execution_time']:.2f} 秒")

    print(f"\n🏆 Top 5 高被引论文:")
    for i, work in enumerate(result['works'][:5], 1):
        title = work['title'][:65] + "..." if len(work['title']) > 65 else work['title']
        print(f"\n  {i}. {title}")
        print(f"     年份: {work['publication_year']} | 被引: {work['cited_by_count']}次")
        if work.get('authors'):
            authors_str = ", ".join([a['name'] for a in work['authors'][:3]])
            if len(work['authors']) > 3:
                authors_str += f" 等 {len(work['authors'])} 位作者"
            print(f"     作者: {authors_str}")


async def main():
    """运行所有示例"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "WorksExtractor 辅助搜索功能示例" + " " * 16 + "║")
    print("╚" + "=" * 68 + "╝")

    print("\n💡 提示：这些示例展示了如何使用辅助搜索功能来发现 OpenAlex 实体 ID")
    print("   用户通常不知道精确的 topic_id, author_id 等，需要先搜索再查询。")

    # 运行所有示例
    await example_topic_search()
    await example_author_search()
    await example_institution_search()
    await example_source_search()
    await example_smart_search()
    await example_complete_workflow()

    print("\n" + "=" * 70)
    print("✅ 所有示例运行完成！")
    print("=" * 70)
    print("\n📚 更多用法请参考: src/DataExtractorTool/README.md")
    print()


if __name__ == "__main__":
    asyncio.run(main())
