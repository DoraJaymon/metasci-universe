"""
RPYS (Reference Publication Year Spectroscopy) 实现

该模块实现了引用出版年份谱分析，用于检测研究领域的历史根源。

核心功能：
1. 智能数据准备（支持API和数据库）
2. 计算每年被引次数
3. 计算与5年中位数的偏差
4. 识别重要的历史文献年份
5. 生成可视化图表

参考文献：
Marx, W., Bornmann, L., Barth, A., & Leydesdorff, L. (2014).
Detecting the historical roots of research fields by reference publication
year spectroscopy (RPYS). JASIST, 65(4), 751-764.

Author: SciSciTool
Date: 2025-11-18
"""

from typing import Dict, List, Optional, Tuple
from collections import defaultdict, Counter
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import json
import asyncio
from datetime import datetime
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
import plotly.graph_objects as go
import plotly.io as pio


class RPYS:
    """
    RPYS (Reference Publication Year Spectroscopy) 分析类

    提供完整的RPYS分析流程，包括数据准备、分析和可视化。

    Example:
        >>> rpys = RPYS()
        >>> # 准备数据（自动缓存）
        >>> works = await rpys.prepare_data(
        ...     keywords="scientometrics",
        ...     limit=100,
        ...     data_source="api"  # 或 "database"
        ... )
        >>> # 执行分析
        >>> result = rpys.analyze(works)
        >>> # 查看结果
        >>> rpys.plot(result)
    """

    def __init__(self, cache_dir: Optional[str] = None, verbose: bool = True):
        """
        初始化RPYS分析器

        Args:
            cache_dir: 缓存目录，默认为 MetaSciToolUniverse/data/
            verbose: 是否打印详细信息
        """
        self.verbose = verbose

        # 设置缓存目录（默认为项目根目录的data文件夹）
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / "data"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(exist_ok=True, parents=True)

        # 创建数据管理器
        import sys
        src_path = Path(__file__).parent.parent
        if str(src_path) not in sys.path:
            sys.path.insert(0, str(src_path))

        from DataExtractorTool.works_data_manager import WorksDataManager
        self.data_manager = WorksDataManager(
            cache_dir=self.cache_dir / "rpys_cache",
            verbose=verbose
        )
    async def prepare_data(
        self,
        filters: Optional[Dict] = None,
        data_file: Optional[str] = None,
        data_source: str = "api",
        db_connection=None,
        force_refetch: bool = False,
        # 向后兼容参数（将转换为 filters）
        keywords: Optional[str] = None,
        publication_year: Optional[Tuple[int, int]] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        智能准备RPYS分析所需的数据

        该方法现在委托给 WorksDataManager 处理数据获取和缓存。

        Args:
            filters: 查询过滤条件字典（推荐使用）
            data_file: 数据文件路径（默认保存在cache_dir）
            data_source: 数据来源 "api" 或 "database"
            db_connection: 数据库连接（当data_source="database"时需要）
            force_refetch: 是否强制重新获取数据（忽略缓存）

            # 向后兼容参数
            keywords: 搜索关键词（将转换为 filters）
            publication_year: 年份范围（将转换为 filters）
            limit: 获取论文数量（将转换为 filters）

        Returns:
            包含 referenced_works_details 的论文数据列表

        Examples:
            # 新方式（推荐）
            works = await rpys.prepare_data(
                filters={
                    "keywords": "scientometrics",
                    "publication_year": (2020, 2024),
                    "limit": 100
                }
            )

            # 旧方式（仍然支持）
            works = await rpys.prepare_data(
                keywords="scientometrics",
                publication_year=(2020, 2024),
                limit=100
            )
        """
        if self.verbose:
            print(f"[RPYS] 开始数据准备...")

        # 处理向后兼容参数
        if filters is None:
            filters = {}

        # 合并旧参数到 filters
        if keywords is not None:
            filters.setdefault('keywords', keywords)
        if publication_year is not None:
            filters.setdefault('publication_year', publication_year)
        if limit is not None:
            filters.setdefault('limit', limit)

        # 设置默认值
        filters.setdefault('limit', 100)
        filters.setdefault('publication_year', (2020, 2024))

        # 委托给 WorksDataManager
        works = await self.data_manager.prepare_dataset(
            filters=filters,
            include_references=True,  # RPYS 必须包含引用详情
            data_source=data_source,
            db_connection=db_connection,
            use_cache=True,
            force_refetch=force_refetch,
            cache_file=data_file
        )

        if self.verbose:
            info = self.data_manager.get_dataset_info(works)
            print(f"[RPYS] ✅ 数据准备完成！")
            print(f"[RPYS]    论文数: {info['n_works']}")
            print(f"[RPYS]    年份范围: {info['year_range']}")
            print(f"[RPYS]    引用文献数: {info['n_references']}")
            print(f"[RPYS]    平均引用数: {info['avg_references_per_work']:.1f}")

        return works

    def classify_references(
        self,
        works: List[Dict],
        min_sequence_length: int = 3,
        min_citations: int = 5
    ) -> pd.DataFrame:
        """
        对引用文献进行四种类型分类（基于符号序列分析）

        根据 bibliometrix 的实现，识别四种有影响力的参考文献：
        1. Hot Papers (HP) - 热门论文：最近发表立即获得强烈关注
        2. Sleeping Beauties (SB) - 睡美人：最初被忽视后来被认可
        3. Life Cycle (LC) - 生命周期：典型的上升和下降模式
        4. Constant Performers (CP) - 稳定贡献者：长期持续被引用

        Args:
            works: 论文列表（必须包含 referenced_works_details）
            min_sequence_length: 最小序列长度（默认3）
            min_citations: 最小引用次数（默认5）

        Returns:
            DataFrame with columns: [ref_id, ref_year, title, total_citations, sequence, freqYC, freqO, types]
        """
        import re

        if self.verbose:
            print(f"[RPYS] 开始引用文献分类...")

        # ============ 步骤1: 构建引用-年份矩阵 ============
        citation_matrix_data = []
        reference_metadata = {}

        for work in works:
            citing_year = work.get('publication_year')
            if not citing_year:
                continue

            for ref in work.get('referenced_works_details', []):
                ref_id = ref.get('id', '')
                ref_year = ref.get('publication_year')

                if not ref_id or not ref_year:
                    continue

                # 年份合理性检查
                current_year = datetime.now().year
                if ref_year < 1700 or ref_year > current_year:
                    continue

                # 不能引用未来的文献
                if citing_year < ref_year:
                    continue

                citation_matrix_data.append({
                    'ref_id': ref_id,
                    'ref_year': ref_year,
                    'citing_year': citing_year
                })

                # 保存元数据
                if ref_id not in reference_metadata:
                    reference_metadata[ref_id] = {
                        'title': ref.get('title', ref.get('display_name', 'Unknown')),
                        'cited_by_count': ref.get('cited_by_count', 0)
                    }

        if not citation_matrix_data:
            if self.verbose:
                print(f"[RPYS] ⚠️  没有有效的引用记录")
            return pd.DataFrame()

        df = pd.DataFrame(citation_matrix_data)

        if self.verbose:
            print(f"[RPYS] 构建引用矩阵: {len(citation_matrix_data)} 条记录")

        # 透视为矩阵: 行=(ref_id, ref_year), 列=citing_year, 值=count
        citation_matrix = df.pivot_table(
            index=['ref_id', 'ref_year'],
            columns='citing_year',
            aggfunc='size',
            fill_value=0
        )

        if self.verbose:
            print(f"[RPYS] 矩阵大小: {citation_matrix.shape[0]} 引用文献 × {citation_matrix.shape[1]} 引用年份")

        # ============ 步骤2: 计算期望频率和Z值 ============
        citing_years = sorted(citation_matrix.columns)
        z_scores_dict = {}  # (ref_id, ref_year) -> z_scores_array

        # 按被引文献的发表年份分组
        for ref_year in sorted(citation_matrix.index.get_level_values('ref_year').unique()):
            # 同一年发表的引用文献
            refs_in_year = citation_matrix.loc[
                citation_matrix.index.get_level_values('ref_year') == ref_year
            ]

            if len(refs_in_year) <= 1:
                # 单个文献无法计算期望频率，Z值设为0
                for idx in refs_in_year.index:
                    z_scores_dict[idx] = np.zeros(len(citing_years))
                continue

            # 观察频率矩阵
            observed = refs_in_year.values.astype(float)

            # 行边际和 (每篇文献的总引用次数)
            row_sums = observed.sum(axis=1, keepdims=True)
            # 列边际和 (每年的总引用次数)
            col_sums = observed.sum(axis=0, keepdims=True)
            # 总和
            total = observed.sum()

            if total == 0:
                # 无引用，Z值全为0
                for idx in refs_in_year.index:
                    z_scores_dict[idx] = np.zeros(len(citing_years))
                continue

            # 期望频率 = (行和 * 列和) / 总和
            expected = (row_sums @ col_sums) / total

            # 避免除以零
            expected = np.where(expected < 1e-6, 1e-6, expected)

            # 标准化残差 Z = (观察 - 期望) / sqrt(期望)
            z_scores = (observed - expected) / np.sqrt(expected)

            # 处理无穷大和NaN
            z_scores = np.nan_to_num(z_scores, nan=0.0, posinf=0.0, neginf=0.0)

            # 保存结果
            for i, idx in enumerate(refs_in_year.index):
                z_scores_dict[idx] = z_scores[i]

        if self.verbose:
            print(f"[RPYS] Z值计算完成: {len(z_scores_dict)} 篇文献")

        # ============ 步骤3: 生成符号序列 ============
        def z_to_symbol(z):
            """将Z值转换为符号"""
            if z >= 1:
                return "+"
            elif z <= -1:
                return "-"
            else:
                return "o"

        sequences_data = []

        for (ref_id, ref_year), z_array in z_scores_dict.items():
            # 获取观察频率（原始引用次数）
            observed_array = citation_matrix.loc[(ref_id, ref_year)].values

            # 只保留 citing_year >= ref_year 的部分
            valid_indices = [i for i, year in enumerate(citing_years) if year >= ref_year]
            if not valid_indices:
                continue

            valid_z = z_array[valid_indices]
            valid_observed = observed_array[valid_indices]

            # 生成符号序列
            sequence = "".join([z_to_symbol(z) for z in valid_z])

            # 计算频率指标
            freqYC = np.sum(valid_observed > 0) / len(valid_observed)  # 被引年份覆盖率
            freqO = np.sum(valid_z > -1) / len(valid_z)  # 非负Z值比例

            # 总引用次数
            total_citations = int(np.sum(valid_observed))

            # 过滤掉引用次数太少的文献
            if total_citations < min_citations:
                continue

            # 过滤掉序列太短的文献
            if len(sequence) < min_sequence_length:
                continue

            sequences_data.append({
                'ref_id': ref_id,
                'ref_year': int(ref_year),
                'sequence': sequence,
                'freqYC': freqYC,
                'freqO': freqO,
                'total_citations': total_citations,
                'title': reference_metadata.get(ref_id, {}).get('title', 'Unknown'),
                'cited_by_count': reference_metadata.get(ref_id, {}).get('cited_by_count', 0)
            })

        if not sequences_data:
            if self.verbose:
                print(f"[RPYS] ⚠️  没有符合条件的引用文献")
            return pd.DataFrame()

        if self.verbose:
            print(f"[RPYS] 符号序列生成完成: {len(sequences_data)} 篇文献")

        # ============ 步骤4: 识别四种类型 ============
        def classify_sequence(seq_data):
            """
            根据符号序列分类引用文献

            Args:
                seq_data: dict with keys: sequence, freqYC, freqO

            Returns:
                list of types: ["Hot Paper", "Sleeping Beauty", ...]
            """
            seq = seq_data['sequence']
            freqYC = seq_data['freqYC']
            freqO = seq_data['freqO']

            if len(seq) == 0:
                return []

            types = []

            # 分割序列
            seq1 = seq[:4] if len(seq) >= 4 else seq
            seq2 = seq[4:] if len(seq) > 4 else ""
            seq3 = seq[-3:] if len(seq) > 6 else ""

            # 1. Sleeping Beauty (SB)
            # 开始有连续2个或更多 "-"，后面有 "+"
            if re.search(r'-{2,}', seq[:3]) and re.search(r'\+', seq[3:]):
                types.append("Sleeping Beauty")

            # 2. Constant Performer (CP)
            # 高频率覆盖率、高非负比例、序列长度>2
            if freqO >= 0.8 and freqYC >= 0.8 and len(seq) > 2:
                types.append("Constant Performer")

            # 3. Hot Paper (HP)
            # 开始有连续2个或更多 "+"
            if re.search(r'\+{2,}', seq[:3]):
                types.append("Hot Paper")

            # 4. Life Cycle (LC)
            # 前4个没有连续3+个"+"，中间有连续2+个"+"
            has_early_peak = bool(re.search(r'\+{3,}', seq1))
            has_middle_peak = bool(re.search(r'\+{2,}', seq2))

            if not has_early_peak and has_middle_peak and len(seq2) > 0:
                types.append("Life Cycle")

            return types

        # 应用分类
        for seq_data in sequences_data:
            seq_data['types'] = classify_sequence(seq_data)

        result_df = pd.DataFrame(sequences_data)

        if self.verbose:
            type_counts = {
                'Hot Paper': sum(1 for row in sequences_data if 'Hot Paper' in row['types']),
                'Sleeping Beauty': sum(1 for row in sequences_data if 'Sleeping Beauty' in row['types']),
                'Life Cycle': sum(1 for row in sequences_data if 'Life Cycle' in row['types']),
                'Constant Performer': sum(1 for row in sequences_data if 'Constant Performer' in row['types'])
            }
            print(f"[RPYS] 分类结果:")
            for type_name, count in type_counts.items():
                print(f"  - {type_name}: {count}")

        return result_df

    def analyze(
        self,
        works: List[Dict],
        timespan: Optional[Tuple[int, int]] = None,
        median_window: str = "centered",
        top_refs_per_year: int = 3,
        classify_refs: bool = True
    ) -> Dict:
        """
        执行RPYS分析

        Args:
            works: 论文数据列表（必须包含referenced_works_details）
            timespan: 分析的年份范围 (min_year, max_year)
            median_window: 中位数窗口类型 "centered" 或 "backward"
            top_refs_per_year: 每年显示的top引用文献数量
            classify_refs: 是否对引用文献进行四种类型分类（默认True）

        Returns:
            包含分析结果的字典
        """
        if not works:
            raise ValueError("输入的论文数据不能为空")

        if self.verbose:
            print(f"[RPYS] 开始分析 {len(works)} 篇论文...")

        # ============ 1. 提取引用记录 ============
        citation_records = []
        reference_info = {}

        for work in works:
            citing_year = work.get("publication_year")
            if not citing_year:
                continue

            ref_details = work.get("referenced_works_details", [])

            if not ref_details:
                if self.verbose:
                    print(f"[RPYS] ⚠️  警告：论文缺少referenced_works_details")
                continue

            for ref in ref_details:
                ref_id = ref.get("id", "")
                ref_year = ref.get("publication_year")

                if not ref_id or not ref_year:
                    continue

                # 年份合理性检查
                current_year = datetime.now().year
                if ref_year < 1700 or ref_year > current_year:
                    continue

                citation_records.append({
                    "reference_id": ref_id,
                    "cited_year": ref_year,
                    "citing_year": citing_year,
                    "title": ref.get("title", ref.get("display_name", "Unknown"))
                })

                if ref_id not in reference_info:
                    reference_info[ref_id] = {
                        "year": ref_year,
                        "title": ref.get("title", ref.get("display_name", "Unknown")),
                        "cited_by_count": ref.get("cited_by_count", 0)
                    }

        if not citation_records:
            raise ValueError("未找到有效的引用记录")

        if self.verbose:
            print(f"[RPYS] 提取了 {len(citation_records)} 条引用记录")

        df_citations = pd.DataFrame(citation_records)

        # ============ 2. 按年份聚合 ============
        year_citations = (
            df_citations
            .groupby("cited_year")
            .size()
            .reset_index(name="count")
            .rename(columns={"cited_year": "year"})
        )

        # ============ 3. 补全年份序列 ============
        min_year = year_citations["year"].min()
        max_year = year_citations["year"].max()

        if timespan:
            min_year = max(min_year, timespan[0])
            max_year = min(max_year, timespan[1])

        full_years = pd.DataFrame({"year": range(min_year, max_year + 1)})
        rpys_df = full_years.merge(year_citations, on="year", how="left").fillna(0)
        rpys_df["count"] = rpys_df["count"].astype(int)

        # ============ 4. 计算5年中位数和偏差 ============
        years = rpys_df["year"].values
        counts = rpys_df["count"].values
        n = len(years)

        # 计算中位数
        median_5yr = np.zeros(n)
        if median_window == "centered":
            for i in range(n):
                start = max(0, i - 2)
                end = min(n, i + 3)
                median_5yr[i] = np.median(counts[start:end])
        elif median_window == "backward":
            for i in range(n):
                start = max(0, i - 4)
                median_5yr[i] = np.median(counts[start:i+1])
        else:
            raise ValueError(f"不支持的median_window: {median_window}")

        rpys_df["median_5yr"] = median_5yr
        rpys_df["deviation"] = counts - median_5yr

        # ============ 5. 识别峰值年份 ============
        threshold = rpys_df["deviation"].mean() + rpys_df["deviation"].std()
        rpys_df["is_peak"] = rpys_df["deviation"] > threshold

        peak_years_data = []
        for _, row in rpys_df[rpys_df["is_peak"]].iterrows():
            year = int(row["year"])
            year_refs = df_citations[df_citations["cited_year"] == year]

            # 获取该年份的top引用文献
            top_refs = (
                year_refs
                .groupby("reference_id")
                .agg({
                    "reference_id": "count",
                    "title": "first"
                })
                .rename(columns={"reference_id": "frequency"})
                .sort_values("frequency", ascending=False)
                .head(top_refs_per_year)
                .reset_index()
            )

            # 添加被引次数信息
            top_refs_with_citations = []
            for _, ref_row in top_refs.iterrows():
                ref_id = ref_row["reference_id"]
                ref_info = reference_info.get(ref_id, {})
                top_refs_with_citations.append({
                    "reference_id": ref_id,
                    "title": ref_row["title"],
                    "frequency": ref_row["frequency"],
                    "cited_by_count": ref_info.get("cited_by_count", 0)
                })

            peak_years_data.append({
                "year": year,
                "count": int(row["count"]),
                "deviation_rate": float(row["deviation"] / row["count"]) if row["count"] > 0 else 0,
                "top_references": top_refs_with_citations
            })

        if self.verbose:
            print(f"[RPYS] 识别出 {len(peak_years_data)} 个峰值年份")

        # ============ 6. 引用文献分类（可选）============
        reference_types = None
        if classify_refs:
            if self.verbose:
                print(f"\n[RPYS] 开始引用文献四种类型分类...")

            ref_classification = self.classify_references(works)

            if not ref_classification.empty:
                # 按类型分组
                reference_types = {
                    'hot_papers': ref_classification[
                        ref_classification['types'].apply(lambda x: 'Hot Paper' in x)
                    ].sort_values('total_citations', ascending=False).to_dict('records'),

                    'sleeping_beauties': ref_classification[
                        ref_classification['types'].apply(lambda x: 'Sleeping Beauty' in x)
                    ].sort_values('total_citations', ascending=False).to_dict('records'),

                    'life_cycles': ref_classification[
                        ref_classification['types'].apply(lambda x: 'Life Cycle' in x)
                    ].sort_values('total_citations', ascending=False).to_dict('records'),

                    'constant_performers': ref_classification[
                        ref_classification['types'].apply(lambda x: 'Constant Performer' in x)
                    ].sort_values('total_citations', ascending=False).to_dict('records'),

                    'all_classified': ref_classification.to_dict('records')
                }

                if self.verbose:
                    print(f"[RPYS] ✅ 引用文献分类完成")
                    print(f"  - Hot Papers: {len(reference_types['hot_papers'])}")
                    print(f"  - Sleeping Beauties: {len(reference_types['sleeping_beauties'])}")
                    print(f"  - Life Cycles: {len(reference_types['life_cycles'])}")
                    print(f"  - Constant Performers: {len(reference_types['constant_performers'])}")
            else:
                if self.verbose:
                    print(f"[RPYS] ⚠️  引用文献分类未产生结果")

        # ============ 7. 返回结果 ============
        result = {
            "rpys_data": rpys_df.to_dict("records"),
            "n_works": len(works),
            "n_references": len(reference_info),
            "year_range": (int(min_year), int(max_year)),
            "median_window": median_window,
            "peak_years": peak_years_data,
            "reference_types": reference_types  # 新增：四种类型的引用文献
        }

        if self.verbose:
            print(f"[RPYS] ✅ 分析完成！")

        return result

    def plot(
        self,
        result: Dict,
        figsize: Tuple[int, int] = (14, 7),
        save_path: Optional[str] = None,
        style: str = 'default',
        show_peaks: bool = True,
        **kwargs
    ):
        """
        生成RPYS可视化图表

        Args:
            result: analyze()返回的结果字典
            figsize: 图表大小
            save_path: 保存路径（可选）
            style: 可视化风格 ('default' 或 'pybibx')
            show_peaks: 是否显示峰值标记
            **kwargs: 其他参数传递给具体的绘图方法

        Returns:
            matplotlib.figure.Figure (style='default') 或 None (style='pybibx')
        """
        if style == 'pybibx':
            return self.plot_pybibx_style(result, show_peaks=show_peaks, **kwargs)
        else:
            return self._plot_default(result, figsize, save_path, show_peaks)

    def _plot_default(
        self,
        result: Dict,
        figsize: Tuple[int, int] = (14, 7),
        save_path: Optional[str] = None,
        show_peaks: bool = True
    ) -> plt.Figure:
        """
        默认的 Matplotlib 风格可视化

        Args:
            result: analyze()返回的结果字典
            figsize: 图表大小
            save_path: 保存路径（可选）
            show_peaks: 是否显示峰值标记

        Returns:
            matplotlib.figure.Figure
        """
        rpys_df = pd.DataFrame(result["rpys_data"])

        fig, ax = plt.subplots(figsize=figsize)

        years = rpys_df["year"].values
        counts = rpys_df["count"].values
        median = rpys_df["median_5yr"].values

        # 绘制引用次数线
        ax.plot(years, counts, color="steelblue", linewidth=1.5, label="Citation Count")

        # 绘制中值线
        ax.plot(years, median, color="red", linewidth=1.5, linestyle="--", label="5-Year Median")

        # 标记峰值年份
        if show_peaks:
            peak_data = rpys_df[rpys_df["is_peak"]]
            if len(peak_data) > 0:
                ax.scatter(peak_data["year"], peak_data["count"],
                          s=100, color="red", marker="o", zorder=5, label="Peak Years")

        # 设置标签和标题
        ax.set_xlabel("Publication Year", fontsize=12, fontweight="bold")
        ax.set_ylabel("Number of Citations", fontsize=12, fontweight="bold")
        ax.set_title(
            f"RPYS - Reference Publication Year Spectroscopy\n"
            f"({result['median_window']} median, {result['year_range'][0]}-{result['year_range'][1]})",
            fontsize=14, fontweight="bold"
        )

        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            if self.verbose:
                print(f"[RPYS] 图表已保存到: {save_path}")

        return fig

    def plot_pybibx_style(
        self,
        result: Dict,
        view: str = 'browser',
        show_peaks: bool = True,
        peaks_only: bool = False,
        save_html: Optional[str] = None
    ):
        """
        使用 PyBibX 风格的交互式可视化（Plotly）

        这个方法借鉴了 PyBibX 的 plot_rpys 方法，提供更强的交互性和更现代的视觉效果。

        Args:
            result: analyze()返回的结果字典（或直接传入 works 数据）
            view: 'browser' 在浏览器中打开，'notebook' 在 notebook 中显示
            show_peaks: 是否显示峰值标记
            peaks_only: 是否只显示峰值年份
            save_html: 保存为 HTML 文件的路径（可选）

        Features:
            - 交互式 Plotly 图表
            - 时间范围选择器
            - 范围滑块
            - 红色高亮峰值年份
            - 平滑曲线和峰值标记

        Example:
            >>> rpys = RPYS()
            >>> works = await rpys.prepare_data(keywords='scientometrics', limit=100)
            >>> result = rpys.analyze(works)
            >>> rpys.plot(result, style='pybibx')  # 使用 PyBibX 风格
        """
        if self.verbose:
            print(f"\n[RPYS] 绘制 PyBibX 风格的 RPYS 图...")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'
        elif view == 'notebook':
            pio.renderers.default = 'notebook'

        # 支持两种输入：result字典 或 works数据
        if isinstance(result, dict) and 'rpys_data' in result:
            # 从 analyze() 的结果中提取数据
            rpys_df = pd.DataFrame(result["rpys_data"])
            years = rpys_df["year"].values
            counts = rpys_df["count"].values

            # 重新计算平滑值和峰值（使用 PyBibX 的方法）
            smoothed_counts = gaussian_filter1d(counts, sigma=1)
            peaks, properties = find_peaks(smoothed_counts, height=1)
            peak_years = years[peaks]
            peak_values = smoothed_counts[peaks]

        elif isinstance(result, list):
            # 直接从 works 数据中提取引用年份
            if self.verbose:
                print(f"[RPYS] 从 works 数据中提取引用年份...")

            reference_years = []
            for work in result:
                for ref in work.get('referenced_works_details', []):
                    year = ref.get('publication_year')
                    if year and isinstance(year, int) and 1700 <= year <= 2025:
                        reference_years.append(year)

            if not reference_years:
                print("[RPYS] ⚠️  没有有效的引用年份数据")
                return None

            # 统计每年的引用次数
            year_counts = Counter(reference_years)
            years = np.array(sorted(year_counts.keys()))
            counts = np.array([year_counts[year] for year in years])

            # 高斯平滑
            smoothed_counts = gaussian_filter1d(counts, sigma=1)

            # 峰值检测
            peaks, properties = find_peaks(smoothed_counts, height=1)
            peak_years = years[peaks]
            peak_values = smoothed_counts[peaks]

        else:
            raise ValueError("result 必须是 analyze() 返回的字典或 works 数据列表")

        if self.verbose:
            print(f"[RPYS] 年份范围: {years.min()} - {years.max()}")
            print(f"[RPYS] 检测到 {len(peak_years)} 个峰值年份")
            if len(peak_years) > 0:
                print(f"[RPYS] 峰值年份: {', '.join(map(str, peak_years[:10]))}{' ...' if len(peak_years) > 10 else ''}")

        # 配色（PyBibX 风格）
        bar_colors = [
            'rgba(240, 100, 100, 0.5)' if year in peak_years
            else 'rgba(100, 150, 240, 0.5)'
            for year in years
        ]

        # 如果只显示峰值年份
        if peaks_only and len(peak_years) > 0:
            mask = np.isin(years, peak_years)
            years = years[mask]
            counts = counts[mask]
            smoothed_counts = smoothed_counts[mask]
            bar_colors = [c for i, c in enumerate(bar_colors) if mask[i]]

        # 创建图表
        fig = go.Figure()

        # 添加柱状图（原始引用次数）
        fig.add_trace(go.Bar(
            x=years.tolist(),
            y=counts.tolist(),
            name='Raw Citation Counts',
            marker_color=bar_colors,
            hovertemplate='<b>Year:</b> %{x}<br><b>Count:</b> %{y}<extra></extra>'
        ))

        # 添加平滑曲线
        fig.add_trace(go.Scatter(
            x=years.tolist(),
            y=smoothed_counts.tolist(),
            mode='lines+markers',
            name='Smoothed Citation Counts',
            line=dict(color='black', width=2),
            marker=dict(size=4),
            hovertemplate='<b>Year:</b> %{x}<br><b>Smoothed:</b> %{y:.2f}<extra></extra>'
        ))

        # 添加峰值标记
        if show_peaks and len(peak_years) > 0:
            fig.add_trace(go.Scatter(
                x=peak_years.tolist(),
                y=peak_values.tolist(),
                mode='markers+text',
                marker=dict(
                    color='red',
                    size=12,
                    symbol='circle',
                    line=dict(width=2, color='darkred')
                ),
                name='Peaks',
                text=[str(int(y)) for y in peak_years],
                textposition='top center',
                textfont=dict(size=10, color='red'),
                hovertemplate='<b>Peak Year:</b> %{x}<br><b>Value:</b> %{y:.2f}<extra></extra>'
            ))

        # 更新布局（PyBibX 风格）
        fig.update_layout(
            title={
                'text': 'Reference Publication Year Spectroscopy (RPYS) - PyBibX Style',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'weight': 'bold'}
            },
            xaxis_title='Publication Year',
            yaxis_title='Citation Counts',
            showlegend=True,
            xaxis=dict(
                rangeselector=dict(
                    buttons=list([
                        dict(count=10, label='10y', step='year', stepmode='backward'),
                        dict(count=20, label='20y', step='year', stepmode='backward'),
                        dict(count=50, label='50y', step='year', stepmode='backward'),
                        dict(step='all', label='All')
                    ])
                ),
                rangeslider=dict(visible=True),
                type='linear'
            ),
            height=700,
            template='plotly_white',
            hovermode='x unified'
        )

        # 保存为 HTML
        if save_html:
            fig.write_html(save_html)
            if self.verbose:
                print(f"[RPYS] ✅ HTML 已保存到: {save_html}")

        # 显示图表
        if self.verbose:
            print(f"[RPYS] ✅ RPYS 图表已生成")

        fig.show()

        return fig

    def clear_cache(self, data_file: Optional[str] = None):
        """
        清除缓存文件

        Args:
            data_file: 要删除的数据文件路径（None表示删除所有缓存）
        """
        if data_file:
            data_path = Path(data_file)
            if data_path.exists():
                data_path.unlink()
                if self.verbose:
                    print(f"[RPYS] ✅ 已删除: {data_path}")
        else:
            # 删除所有 rpys_data_*.json 文件
            if self.cache_dir.exists():
                for f in self.cache_dir.glob("rpys_data_*.json"):
                    f.unlink()
                    if self.verbose:
                        print(f"[RPYS] ✅ 已删除: {f}")


# 兼容旧版本的函数接口
def rpys_analysis(
    works: List[Dict],
    timespan: Optional[Tuple[int, int]] = None,
    median_window: str = "centered",
    top_refs_per_year: int = 3,
    verbose: bool = True
) -> Dict:
    """
    执行RPYS分析（兼容旧版本的函数接口）

    推荐使用新的RPYS类接口，提供更好的功能和灵活性。

    Args:
        works: 论文数据列表（必须包含referenced_works_details）
        timespan: 分析的年份范围
        median_window: 中位数窗口类型
        top_refs_per_year: 每年显示的top引用文献数量
        verbose: 是否打印详细信息

    Returns:
        分析结果字典
    """
    rpys = RPYS(verbose=verbose)
    result = rpys.analyze(
        works=works,
        timespan=timespan,
        median_window=median_window,
        top_refs_per_year=top_refs_per_year
    )

    # 生成图表
    result["figure"] = rpys.plot(result)

    return result


if __name__ == "__main__":
    print("RPYS模块已加载")
    print("使用示例：")
    print("  rpys = RPYS()")
    print("  works = await rpys.prepare_data(keywords='scientometrics', limit=100)")
    print("  result = rpys.analyze(works)")
    print("  rpys.plot(result)")
