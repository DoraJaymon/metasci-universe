"""
TopicModeling - 基于 BERTopic 的主题建模工具

特性：
- 使用 BERTopic 进行主题建模
- 显示实际主题关键词（而非 "topic_1"）
- 简洁的可视化风格
- 支持 OpenAlex 数据格式
"""

import json
import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Union
from pathlib import Path
import plotly.graph_objects as go
import plotly.io as pio
from datetime import datetime

# BERTopic 相关
from bertopic import BERTopic
from sentence_transformers import SentenceTransformer
from umap import UMAP
from sklearn.feature_extraction.text import CountVectorizer


class TopicModeling:
    """
    主题建模类

    使用 BERTopic 对学术论文进行主题建模和分析
    """

    def __init__(self, verbose: bool = True):
        """
        初始化

        Args:
            verbose: 是否打印详细信息
        """
        self.verbose = verbose
        self.topic_model = None
        self.topics = None
        self.probs = None
        self.topic_info = None
        self.docs = None
        self.original_data = None

    def load_data(self, data_path: str) -> pd.DataFrame:
        """
        加载数据

        Args:
            data_path: JSON 数据文件路径（OpenAlex 格式）

        Returns:
            DataFrame with 'title', 'abstract', 'year', 'id' columns
        """
        if self.verbose:
            print(f"📖 加载数据: {data_path}")

        with open(data_path, 'r', encoding='utf-8') as f:
            works = json.load(f)

        # 提取标题、摘要、年份等信息
        data_list = []
        for work in works:
            # 构建文本（标题 + 摘要倒排索引）
            title = work.get('title', '')

            # 处理 abstract_inverted_index
            abstract = ""
            abstract_inv = work.get('abstract_inverted_index', {})
            if abstract_inv:
                # 将倒排索引转换为文本
                words_positions = []
                for word, positions in abstract_inv.items():
                    for pos in positions:
                        words_positions.append((pos, word))
                # 按位置排序
                words_positions.sort()
                abstract = ' '.join([w for _, w in words_positions])

            # 合并标题和摘要
            text = f"{title}. {abstract}" if abstract else title

            if text.strip():  # 只保留有内容的论文
                data_list.append({
                    'id': work.get('id', ''),
                    'title': title,
                    'abstract': abstract,
                    'text': text,
                    'year': work.get('publication_year'),
                    'cited_by_count': work.get('cited_by_count', 0)
                })

        self.original_data = pd.DataFrame(data_list)

        if self.verbose:
            print(f"✅ 加载了 {len(self.original_data)} 篇论文")
            print(f"   年份范围: {self.original_data['year'].min()} - {self.original_data['year'].max()}")

        return self.original_data

    def fit(
        self,
        texts: Optional[List[str]] = None,
        nr_topics: Optional[int] = None,
        min_topic_size: int = 10,
        embedding_model: str = 'allenai/scibert_scivocab_uncased',
        language: str = 'english',
        calculate_probabilities: bool = True
    ):
        """
        训练主题模型

        Args:
            texts: 文本列表（如果为 None，使用 load_data 加载的数据）
            nr_topics: 主题数量（None 表示自动）
            min_topic_size: 最小主题大小
            embedding_model: 嵌入模型名称
            language: 语言
            calculate_probabilities: 是否计算概率
        """
        if texts is None:
            if self.original_data is None:
                raise ValueError("请先使用 load_data() 加载数据，或提供 texts 参数")
            texts = self.original_data['text'].tolist()

        self.docs = texts

        if self.verbose:
            print(f"\n🎯 开始训练主题模型...")
            print(f"   文本数量: {len(texts)}")
            print(f"   目标主题数: {nr_topics if nr_topics else '自动'}")
            print(f"   最小主题大小: {min_topic_size}")
            print(f"   嵌入模型: {embedding_model}")

        # 配置 UMAP
        umap_model = UMAP(
            n_neighbors=15,
            n_components=5,
            min_dist=0.0,
            metric='cosine',
            random_state=42
        )

        # 配置 CountVectorizer（去除停用词）
        vectorizer_model = CountVectorizer(
            stop_words=language,
            ngram_range=(1, 2),  # 使用 1-2 gram
            min_df=2  # 最少出现 2 次
        )

        # 配置嵌入模型
        sentence_model = SentenceTransformer(embedding_model)

        # 创建 BERTopic 模型
        self.topic_model = BERTopic(
            umap_model=umap_model,
            vectorizer_model=vectorizer_model,
            embedding_model=sentence_model,
            nr_topics=nr_topics,
            min_topic_size=min_topic_size,
            calculate_probabilities=calculate_probabilities,
            verbose=self.verbose
        )

        # 训练模型
        self.topics, self.probs = self.topic_model.fit_transform(texts)
        self.topic_info = self.topic_model.get_topic_info()

        if self.verbose:
            print(f"\n✅ 训练完成！")
            print(f"   识别出 {len(self.topic_info)} 个主题")
            print(f"\n主题统计:")
            print(self.topic_info[['Topic', 'Count', 'Name']].head(10))

        return self

    def get_topic_label(self, topic_id: int, max_words: int = 3) -> str:
        """
        获取主题标签（使用关键词而非 "topic_1"）

        Args:
            topic_id: 主题 ID
            max_words: 最多使用多少个关键词

        Returns:
            主题标签字符串
        """
        if topic_id == -1:
            return "Outlier"

        # 获取主题的 top 关键词
        topic_words = self.topic_model.get_topic(topic_id)
        if not topic_words:
            return f"Topic {topic_id}"

        # 取前 max_words 个词
        keywords = [word for word, _ in topic_words[:max_words]]
        label = ", ".join(keywords)

        return label

    def reduce_topics(self, nr_topics: int):
        """
        减少主题数量

        Args:
            nr_topics: 目标主题数量
        """
        if self.verbose:
            print(f"\n🔄 减少主题数量到 {nr_topics}...")

        self.topics, self.probs = self.topic_model.reduce_topics(
            self.docs,
            nr_topics=nr_topics
        )
        self.topic_info = self.topic_model.get_topic_info()

        if self.verbose:
            print(f"✅ 完成！当前主题数: {len(self.topic_info)}")

    def plot_topics_distribution(
        self,
        top_n: int = 15,
        view: str = 'notebook',
        save_path: Optional[str] = None
    ):
        """
        绘制主题分布柱状图（类似 get_top_ngrams 风格）

        Args:
            top_n: 显示前 N 个主题
            view: 'browser' 或 'notebook'
            save_path: 保存路径（可选）
        """
        if self.topic_model is None:
            raise ValueError("请先训练模型（使用 fit 方法）")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'

        # 获取主题信息（排除 outlier topic -1）
        topic_df = self.topic_info[self.topic_info['Topic'] != -1].head(top_n)

        # 准备数据
        labels = []
        counts = []
        hover_texts = []

        for idx, row in topic_df.iterrows():
            topic_id = row['Topic']
            count = row['Count']

            # 使用实际关键词作为标签
            label = self.get_topic_label(topic_id, max_words=3)
            labels.append(label)
            counts.append(count)

            # Hover 文本：显示更多关键词
            topic_words = self.topic_model.get_topic(topic_id)
            words_str = ', '.join([f"{word}({score:.3f})" for word, score in topic_words[:10]])
            hover_text = f"<b>Topic {topic_id}</b><br>Count: {count}<br><br>Keywords:<br>{words_str}"
            hover_texts.append(hover_text)

        # 创建柱状图（参考 get_top_ngrams 风格）
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=counts,
            y=labels,
            orientation='h',  # 水平柱状图
            marker=dict(
                color='rgba(55, 128, 191, 0.7)',  # 蓝色
                line=dict(color='rgba(55, 128, 191, 1.0)', width=2)
            ),
            hovertext=hover_texts,
            hoverinfo='text',
            name=''
        ))

        fig.update_layout(
            title=dict(
                text=f'<b>Top {top_n} Topics Distribution</b>',
                x=0.5,
                xanchor='center'
            ),
            xaxis_title='<b>Document Count</b>',
            yaxis_title='<b>Topic (Keywords)</b>',
            template='plotly_white',
            height=max(400, top_n * 40),  # 动态高度
            showlegend=False,
            hovermode='closest'
        )

        # 反转 y 轴（最大的在上面）
        fig.update_yaxes(autorange="reversed")

        # 保存
        if save_path:
            fig.write_html(save_path)
            if self.verbose:
                print(f"💾 图表已保存到: {save_path}")

        fig.show()

        return fig

    def plot_topics_over_time(
        self,
        view: str = 'notebook',
        save_path: Optional[str] = None
    ):
        """
        绘制主题随时间变化图

        Args:
            view: 'browser' 或 'notebook'
            save_path: 保存路径（可选）
        """
        if self.original_data is None:
            raise ValueError("需要包含 'year' 列的原始数据")

        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'

        # 准备时间戳数据
        timestamps = self.original_data['year'].astype(str).tolist()

        # 使用 BERTopic 内置的 topics_over_time
        topics_over_time = self.topic_model.topics_over_time(
            self.docs,
            timestamps
        )

        # 使用 BERTopic 内置可视化
        fig = self.topic_model.visualize_topics_over_time(topics_over_time)

        # 保存
        if save_path:
            fig.write_html(save_path)
            if self.verbose:
                print(f"💾 图表已保存到: {save_path}")

        fig.show()

        return fig

    def plot_topics_heatmap(
        self,
        view: str = 'notebook',
        save_path: Optional[str] = None,
        top_n: int = 20
    ):
        """
        绘制主题相似度热力图

        Args:
            view: 'browser' 或 'notebook'
            save_path: 保存路径（可选）
            top_n: 显示前 N 个主题
        """
        # 设置渲染器
        if view == 'browser':
            pio.renderers.default = 'browser'

        # 使用 BERTopic 内置可视化
        fig = self.topic_model.visualize_heatmap(top_n_topics=top_n)

        # 保存
        if save_path:
            fig.write_html(save_path)
            if self.verbose:
                print(f"💾 图表已保存到: {save_path}")

        fig.show()

        return fig

    def get_topic_words(self, topic_id: int, n_words: int = 10) -> List[tuple]:
        """
        获取主题的关键词

        Args:
            topic_id: 主题 ID
            n_words: 返回词数

        Returns:
            [(word, score), ...] 列表
        """
        return self.topic_model.get_topic(topic_id)[:n_words]

    def get_representative_docs(self, topic_id: int) -> List[str]:
        """
        获取主题的代表性文档

        Args:
            topic_id: 主题 ID

        Returns:
            代表性文档列表
        """
        return self.topic_model.get_representative_docs(topic_id)

    def save_model(self, save_path: str):
        """
        保存模型

        Args:
            save_path: 保存路径
        """
        self.topic_model.save(save_path)
        if self.verbose:
            print(f"💾 模型已保存到: {save_path}")

    def load_model(self, load_path: str):
        """
        加载模型

        Args:
            load_path: 模型路径
        """
        self.topic_model = BERTopic.load(load_path)
        if self.verbose:
            print(f"✅ 模型已加载: {load_path}")

    def get_summary(self) -> Dict:
        """
        获取主题建模摘要

        Returns:
            包含统计信息的字典
        """
        if self.topic_model is None:
            return {}

        summary = {
            'n_topics': len(self.topic_info) - 1,  # 排除 outlier
            'n_documents': len(self.docs),
            'topics': []
        }

        for idx, row in self.topic_info[self.topic_info['Topic'] != -1].iterrows():
            topic_id = row['Topic']
            topic_summary = {
                'id': int(topic_id),
                'label': self.get_topic_label(topic_id, max_words=5),
                'count': int(row['Count']),
                'keywords': self.get_topic_words(topic_id, n_words=10)
            }
            summary['topics'].append(topic_summary)

        return summary

    def export_topics(self, output_path: str):
        """
        导出主题信息到 CSV

        Args:
            output_path: 输出文件路径
        """
        # 准备导出数据
        export_data = []

        for idx, row in self.topic_info[self.topic_info['Topic'] != -1].iterrows():
            topic_id = row['Topic']
            topic_words = self.get_topic_words(topic_id, n_words=10)

            export_data.append({
                'Topic_ID': topic_id,
                'Topic_Label': self.get_topic_label(topic_id, max_words=5),
                'Count': row['Count'],
                'Keywords': '; '.join([f"{word}({score:.3f})" for word, score in topic_words])
            })

        df = pd.DataFrame(export_data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')

        if self.verbose:
            print(f"💾 主题信息已导出到: {output_path}")
