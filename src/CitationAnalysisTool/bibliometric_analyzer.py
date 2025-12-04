"""
基本文献计量分析工具 (Basic Bibliometric Analyzer)

该模块提供对学术论文数据进行基本描述性统计分析的功能。

主要功能：
1. 年度科学产出 (Annual scientific production)
2. 高产作者 (Most productive authors)
3. 高被引论文 (Most cited manuscripts)
4. 最相关的来源/期刊 (Most relevant sources/journals)
5. 最常见的关键词 (Most frequent keywords/topics)

Author: SciSciTool
Date: 2025-11-17
"""

from typing import Dict, List
from collections import defaultdict


def basic_bibliometric_analysis(
    works: List[Dict],
    top_authors: int = 20,
    top_papers: int = 20,
    top_sources: int = 20,
    top_keywords: int = 30
) -> Dict:
    """
    对论文数据进行基本文献计量分析（单函数完整实现）

    Args:
        works: 论文数据列表，每个元素是包含以下字段的字典：
            - id: 论文ID
            - title: 标题
            - publication_year: 发表年份
            - cited_by_count: 被引次数
            - authors: 作者列表 [{"id": "A123", "name": "John Doe"}, ...]
            - source: 来源信息 {"id": "S123", "name": "Nature", "type": "journal"}
            - topics: 主题列表 [{"id": "T123", "name": "ML", "score": 0.9}, ...]
            - doi: DOI (可选)
            - is_oa: 是否开放获取 (可选)

        top_authors: 返回前N位高产作者
        top_papers: 返回前N篇高被引论文
        top_sources: 返回前N个相关来源
        top_keywords: 返回前N个关键词

    Returns:
        {
            "annual_production": {...},       # 年度科学产出
            "most_productive_authors": {...}, # 高产作者
            "most_cited_papers": {...},       # 高被引论文
            "most_relevant_sources": {...},   # 最相关来源
            "most_frequent_keywords": {...}   # 最常见关键词
        }
    """
    n_papers = len(works)

    # ========== 1. 年度科学产出 ==========
    year_stats = defaultdict(lambda: {"n_papers": 0, "citations": []})
    for work in works:
        year = work.get("publication_year")
        if year:
            year_stats[year]["n_papers"] += 1
            year_stats[year]["citations"].append(work.get("cited_by_count", 0))

    annual_data = []
    for year, stats in year_stats.items():
        total_cit = sum(stats["citations"])
        annual_data.append({
            "year": year,
            "n_papers": stats["n_papers"],
            "total_citations": total_cit,
            "avg_citations": round(total_cit / stats["n_papers"], 2) if stats["n_papers"] > 0 else 0
        })
    annual_data.sort(key=lambda x: x["year"], reverse=True)

    # ========== 2. 高产作者 ==========
    author_stats = defaultdict(lambda: {"name": "", "papers": [], "citations": []})
    for work in works:
        for author in work.get("authors", []):
            aid = author.get("id")
            if aid:
                author_stats[aid]["name"] = author.get("name", "")
                author_stats[aid]["papers"].append(work.get("id"))
                author_stats[aid]["citations"].append(work.get("cited_by_count", 0))

    authors_data = []
    for aid, stats in author_stats.items():
        n_pap = len(stats["papers"])
        total_cit = sum(stats["citations"])
        # 计算h-index
        sorted_cit = sorted(stats["citations"], reverse=True)
        h_idx = sum(1 for i, c in enumerate(sorted_cit, 1) if c >= i)

        authors_data.append({
            "id": aid,
            "name": stats["name"],
            "n_papers": n_pap,
            "total_citations": total_cit,
            "avg_citations": round(total_cit / n_pap, 2) if n_pap > 0 else 0,
            "h_index": h_idx
        })
    authors_data.sort(key=lambda x: x["n_papers"], reverse=True)

    # ========== 3. 高被引论文 ==========
    papers_data = []
    sorted_works = sorted(works, key=lambda x: x.get("cited_by_count", 0), reverse=True)
    for rank, work in enumerate(sorted_works[:top_papers], 1):
        authors = work.get("authors", [])
        author_names = [a.get("name", "") for a in authors[:5] if a.get("name")]
        authors_str = "; ".join(author_names)
        if len(authors) > 5:
            authors_str += " et al."

        source = work.get("source", {})
        papers_data.append({
            "rank": rank,
            "id": work.get("id", ""),
            "title": work.get("title", ""),
            "authors": authors_str,
            "year": work.get("publication_year"),
            "source": source.get("name", "") if isinstance(source, dict) else "",
            "cited_by_count": work.get("cited_by_count", 0),
            "doi": work.get("doi", "")
        })

    total_citations = sum(w.get("cited_by_count", 0) for w in works)

    # ========== 4. 最相关来源 ==========
    source_stats = defaultdict(lambda: {"name": "", "type": "", "papers": [], "citations": []})
    for work in works:
        source = work.get("source", {})
        if isinstance(source, dict):
            sid = source.get("id")
            if sid:
                source_stats[sid]["name"] = source.get("name", "")
                source_stats[sid]["type"] = source.get("type", "")
                source_stats[sid]["papers"].append(work.get("id"))
                source_stats[sid]["citations"].append(work.get("cited_by_count", 0))

    sources_data = []
    for sid, stats in source_stats.items():
        n_pap = len(stats["papers"])
        total_cit = sum(stats["citations"])
        # h-index
        sorted_cit = sorted(stats["citations"], reverse=True)
        h_idx = sum(1 for i, c in enumerate(sorted_cit, 1) if c >= i)

        sources_data.append({
            "id": sid,
            "name": stats["name"],
            "type": stats["type"],
            "n_papers": n_pap,
            "total_citations": total_cit,
            "avg_citations": round(total_cit / n_pap, 2) if n_pap > 0 else 0,
            "h_index": h_idx
        })
    sources_data.sort(key=lambda x: x["n_papers"], reverse=True)

    # ========== 5. 最常见关键词 ==========
    topic_stats = defaultdict(lambda: {"name": "", "scores": [], "citations": []})
    for work in works:
        for topic in work.get("topics", []):
            tid = topic.get("id")
            if tid:
                topic_stats[tid]["name"] = topic.get("name", "")
                topic_stats[tid]["scores"].append(topic.get("score", 0))
                topic_stats[tid]["citations"].append(work.get("cited_by_count", 0))

    keywords_data = []
    for tid, stats in topic_stats.items():
        freq = len(stats["scores"])
        total_cit = sum(stats["citations"])
        keywords_data.append({
            "id": tid,
            "name": stats["name"],
            "frequency": freq,
            "percentage": round(freq / n_papers * 100, 2) if n_papers > 0 else 0,
            "avg_score": round(sum(stats["scores"]) / freq, 3) if freq > 0 else 0,
            "total_citations": total_cit,
            "avg_citations": round(total_cit / freq, 2) if freq > 0 else 0
        })
    keywords_data.sort(key=lambda x: x["frequency"], reverse=True)

    # ========== 返回结果 ==========
    return {
        "annual_production": {
            "total_papers": n_papers,
            "total_years": len(year_stats),
            "year_range": [min(year_stats.keys()), max(year_stats.keys())] if year_stats else [None, None],
            "annual_data": annual_data
        },
        "most_productive_authors": {
            "total_authors": len(author_stats),
            "authors": authors_data[:top_authors]
        },
        "most_cited_papers": {
            "total_papers": n_papers,
            "total_citations": total_citations,
            "avg_citations": round(total_citations / n_papers, 2) if n_papers > 0 else 0,
            "papers": papers_data
        },
        "most_relevant_sources": {
            "total_sources": len(source_stats),
            "sources": sources_data[:top_sources]
        },
        "most_frequent_keywords": {
            "total_topics": len(topic_stats),
            "keywords": keywords_data[:top_keywords]
        }
    }
