"""
Historical Direct Citation Network - 历史直接引用网络分析

基于 Eugene Garfield 的理论，分析文献集合内部的直接引用关系。

核心概念：
- LCS (Local Citation Score): 论文在数据集内部的被引次数
- GCS (Global Citation Score): 论文在全局的被引次数
- 关注数据集内部的知识流动和演化

功能：
1. 提取数据集内部的引用关系
2. 计算每篇论文的 LCS
3. 识别领域基石文献
4. 构建引用网络矩阵
5. 可视化时间演化

参考：
- Garfield, E. (2004). Historiographic mapping of knowledge domains literature.
- bibliometrix R package: histNetwork.R
"""

import pandas as pd
import numpy as np
import networkx as nx
from typing import List, Dict, Any, Tuple, Optional
from collections import Counter
import matplotlib.pyplot as plt
from datetime import datetime


class HistoricalCitationNetwork:
    """
    历史直接引用网络分析工具

    Example:
        >>> works = [...]  # 论文列表
        >>> hcn = HistoricalCitationNetwork(works)
        >>>
        >>> # 提取内部引用
        >>> citations_df = hcn.extract_internal_citations()
        >>>
        >>> # 计算 LCS
        >>> lcs_df = hcn.calculate_lcs()
        >>>
        >>> # 识别关键文献
        >>> key_papers = hcn.identify_key_papers(top_n=20)
        >>>
        >>> # 构建网络
        >>> network_matrix = hcn.build_network_matrix()
        >>>
        >>> # 完整分析
        >>> results = hcn.analyze()
    """

    def __init__(self, works: List[Dict[str, Any]], verbose: bool = True):
        """
        初始化历史引用网络分析器

        Args:
            works: 论文列表，每篇论文必须包含：
                - id: 论文唯一标识符
                - title: 标题
                - publication_year: 发表年份
                - cited_by_count: 全局被引次数（GCS）
                - referenced_works: 引用文献列表（可选）
            verbose: 是否打印详细信息
        """
        self.works = works
        self.verbose = verbose

        # 缓存计算结果
        self._citations_df = None
        self._lcs_df = None
        self._network_matrix = None
        self._work_ids = None
        self._id_to_work = None

        # 验证数据
        self._validate_data()

        if self.verbose:
            print(f"初始化历史引用网络分析器:")
            print(f"  论文数量: {len(self.works)}")
            year_range = self._get_year_range()
            if year_range:
                print(f"  年份范围: {year_range[0]} - {year_range[1]}")

    def _validate_data(self):
        """验证输入数据"""
        required_fields = ['id', 'title', 'publication_year']

        if not self.works:
            raise ValueError("论文列表不能为空")

        for i, work in enumerate(self.works[:5]):  # 检查前5篇
            for field in required_fields:
                if field not in work:
                    raise ValueError(
                        f"论文 {i} 缺少必需字段: {field}\n"
                        f"必需字段: {required_fields}"
                    )

    def _get_year_range(self) -> Optional[Tuple[int, int]]:
        """获取年份范围"""
        years = [w.get('publication_year') for w in self.works if w.get('publication_year')]
        if years:
            return min(years), max(years)
        return None

    def extract_internal_citations(self) -> pd.DataFrame:
        """
        提取数据集内部的引用关系

        只保留同时存在于数据集中的引用关系（citing → cited）

        Returns:
            DataFrame with columns: [citing_id, cited_id, citing_year, cited_year]

        Example:
            >>> citations = hcn.extract_internal_citations()
            >>> print(f"找到 {len(citations)} 条内部引用")
        """
        if self._citations_df is not None:
            return self._citations_df

        if self.verbose:
            print("\n提取数据集内部的引用关系...")

        # 构建ID集合（快速查找）
        work_ids = set(work['id'] for work in self.works)
        id_to_year = {work['id']: work.get('publication_year') for work in self.works}

        # 提取内部引用
        citations = []
        works_with_refs = 0
        total_refs = 0
        internal_refs = 0

        for work in self.works:
            citing_id = work['id']
            citing_year = work.get('publication_year')

            # 获取引用文献列表
            refs = work.get('referenced_works', [])

            if refs:
                works_with_refs += 1
                total_refs += len(refs)

                # 只保留数据集内部的引用
                for ref_id in refs:
                    if ref_id in work_ids:
                        cited_year = id_to_year.get(ref_id)
                        citations.append({
                            'citing_id': citing_id,
                            'cited_id': ref_id,
                            'citing_year': citing_year,
                            'cited_year': cited_year
                        })
                        internal_refs += 1

        self._citations_df = pd.DataFrame(citations)

        if self.verbose:
            print(f"  有引用文献的论文: {works_with_refs}/{len(self.works)}")
            print(f"  总引用文献数: {total_refs}")
            print(f"  数据集内部引用: {internal_refs}")
            if total_refs > 0:
                print(f"  内部引用比例: {internal_refs/total_refs*100:.1f}%")

        return self._citations_df

    def calculate_lcs(self) -> pd.DataFrame:
        """
        计算每篇论文的 Local Citation Score (LCS)

        LCS = 论文在数据集内部被引用的次数

        Returns:
            DataFrame with columns: [work_id, lcs, gcs, title, year]
            按 LCS 降序排序

        Example:
            >>> lcs_df = hcn.calculate_lcs()
            >>> print(lcs_df.head(10))  # 前10篇高LCS论文
        """
        if self._lcs_df is not None:
            return self._lcs_df

        # 确保已提取引用
        if self._citations_df is None:
            self.extract_internal_citations()

        if self.verbose:
            print("\n计算 Local Citation Score (LCS)...")

        # 计算 LCS（被引次数）
        lcs_counts = self._citations_df.groupby('cited_id').size().reset_index(name='lcs')

        # 创建完整的工作列表（包括LCS=0的论文）
        all_works = pd.DataFrame([
            {
                'work_id': work['id'],
                'title': work.get('title', '')[:100],  # 限制标题长度
                'year': work.get('publication_year'),
                'gcs': work.get('cited_by_count', 0)
            }
            for work in self.works
        ])

        # 合并 LCS
        result = all_works.merge(
            lcs_counts,
            left_on='work_id',
            right_on='cited_id',
            how='left'
        )

        # 填充缺失的 LCS（未被引用的论文）
        result['lcs'] = result['lcs'].fillna(0).astype(int)
        result = result.drop('cited_id', axis=1, errors='ignore')

        # 按 LCS 降序排序
        result = result.sort_values('lcs', ascending=False).reset_index(drop=True)

        self._lcs_df = result

        if self.verbose:
            print(f"  LCS > 0 的论文: {len(result[result['lcs'] > 0])}/{len(result)}")
            print(f"  最高 LCS: {result['lcs'].max()}")
            print(f"  平均 LCS: {result['lcs'].mean():.2f}")
            print(f"  中位数 LCS: {result['lcs'].median():.1f}")

        return self._lcs_df

    def identify_key_papers(
        self,
        top_n: int = 20,
        min_lcs: int = 1,
        criterion: str = 'lcs'
    ) -> pd.DataFrame:
        """
        识别关键文献

        Args:
            top_n: 返回前N篇论文
            min_lcs: 最小 LCS 阈值
            criterion: 排序标准 ('lcs', 'gcs', 或 'lcs/gcs')

        Returns:
            关键文献列表

        Example:
            >>> key_papers = hcn.identify_key_papers(top_n=10, criterion='lcs')
            >>> for _, paper in key_papers.iterrows():
            >>>     print(f"LCS={paper['lcs']}: {paper['title']}")
        """
        # 确保已计算 LCS
        if self._lcs_df is None:
            self.calculate_lcs()

        # 过滤
        result = self._lcs_df[self._lcs_df['lcs'] >= min_lcs].copy()

        # 按标准排序
        if criterion == 'lcs':
            result = result.sort_values('lcs', ascending=False)
        elif criterion == 'gcs':
            result = result.sort_values('gcs', ascending=False)
        elif criterion == 'lcs/gcs':
            # 计算 LCS/GCS 比率（避免除零）
            result['lcs_gcs_ratio'] = result['lcs'] / (result['gcs'] + 1)
            result = result.sort_values('lcs_gcs_ratio', ascending=False)
        else:
            raise ValueError(f"未知的排序标准: {criterion}")

        return result.head(top_n).reset_index(drop=True)

    def build_network_matrix(self) -> Tuple[np.ndarray, List[str]]:
        """
        构建引用网络邻接矩阵

        Returns:
            (adjacency_matrix, work_ids)
            - adjacency_matrix[i][j] = 1 表示论文i引用了论文j
            - work_ids: 论文ID列表（与矩阵索引对应）

        Example:
            >>> matrix, ids = hcn.build_network_matrix()
            >>> print(f"网络规模: {matrix.shape}")
            >>> print(f"引用关系数: {matrix.sum()}")
        """
        if self._network_matrix is not None and self._work_ids is not None:
            return self._network_matrix, self._work_ids

        # 确保已提取引用
        if self._citations_df is None:
            self.extract_internal_citations()

        if self.verbose:
            print("\n构建引用网络矩阵...")

        # 创建ID到索引的映射
        work_ids = [work['id'] for work in self.works]
        id_to_idx = {wid: idx for idx, wid in enumerate(work_ids)}

        # 初始化邻接矩阵
        n = len(work_ids)
        matrix = np.zeros((n, n), dtype=np.int8)

        # 填充矩阵
        for _, row in self._citations_df.iterrows():
            citing_idx = id_to_idx[row['citing_id']]
            cited_idx = id_to_idx[row['cited_id']]
            matrix[citing_idx][cited_idx] = 1

        self._network_matrix = matrix
        self._work_ids = work_ids

        if self.verbose:
            print(f"  矩阵规模: {n} × {n}")
            print(f"  引用关系数: {matrix.sum()}")
            density = matrix.sum() / (n * n) * 100
            print(f"  网络密度: {density:.2f}%")

        return self._network_matrix, self._work_ids

    def get_citation_graph(
        self,
        top_n: Optional[int] = None,
        min_lcs: int = 1
    ) -> nx.DiGraph:
        """
        获取 NetworkX 有向图对象

        Args:
            top_n: 只包含前N个高LCS论文（可选）
            min_lcs: 最小LCS阈值

        Returns:
            NetworkX DiGraph 对象，包含节点属性：
            - title: 标题
            - year: 年份
            - lcs: Local Citation Score
            - gcs: Global Citation Score

        Example:
            >>> G = hcn.get_citation_graph(top_n=50)
            >>> print(f"节点数: {G.number_of_nodes()}")
            >>> print(f"边数: {G.number_of_edges()}")
        """
        # 确保已计算 LCS 和网络矩阵
        if self._lcs_df is None:
            self.calculate_lcs()
        if self._network_matrix is None:
            self.build_network_matrix()

        # 筛选节点
        lcs_df = self._lcs_df[self._lcs_df['lcs'] >= min_lcs].copy()

        if top_n is not None:
            lcs_df = lcs_df.head(top_n)

        # 获取筛选后的索引
        selected_ids = set(lcs_df['work_id'].values)
        id_to_idx = {wid: idx for idx, wid in enumerate(self._work_ids)}
        selected_indices = [id_to_idx[wid] for wid in selected_ids if wid in id_to_idx]

        # 创建子图
        if selected_indices:
            sub_matrix = self._network_matrix[np.ix_(selected_indices, selected_indices)]
            sub_ids = [self._work_ids[i] for i in selected_indices]
        else:
            sub_matrix = self._network_matrix
            sub_ids = self._work_ids

        # 创建NetworkX图
        G = nx.DiGraph(sub_matrix)

        # 添加节点属性
        id_to_work = {w['id']: w for w in self.works}
        lcs_dict = dict(zip(lcs_df['work_id'], lcs_df['lcs']))

        for i, node in enumerate(G.nodes()):
            work_id = sub_ids[i]
            work = id_to_work.get(work_id, {})

            G.nodes[node]['work_id'] = work_id
            G.nodes[node]['title'] = work.get('title', '')[:80]
            G.nodes[node]['year'] = work.get('publication_year')
            G.nodes[node]['lcs'] = lcs_dict.get(work_id, 0)
            G.nodes[node]['gcs'] = work.get('cited_by_count', 0)

        return G

    def plot_network(
        self,
        top_n: int = 30,
        layout: str = 'temporal',
        figsize: Tuple[int, int] = (16, 10),
        save_path: Optional[str] = None
    ):
        """
        绘制历史引用网络图

        Args:
            top_n: 显示前N个高LCS论文
            layout: 布局方式 ('temporal'=时间轴, 'spring'=弹簧, 'circular'=环形)
            figsize: 图片尺寸
            save_path: 保存路径（可选）

        Example:
            >>> hcn.plot_network(top_n=20, layout='temporal')
            >>> hcn.plot_network(top_n=30, save_path='network.png')
        """
        # 获取图对象
        G = self.get_citation_graph(top_n=top_n, min_lcs=1)

        if G.number_of_nodes() == 0:
            print("警告: 没有符合条件的节点可以绘制")
            return

        # 计算布局
        if layout == 'temporal':
            pos = self._temporal_layout(G)
        elif layout == 'spring':
            pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)
        elif layout == 'circular':
            pos = nx.circular_layout(G)
        else:
            raise ValueError(f"未知的布局方式: {layout}")

        # 创建图形
        plt.figure(figsize=figsize)

        # 绘制边
        nx.draw_networkx_edges(
            G, pos,
            edge_color='gray',
            alpha=0.3,
            arrows=True,
            arrowsize=15,
            arrowstyle='->',
            width=1
        )

        # 节点大小（基于LCS）
        node_sizes = [G.nodes[n]['lcs'] * 100 + 100 for n in G.nodes()]

        # 节点颜色（基于年份）
        years = [G.nodes[n]['year'] for n in G.nodes()]
        node_colors = years

        # 绘制节点
        nodes = nx.draw_networkx_nodes(
            G, pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap=plt.cm.viridis,
            alpha=0.8,
            edgecolors='black',
            linewidths=1
        )

        # 添加颜色条
        plt.colorbar(nodes, label='Publication Year', shrink=0.8)

        # 添加标签（简化）
        labels = {}
        for n in G.nodes():
            title = G.nodes[n]['title'][:30]
            year = G.nodes[n]['year']
            lcs = G.nodes[n]['lcs']
            labels[n] = f"{title}...\n({year}, LCS={lcs})"

        nx.draw_networkx_labels(
            G, pos,
            labels,
            font_size=7,
            font_weight='bold'
        )

        plt.title(
            f"Historical Direct Citation Network (Top {top_n} papers by LCS)",
            fontsize=16,
            fontweight='bold'
        )
        plt.xlabel("Time Dimension" if layout == 'temporal' else "", fontsize=12)
        plt.axis('off')
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            if self.verbose:
                print(f"图片已保存到: {save_path}")

        plt.show()

    def _temporal_layout(self, G: nx.DiGraph) -> Dict:
        """
        时间轴布局（X轴=年份，Y轴=调整后的位置）
        """
        # 基础弹簧布局
        spring_pos = nx.spring_layout(G, k=0.5, iterations=50, seed=42)

        # X轴映射到年份
        years = [G.nodes[n]['year'] for n in G.nodes()]
        unique_years = sorted(set(years))
        year_to_x = {y: i for i, y in enumerate(unique_years)}

        # 归一化
        max_x = len(unique_years) - 1 if len(unique_years) > 1 else 1

        pos = {}
        for node in G.nodes():
            year = G.nodes[node]['year']
            x = year_to_x[year] / max_x
            y = spring_pos[node][1]
            pos[node] = (x, y)

        return pos

    def analyze(self) -> Dict[str, Any]:
        """
        执行完整分析

        Returns:
            {
                'summary': {...},          # 汇总统计
                'key_papers': [...],       # 关键文献
                'network_stats': {...},    # 网络统计
                'temporal_evolution': [...] # 时间演化
            }

        Example:
            >>> results = hcn.analyze()
            >>> print(results['summary'])
        """
        if self.verbose:
            print("\n" + "=" * 80)
            print(" 历史直接引用网络分析")
            print("=" * 80)

        # 1. 提取引用
        citations_df = self.extract_internal_citations()

        # 2. 计算LCS
        lcs_df = self.calculate_lcs()

        # 3. 构建网络
        matrix, work_ids = self.build_network_matrix()

        # 4. 识别关键文献
        key_papers = self.identify_key_papers(top_n=20)

        # 5. 网络统计
        G = self.get_citation_graph()
        network_stats = {
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
            'density': nx.density(G),
            'is_dag': nx.is_directed_acyclic_graph(G),
            'weakly_connected_components': nx.number_weakly_connected_components(G),
            'strongly_connected_components': nx.number_strongly_connected_components(G)
        }

        # 6. 时间演化
        temporal_stats = self._analyze_temporal_evolution(citations_df, lcs_df)

        # 7. 汇总统计
        summary = {
            'total_papers': len(self.works),
            'papers_with_lcs': len(lcs_df[lcs_df['lcs'] > 0]),
            'total_internal_citations': len(citations_df),
            'avg_lcs': float(lcs_df['lcs'].mean()),
            'max_lcs': int(lcs_df['lcs'].max()),
            'avg_gcs': float(lcs_df['gcs'].mean()),
            'internal_citation_rate': len(citations_df) / len(self.works) if len(self.works) > 0 else 0
        }

        if self.verbose:
            print("\n" + "=" * 80)
            print(" 分析完成")
            print("=" * 80)
            print(f"\n汇总统计:")
            for key, value in summary.items():
                print(f"  {key}: {value}")

        return {
            'summary': summary,
            'key_papers': key_papers.to_dict('records'),
            'network_stats': network_stats,
            'temporal_evolution': temporal_stats,
            'lcs_df': lcs_df,
            'citations_df': citations_df
        }

    def _analyze_temporal_evolution(
        self,
        citations_df: pd.DataFrame,
        lcs_df: pd.DataFrame
    ) -> List[Dict]:
        """分析时间演化模式"""
        # 按年份分组
        year_stats = []

        # 获取所有年份
        all_years = sorted(set(lcs_df['year'].dropna()))

        for year in all_years:
            # 该年发表的论文
            year_papers = lcs_df[lcs_df['year'] == year]

            # 该年论文的引用
            year_cites = citations_df[citations_df['citing_year'] == year]

            # 引用了多少之前的论文
            cited_years = citations_df[
                citations_df['citing_year'] == year
            ]['cited_year'].dropna()

            # 计算引用的时间跨度
            if len(cited_years) > 0:
                avg_citation_age = year - cited_years.mean()
                max_citation_age = year - cited_years.min()
            else:
                avg_citation_age = 0
                max_citation_age = 0

            year_stats.append({
                'year': int(year),
                'n_papers': len(year_papers),
                'avg_lcs': float(year_papers['lcs'].mean()) if len(year_papers) > 0 else 0,
                'avg_gcs': float(year_papers['gcs'].mean()) if len(year_papers) > 0 else 0,
                'n_citations_made': len(year_cites),
                'avg_citation_age': float(avg_citation_age),
                'max_citation_age': float(max_citation_age)
            })

        return year_stats


# 便捷函数
def analyze_historical_citations(
    works: List[Dict],
    top_n: int = 20,
    plot: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    一键分析历史引用网络

    Args:
        works: 论文列表
        top_n: 识别前N个关键文献
        plot: 是否绘制网络图
        verbose: 是否打印详细信息

    Returns:
        分析结果字典

    Example:
        >>> works = [...]
        >>> results = analyze_historical_citations(works, top_n=20)
        >>> print(results['summary'])
    """
    hcn = HistoricalCitationNetwork(works, verbose=verbose)
    results = hcn.analyze()

    if plot and len(works) > 0:
        hcn.plot_network(top_n=top_n)

    return results
