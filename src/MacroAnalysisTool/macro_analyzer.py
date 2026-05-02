"""
MacroAnalyzer - 宏观分析工具

提供国家和机构生产力分析功能，借鉴 PyBibX 的可视化风格
"""

from typing import List, Dict, Optional, Tuple
from collections import Counter, defaultdict
from pathlib import Path
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import psycopg2
import json
import sys
import pycountry

# 导入数据库配置
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

try:
    from config.db_config import DB_CONFIG
except ImportError:
    DB_CONFIG = None


def _db_config_from_env() -> Optional[Dict]:
    """Build DB config from environment variables when available."""
    dsn = os.getenv("METASCI_DB_DSN") or os.getenv("DEEPALEX_DB_DSN") or os.getenv("DATABASE_URL")
    if dsn:
        return {"dsn": dsn}

    host = os.getenv("METASCI_DB_HOST") or os.getenv("DEEPALEX_DB_HOST")
    database = os.getenv("METASCI_DB_NAME") or os.getenv("DEEPALEX_DB_NAME")
    user = os.getenv("METASCI_DB_USER") or os.getenv("DEEPALEX_DB_USER")
    password = os.getenv("METASCI_DB_PASSWORD") or os.getenv("DEEPALEX_DB_PASSWORD")

    if not all([host, database, user, password]):
        return None

    return {
        "host": host,
        "port": int(os.getenv("METASCI_DB_PORT") or os.getenv("DEEPALEX_DB_PORT") or "5432"),
        "database": database,
        "user": user,
        "password": password,
    }


class MacroAnalyzer:
    """
    宏观分析器

    提供基于 OpenAlex 数据的国家和机构生产力分析功能

    Features:
        - 国家生产力交互式地图（动画choropleth）
        - 机构生产力时间线图
        - 支持 PyBibX 风格的可视化

    Example:
        >>> analyzer = MacroAnalyzer()
        >>> analyzer.load_data(works)
        >>> analyzer.countries_productivity(view='browser')
    """

    def __init__(self, verbose: bool = True, db_config: Optional[Dict] = None):
        """
        初始化宏观分析器

        Args:
            verbose: 是否打印详细信息
            db_config: 数据库配置（用于获取机构信息）
                如果不提供，将使用 config/db_config.py 中的配置
        """
        self.verbose = verbose
        self.works = None
        self.author_institutions = {}  # {author_id: {institution, country}}
        self.country_year_counts = {}  # {year: {country: count}}
        self.institution_year_counts = {}  # {year: {institution: count}}

        # 数据库配置：传入参数 > 环境变量 > config/db_config.py。
        self.db_config = db_config or _db_config_from_env() or DB_CONFIG

    def load_data(self, works: List[Dict], enrich_institutions: bool = False) -> 'MacroAnalyzer':
        """
        加载 OpenAlex 数据

        Args:
            works: OpenAlex 论文数据列表
            enrich_institutions: 是否从数据库获取机构信息（针对简化的数据）

        Returns:
            self (支持链式调用)
        """
        self.works = works

        if self.verbose:
            print(f"[MacroAnalyzer] 加载了 {len(works)} 篇论文")

        # 提取作者和机构信息
        self._extract_author_institutions(enrich_institutions)

        # 构建年份-国家/机构统计
        self._build_statistics()

        return self

    def _extract_author_institutions(self, enrich: bool = False):
        """从 works 数据中提取作者和机构信息"""
        author_ids = set()

        # 首先尝试从现有数据中提取
        for work in self.works:
            # 尝试从 _raw.authorships 中提取（完整数据）
            if '_raw' in work and 'authorships' in work.get('_raw', {}):
                authorships = work['_raw']['authorships']
                for authorship in authorships:
                    author = authorship.get('author', {})
                    author_id = author.get('id', '')
                    institutions = authorship.get('institutions', [])

                    if author_id and institutions:
                        # 使用第一个机构
                        inst = institutions[0]
                        self.author_institutions[author_id] = {
                            'institution': inst.get('display_name', 'Unknown'),
                            'institution_id': inst.get('id', ''),
                            'country': inst.get('country_code', 'Unknown')
                        }

            # 如果没有完整数据，收集作者 ID 用于后续查询
            elif 'authors' in work:
                for author in work['authors']:
                    author_id = author.get('id', '')
                    if author_id:
                        author_ids.add(author_id)

        if self.verbose:
            print(f"[MacroAnalyzer] 从现有数据中提取了 {len(self.author_institutions)} 个作者-机构关系")

        # 如果需要且有缺失的作者信息，从数据库获取
        if enrich and author_ids - set(self.author_institutions.keys()):
            missing_ids = author_ids - set(self.author_institutions.keys())
            if self.verbose:
                print(f"[MacroAnalyzer] 从数据库查询 {len(missing_ids)} 个作者的机构信息...")
            self._fetch_author_institutions_from_db(missing_ids)

    def _fetch_author_institutions_from_db(self, author_ids: set):
        """从数据库获取作者机构信息"""
        if not author_ids:
            return

        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()

            # 批量查询作者的最新机构信息
            author_ids_list = list(author_ids)[:1000]  # 限制查询数量

            query = """
            SELECT DISTINCT ON (a.author_id)
                a.author_id,
                i.display_name as institution_name,
                i.institution_id,
                i.country_code
            FROM authors a
            LEFT JOIN institutions i ON a.institution_id = i.institution_id
            WHERE a.author_id = ANY(%s)
            ORDER BY a.author_id, a.work_id DESC
            """

            cur.execute(query, (author_ids_list,))
            results = cur.fetchall()

            for row in results:
                author_id, inst_name, inst_id, country = row
                self.author_institutions[author_id] = {
                    'institution': inst_name or 'Unknown',
                    'institution_id': inst_id or '',
                    'country': country or 'Unknown'
                }

            if self.verbose:
                print(f"[MacroAnalyzer] 从数据库获取了 {len(results)} 个作者的机构信息")

            cur.close()
            conn.close()

        except Exception as e:
            if self.verbose:
                print(f"[MacroAnalyzer] 数据库查询失败: {e}")

    def _build_statistics(self):
        """构建年份-国家/机构统计"""
        country_year = defaultdict(lambda: defaultdict(int))
        institution_year = defaultdict(lambda: defaultdict(int))

        for work in self.works:
            year = work.get('publication_year')
            if not year:
                continue

            # 优先使用 _raw.authorships（如果存在），否则回退到 authors
            # _raw.authorships 包含完整的作者信息和机构信息
            authorships = work.get('_raw', {}).get('authorships', [])

            if authorships:
                # 使用 _raw.authorships 中的作者ID
                authors_data = [
                    {'id': a.get('author', {}).get('id', '')}
                    for a in authorships
                ]
            else:
                # 回退到 work.authors（旧数据格式）
                authors_data = work.get('authors', [])

            countries_in_work = set()
            institutions_in_work = set()

            for author in authors_data:
                author_id = author.get('id', '')

                # 标准化 author_id 格式（支持短格式和长格式）
                # 短格式: 'A5026129552'
                # 长格式: 'https://openalex.org/A5026129552'
                normalized_id = author_id
                if author_id and not author_id.startswith('https://'):
                    # 如果是短格式，转换为长格式
                    normalized_id = f'https://openalex.org/{author_id}'

                # 尝试两种格式
                info = self.author_institutions.get(normalized_id) or \
                       self.author_institutions.get(author_id)

                if info:
                    country = info.get('country', 'Unknown')
                    institution = info.get('institution', 'Unknown')

                    if country and country != 'Unknown' and country != '':
                        countries_in_work.add(country)
                    if institution and institution != 'Unknown' and institution != '':
                        institutions_in_work.add(institution)

            # 统计（每篇论文的每个国家/机构计数一次）
            for country in countries_in_work:
                country_year[year][country] += 1

            for institution in institutions_in_work:
                institution_year[year][institution] += 1

        self.country_year_counts = dict(country_year)
        self.institution_year_counts = dict(institution_year)

        if self.verbose:
            total_countries = len(set(c for year_data in self.country_year_counts.values() for c in year_data.keys()))
            total_institutions = len(set(i for year_data in self.institution_year_counts.values() for i in year_data.keys()))
            print(f"[MacroAnalyzer] 识别了 {total_countries} 个国家, {total_institutions} 个机构")

    def countries_productivity(
        self,
        view: str = 'browser',
        save_html: Optional[str] = None,
        title: Optional[str] = None,
        colorscale: str = 'Viridis'
    ):
        """
        绘制国家生产力交互式地图（动画 choropleth）

        借鉴 PyBibX 的 countries_productivity 方法，
        使用 Plotly 创建交互式世界地图，展示各国随时间的生产力变化。

        Args:
            view: 'browser' 在浏览器中打开，'notebook' 在 notebook 中显示
            save_html: 保存为 HTML 文件的路径（可选）
            title: 图表标题（可选）
            colorscale: 颜色方案 ('Viridis', 'Blues', 'Reds', 'Sunset', etc.)

        Features:
            - 动画 choropleth 地图
            - Play/Pause 按钮
            - 年份滑块
            - 交互式悬停显示详细信息

        Returns:
            plotly Figure 对象

        Example:
            >>> analyzer = MacroAnalyzer()
            >>> analyzer.load_data(works, enrich_institutions=True)
            >>> analyzer.countries_productivity(view='browser')
        """
        if not self.country_year_counts:
            raise ValueError("没有国家数据，请先调用 load_data() 并设置 enrich_institutions=True")

        if self.verbose:
            print(f"\n[MacroAnalyzer] 绘制国家生产力地图...")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'
        elif view == 'notebook':
            pio.renderers.default = 'notebook'

        # 准备数据
        years = sorted(self.country_year_counts.keys())

        # 构建 DataFrame
        data_frames = []
        for year in years:
            year_data = self.country_year_counts[year]
            for country, count in year_data.items():
                data_frames.append({
                    'year': year,
                    'country': country,
                    'count': count
                })

        df = pd.DataFrame(data_frames)

        if len(df) == 0:
            if self.verbose:
                print("[MacroAnalyzer] ⚠️  没有可用的国家数据")
            return None

        # 转换国家代码：ISO-2 (US, CN) → ISO-3 (USA, CHN)
        def convert_to_iso3(iso2_code):
            """将 ISO-2 国家代码转换为 ISO-3"""
            try:
                country = pycountry.countries.get(alpha_2=iso2_code)
                return country.alpha_3 if country else iso2_code
            except:
                return iso2_code  # 如果转换失败，保持原样

        df['country_iso3'] = df['country'].apply(convert_to_iso3)
        df['country_name'] = df['country']  # 保留原始代码用于显示

        if self.verbose:
            print(f"[MacroAnalyzer] 年份范围: {min(years)} - {max(years)}")
            print(f"[MacroAnalyzer] 数据点数: {len(df)}")

        # 创建动画地图
        fig = go.Figure()

        # 为每年添加一个 frame
        frames = []
        for year in years:
            year_df = df[df['year'] == year]

            frame = go.Frame(
                data=[go.Choropleth(
                    locations=year_df['country_iso3'],  # 使用转换后的 ISO-3 代码
                    z=year_df['count'],
                    locationmode='ISO-3',  # Plotly 要求 ISO-3 格式 (USA, CHN, GBR)
                    colorscale=colorscale,
                    colorbar_title='Publications',
                    text=year_df['country_name'],  # 显示原始代码
                    hovertemplate='<b>%{text}</b><br>Publications: %{z}<extra></extra>'
                )],
                name=str(year)
            )
            frames.append(frame)

        # 初始帧（第一年）
        first_year_df = df[df['year'] == years[0]]
        fig.add_trace(go.Choropleth(
            locations=first_year_df['country_iso3'],  # 使用转换后的 ISO-3 代码
            z=first_year_df['count'],
            locationmode='ISO-3',  # Plotly 要求 ISO-3 格式 (USA, CHN, GBR)
            colorscale=colorscale,
            colorbar_title='Publications',
            text=first_year_df['country_name'],  # 显示原始代码
            hovertemplate='<b>%{text}</b><br>Publications: %{z}<extra></extra>'
        ))

        fig.frames = frames

        # 更新布局
        default_title = 'Country Productivity Over Time'
        fig.update_layout(
            title={
                'text': title or default_title,
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18}
            },
            geo=dict(
                showframe=False,
                showcoastlines=True,
                projection_type='equirectangular'
            ),
            updatemenus=[
                dict(
                    type='buttons',
                    showactive=False,
                    buttons=[
                        dict(label='Play',
                             method='animate',
                             args=[None, dict(frame=dict(duration=500, redraw=True),
                                            fromcurrent=True,
                                            mode='immediate')]),
                        dict(label='Pause',
                             method='animate',
                             args=[[None], dict(frame=dict(duration=0, redraw=False),
                                              mode='immediate',
                                              transition=dict(duration=0))])
                    ],
                    x=0.1,
                    xanchor='left',
                    y=0,
                    yanchor='top'
                )
            ],
            sliders=[
                dict(
                    active=0,
                    yanchor='top',
                    y=0.05,
                    xanchor='left',
                    x=0.1,
                    currentvalue=dict(
                        prefix='Year: ',
                        visible=True,
                        xanchor='right'
                    ),
                    pad=dict(b=10, t=50),
                    len=0.9,
                    steps=[
                        dict(
                            args=[[str(year)], dict(
                                frame=dict(duration=300, redraw=True),
                                mode='immediate',
                                transition=dict(duration=300)
                            )],
                            label=str(year),
                            method='animate'
                        ) for year in years
                    ]
                )
            ]
        )

        # 保存为 HTML
        if save_html:
            fig.write_html(save_html)
            if self.verbose:
                print(f"[MacroAnalyzer] ✅ HTML 已保存到: {save_html}")

        # 显示图表
        if self.verbose:
            print(f"[MacroAnalyzer] ✅ 国家生产力地图已生成")

        fig.show()

        return fig

    def institution_productivity(
        self,
        topn: int = 10,
        view: str = 'browser',
        save_html: Optional[str] = None,
        title: Optional[str] = None
    ):
        """
        绘制机构生产力时间线图

        借鉴 PyBibX 的 institution_productivity 方法，
        展示 top N 机构随时间的生产力变化。

        Args:
            topn: 显示前 N 个机构
            view: 'browser' 或 'notebook'
            save_html: 保存为 HTML 文件的路径（可选）
            title: 图表标题（可选）

        Features:
            - 时间线散点图
            - 每个机构使用不同颜色
            - 点之间用线连接
            - 交互式悬停显示详细信息

        Returns:
            plotly Figure 对象

        Example:
            >>> analyzer.institution_productivity(topn=15, view='browser')
        """
        if not self.institution_year_counts:
            raise ValueError("没有机构数据，请先调用 load_data() 并设置 enrich_institutions=True")

        if self.verbose:
            print(f"\n[MacroAnalyzer] 绘制机构生产力时间线...")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'
        elif view == 'notebook':
            pio.renderers.default = 'notebook'

        # 计算每个机构的总产出，选择 top N
        institution_totals = Counter()
        for year_data in self.institution_year_counts.values():
            for inst, count in year_data.items():
                institution_totals[inst] += count

        top_institutions = [inst for inst, _ in institution_totals.most_common(topn)]

        if self.verbose:
            print(f"[MacroAnalyzer] 选择了 Top {topn} 机构")

        # 准备数据
        years = sorted(self.institution_year_counts.keys())

        # 为每个机构创建时间序列
        fig = go.Figure()

        colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
        ]

        for idx, institution in enumerate(top_institutions):
            counts = []
            for year in years:
                count = self.institution_year_counts.get(year, {}).get(institution, 0)
                counts.append(count)

            color = colors[idx % len(colors)]

            # 添加散点和线
            fig.add_trace(go.Scatter(
                x=years,
                y=counts,
                mode='lines+markers',
                name=institution,
                line=dict(color=color, width=2),
                marker=dict(size=8, color=color),
                hovertemplate=(
                    f'<b>{institution}</b><br>'
                    'Year: %{x}<br>'
                    'Publications: %{y}<br>'
                    '<extra></extra>'
                )
            ))

        # 更新布局
        default_title = f'Top {topn} Institutions Productivity Over Time'
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
                tickvals=years,
                ticktext=[str(y) for y in years]
            ),
            yaxis=dict(
                title='Number of Publications'
            ),
            hovermode='x unified',
            showlegend=True,
            legend=dict(
                title='Institutions',
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
                print(f"[MacroAnalyzer] ✅ HTML 已保存到: {save_html}")

        # 显示图表
        if self.verbose:
            print(f"[MacroAnalyzer] ✅ 机构生产力时间线已生成")

        fig.show()

        return fig

    def get_country_statistics(self) -> pd.DataFrame:
        """
        获取国家统计数据

        Returns:
            DataFrame，列为国家，行为年份，值为论文数
        """
        if not self.country_year_counts:
            raise ValueError("请先调用 load_data()")

        years = sorted(self.country_year_counts.keys())
        all_countries = set()
        for year_data in self.country_year_counts.values():
            all_countries.update(year_data.keys())

        data = []
        for year in years:
            row = {'year': year}
            year_data = self.country_year_counts[year]
            for country in all_countries:
                row[country] = year_data.get(country, 0)
            data.append(row)

        return pd.DataFrame(data).set_index('year')

    def get_institution_statistics(self, topn: Optional[int] = None) -> pd.DataFrame:
        """
        获取机构统计数据

        Args:
            topn: 只返回 top N 机构（可选）

        Returns:
            DataFrame，列为机构，行为年份，值为论文数
        """
        if not self.institution_year_counts:
            raise ValueError("请先调用 load_data()")

        # 如果指定 topn，先计算总数
        if topn:
            institution_totals = Counter()
            for year_data in self.institution_year_counts.values():
                for inst, count in year_data.items():
                    institution_totals[inst] += count
            selected_institutions = set(inst for inst, _ in institution_totals.most_common(topn))
        else:
            selected_institutions = set()
            for year_data in self.institution_year_counts.values():
                selected_institutions.update(year_data.keys())

        years = sorted(self.institution_year_counts.keys())

        data = []
        for year in years:
            row = {'year': year}
            year_data = self.institution_year_counts[year]
            for institution in selected_institutions:
                row[institution] = year_data.get(institution, 0)
            data.append(row)

        return pd.DataFrame(data).set_index('year')

    def print_summary(self):
        """打印统计摘要"""
        if self.works is None:
            print("[MacroAnalyzer] 尚未加载数据")
            return

        print("\n" + "="*60)
        print("宏观分析摘要")
        print("="*60)

        print(f"\n数据统计:")
        print(f"  - 论文数量: {len(self.works)}")
        print(f"  - 作者-机构关系数: {len(self.author_institutions)}")

        if self.country_year_counts:
            total_countries = len(set(c for year_data in self.country_year_counts.values() for c in year_data.keys()))
            years = sorted(self.country_year_counts.keys())
            print(f"  - 识别的国家数: {total_countries}")
            print(f"  - 年份范围: {min(years)} - {max(years)}")

            # 统计总论文数（按国家）
            country_totals = Counter()
            for year_data in self.country_year_counts.values():
                for country, count in year_data.items():
                    country_totals[country] += count

            print(f"\n最活跃的 10 个国家:")
            for i, (country, count) in enumerate(country_totals.most_common(10), 1):
                print(f"  {i:2d}. {country}: {count} 篇")

        if self.institution_year_counts:
            total_institutions = len(set(i for year_data in self.institution_year_counts.values() for i in year_data.keys()))
            print(f"  - 识别的机构数: {total_institutions}")

            # 统计总论文数（按机构）
            institution_totals = Counter()
            for year_data in self.institution_year_counts.values():
                for institution, count in year_data.items():
                    institution_totals[institution] += count

            print(f"\n最活跃的 10 个机构:")
            for i, (institution, count) in enumerate(institution_totals.most_common(10), 1):
                # 截断过长的机构名
                inst_name = institution if len(institution) <= 50 else institution[:47] + "..."
                print(f"  {i:2d}. {inst_name}: {count} 篇")

        print("\n" + "="*60)


if __name__ == "__main__":
    print("MacroAnalyzer 模块已加载")
    print("使用示例：")
    print("  from MacroAnalysisTool import MacroAnalyzer")
    print("  analyzer = MacroAnalyzer()")
    print("  analyzer.load_data(works, enrich_institutions=True)")
    print("  analyzer.countries_productivity(view='browser')")
    print("  analyzer.institution_productivity(topn=10)")
