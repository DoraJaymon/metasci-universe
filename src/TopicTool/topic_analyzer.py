"""
TopicAnalyzer - 主题分析类

提供主题演化分析和可视化功能，借鉴 PyBibX 的可视化风格
"""

from typing import List, Dict, Optional, Tuple
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio


class TopicAnalyzer:
    """
    主题分析器

    提供基于 OpenAlex topics 的主题演化分析和可视化功能

    Features:
        - 主题演化堆叠面积图（streamgraph）
        - 主题频率分布柱状图
        - 支持 PyBibX 风格的可视化

    Example:
        >>> analyzer = TopicAnalyzer()
        >>> analyzer.load_data(works)
        >>> analyzer.plot_evolution_complement(topn=10)
    """

    def __init__(self, verbose: bool = True):
        """
        初始化主题分析器

        Args:
            verbose: 是否打印详细信息
        """
        self.verbose = verbose
        self.works = None
        self.year_topics = {}  # {year: [topic1, topic2, ...]}
        self.topic_counts = None
        self.color_palette = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
            '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
        ]

    def load_data(self, works: List[Dict]) -> 'TopicAnalyzer':
        """
        加载 OpenAlex 数据

        Args:
            works: OpenAlex 论文数据列表

        Returns:
            self (支持链式调用)
        """
        self.works = works

        if self.verbose:
            print(f"[TopicAnalyzer] 加载了 {len(works)} 篇论文")

        # 提取主题和年份信息
        self._extract_topics()

        return self

    def _extract_topics(self):
        """从 works 数据中提取主题和年份信息"""
        all_topics = []
        self.year_topics = {}

        for work in self.works:
            year = work.get('publication_year')
            topics = work.get('topics', [])

            if year and topics:
                if year not in self.year_topics:
                    self.year_topics[year] = []

                for topic in topics:
                    topic_name = topic.get('name')
                    if topic_name:
                        all_topics.append(topic_name)
                        self.year_topics[year].append(topic_name)

        # 统计主题频率
        self.topic_counts = Counter(all_topics)

        if self.verbose:
            print(f"[TopicAnalyzer] 提取了 {len(self.topic_counts)} 个不同的主题")
            years = sorted(self.year_topics.keys())
            if years:
                print(f"[TopicAnalyzer] 年份范围: {min(years)} - {max(years)}")

    def get_top_topics(self, topn: int = 10) -> List[Tuple[str, int]]:
        """
        获取最常见的主题

        Args:
            topn: 返回前 N 个主题

        Returns:
            [(topic_name, count), ...] 列表
        """
        if self.topic_counts is None:
            raise ValueError("请先调用 load_data() 加载数据")

        return self.topic_counts.most_common(topn)

    def plot_evolution_complement(
        self,
        topn: int = 10,
        custom_topics: Optional[List[str]] = None,
        view: str = 'browser',
        save_html: Optional[str] = None,
        title: Optional[str] = None
    ):
        """
        绘制主题演化堆叠面积图（streamgraph）

        借鉴 PyBibX 的 plot_evolution_year_complement 方法，
        使用 Plotly 创建交互式堆叠面积图，展示主题随时间的演化趋势。

        Args:
            topn: 显示前 N 个最常见的主题（如果不指定 custom_topics）
            custom_topics: 自定义要显示的主题列表
            view: 'browser' 在浏览器中打开，'notebook' 在 notebook 中显示
            save_html: 保存为 HTML 文件的路径（可选）
            title: 图表标题（可选）

        Features:
            - 堆叠面积图（streamgraph）
            - 每个主题使用不同颜色
            - 交互式悬停显示详细信息
            - 显示明确的主题名称（不是 topic_1）

        Example:
            >>> analyzer = TopicAnalyzer()
            >>> analyzer.load_data(works)
            >>> analyzer.plot_evolution_complement(topn=10)
        """
        if self.year_topics is None or len(self.year_topics) == 0:
            raise ValueError("没有主题数据，请先调用 load_data()")

        if self.verbose:
            print(f"\n[TopicAnalyzer] 绘制主题演化图...")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'
        elif view == 'notebook':
            pio.renderers.default = 'notebook'

        # 构建年份-主题频率矩阵
        years = sorted(self.year_topics.keys())
        year_topic_freq = {}

        for year in years:
            topics_in_year = self.year_topics[year]
            topic_freq = Counter(topics_in_year)
            year_topic_freq[year] = topic_freq

        # 创建 DataFrame
        df = pd.DataFrame(year_topic_freq).fillna(0).T

        # 选择要显示的主题
        if custom_topics:
            # 使用自定义主题列表
            selected_topics = [t for t in custom_topics if t in df.columns]
            if len(selected_topics) < len(custom_topics):
                missing = set(custom_topics) - set(selected_topics)
                print(f"[TopicAnalyzer] ⚠️  以下主题不存在: {missing}")
        else:
            # 使用 top N 主题
            total_frequencies = df.sum(axis=0).sort_values(ascending=False)
            selected_topics = total_frequencies.index[:topn].tolist()

        df = df[selected_topics]

        if self.verbose:
            print(f"[TopicAnalyzer] 显示 {len(selected_topics)} 个主题")
            print(f"[TopicAnalyzer] 年份数: {len(years)}")

        # 创建图表
        fig = go.Figure()

        # 添加每个主题的面积图
        for idx, topic in enumerate(df.columns):
            color = self.color_palette[idx % len(self.color_palette)]

            fig.add_trace(go.Scatter(
                x=df.index,
                y=df[topic],
                mode='lines',
                stackgroup='one',  # 堆叠面积图
                name=topic,  # 使用实际的主题名称，不是 topic_1
                line=dict(width=0.5, color=color),
                fillcolor=color,
                hovertemplate=(
                    f'<b>{topic}</b><br>'
                    'Year: %{x}<br>'
                    'Frequency: %{y}<br>'
                    '<extra></extra>'
                )
            ))

        # 更新布局
        default_title = 'Topic Evolution Over Time'
        fig.update_layout(
            title={
                'text': title or default_title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16}
            },
            xaxis=dict(
                title='Year',
                tickmode='array',
                tickvals=list(df.index),
                ticktext=list(df.index),
                tickangle=-45,
                automargin=True
            ),
            yaxis=dict(
                title='Frequency'
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                title='Topics',
                orientation='v',
                yanchor='top',
                y=1,
                xanchor='left',
                x=1.02
            ),
            height=600,
            template='plotly_white'
        )

        # 保存为 HTML
        if save_html:
            fig.write_html(save_html)
            if self.verbose:
                print(f"[TopicAnalyzer] ✅ HTML 已保存到: {save_html}")

        # 显示图表
        if self.verbose:
            print(f"[TopicAnalyzer] ✅ 主题演化图已生成")

        fig.show()

        return fig

    def plot_top_topics(
        self,
        topn: int = 20,
        view: str = 'browser',
        save_html: Optional[str] = None,
        title: Optional[str] = None
    ):
        """
        绘制主题频率分布柱状图

        借鉴 PyBibX 的 get_top_ngrams 风格，使用水平柱状图展示最常见的主题

        Args:
            topn: 显示前 N 个主题
            view: 'browser' 或 'notebook'
            save_html: 保存为 HTML 文件的路径（可选）
            title: 图表标题（可选）

        Returns:
            plotly Figure 对象
        """
        if self.topic_counts is None:
            raise ValueError("请先调用 load_data() 加载数据")

        if self.verbose:
            print(f"\n[TopicAnalyzer] 绘制主题频率分布...")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'
        elif view == 'notebook':
            pio.renderers.default = 'notebook'

        # 获取 top N 主题
        top_topics = self.topic_counts.most_common(topn)
        topics, counts = zip(*top_topics)

        # 创建水平柱状图
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=counts,
            y=topics,
            orientation='h',
            marker=dict(
                color=counts,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title='Frequency')
            ),
            text=counts,
            textposition='outside',
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Frequency: %{x}<br>'
                '<extra></extra>'
            )
        ))

        # 更新布局
        default_title = f'Top {topn} Topics Distribution'
        fig.update_layout(
            title={
                'text': title or default_title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16}
            },
            xaxis=dict(title='Frequency'),
            yaxis=dict(title='Topics', autorange='reversed'),  # 从上到下排序
            height=max(400, topn * 25),  # 动态调整高度
            template='plotly_white',
            showlegend=False
        )

        # 保存为 HTML
        if save_html:
            fig.write_html(save_html)
            if self.verbose:
                print(f"[TopicAnalyzer] ✅ HTML 已保存到: {save_html}")

        # 显示图表
        if self.verbose:
            print(f"[TopicAnalyzer] ✅ 主题分布图已生成")

        fig.show()

        return fig

    def get_topic_evolution_data(
        self,
        topn: int = 10,
        custom_topics: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """
        获取主题演化数据（DataFrame 格式）

        Args:
            topn: 前 N 个主题
            custom_topics: 自定义主题列表

        Returns:
            DataFrame，行为年份，列为主题名称，值为频率
        """
        if self.year_topics is None:
            raise ValueError("请先调用 load_data() 加载数据")

        years = sorted(self.year_topics.keys())
        year_topic_freq = {}

        for year in years:
            topics_in_year = self.year_topics[year]
            topic_freq = Counter(topics_in_year)
            year_topic_freq[year] = topic_freq

        # 创建 DataFrame
        df = pd.DataFrame(year_topic_freq).fillna(0).T

        # 选择主题
        if custom_topics:
            selected_topics = [t for t in custom_topics if t in df.columns]
        else:
            total_frequencies = df.sum(axis=0).sort_values(ascending=False)
            selected_topics = total_frequencies.index[:topn].tolist()

        return df[selected_topics]

    def print_summary(self):
        """打印主题分析摘要"""
        if self.works is None:
            print("[TopicAnalyzer] 尚未加载数据")
            return

        print("\n" + "="*60)
        print("主题分析摘要")
        print("="*60)

        print(f"\n数据统计:")
        print(f"  - 论文数量: {len(self.works)}")
        print(f"  - 不同主题数: {len(self.topic_counts)}")

        if self.year_topics:
            years = sorted(self.year_topics.keys())
            print(f"  - 年份范围: {min(years)} - {max(years)}")
            print(f"  - 年份数: {len(years)}")

        print(f"\n最常见的 10 个主题:")
        for i, (topic, count) in enumerate(self.topic_counts.most_common(10), 1):
            print(f"  {i:2d}. {topic}: {count}")

        print("\n" + "="*60)


if __name__ == "__main__":
    print("TopicAnalyzer 模块已加载")
    print("使用示例：")
    print("  from TopicTool import TopicAnalyzer")
    print("  analyzer = TopicAnalyzer()")
    print("  analyzer.load_data(works)")
    print("  analyzer.plot_evolution_complement(topn=10)")
