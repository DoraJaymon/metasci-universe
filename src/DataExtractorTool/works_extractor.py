"""
WorksExtractor - 智能论文数据提取工具

智能数据源切换策略：
- 小批量（< 1000条）或最新数据（>= 2025-04）→ PyAlex API
- 大批量（> 1000条）或历史数据 → PostgreSQL 本地数据库

支持的查询过滤：
- 主题（topic）
- 领域（concepts）
- 年份范围（publication_year）
- 作者（authorships.author）
- 机构（authorships.institutions）
- 国家（authorships.institutions.country_code）
- 期刊/来源（primary_location.source）
- 论文类型（type）
- 开放获取（open_access.is_oa）
- 被引次数范围（cited_by_count）

# WorksExtractor 使用说明

## 功能
从 OpenAlex 获取论文数据，支持：
1. **灵活查询** - 支持多种过滤条件组合
2. **智能切换** - 自动选择最优数据源（API/数据库）
3. **结构化输出** - 统一的数据格式，便于后续分析

## 数据源切换策略

- ✅ **小批量（< 1000条）** → PyAlex API（快速、最新）
- ✅ **大批量（≥ 1000条）** → PostgreSQL（高效、无限制）
- ✅ **最新数据（≥ 2025-04）** → 强制使用 API
- ✅ **历史数据** → 优先使用数据库

**依赖**: pyalex, asyncpg
"""

import asyncio
import os
import sys
import time
from typing import List, Dict, Any, Optional, Union, Callable
from datetime import datetime
from pyalex import Works, config

# 添加项目根目录到路径，以便导入配置
_project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# 导入配置
try:
    from config.db_config import PYALEX_EMAIL
except ImportError:
    PYALEX_EMAIL = None


class RateLimiter:
    """
    API速率限制器

    确保API调用不超过OpenAlex的速率限制：
    - 已认证（有邮箱）: 100请求/分钟
    - 未认证: 10请求/分钟
    - 并发限制: 10个并发请求
    """

    def __init__(self, max_requests_per_minute: int = 90, concurrent_limit: int = 10):
        """
        初始化速率限制器

        Args:
            max_requests_per_minute: 每分钟最大请求数（默认90，留10%缓冲）
            concurrent_limit: 最大并发请求数（默认10）
        """
        self.max_requests = max_requests_per_minute
        self.min_interval = 60.0 / max_requests_per_minute  # 最小请求间隔（秒）
        self.concurrent_limit = concurrent_limit
        self.request_times = []  # 记录最近的请求时间
        self.lock = asyncio.Lock()

    async def wait_if_needed(self):
        """
        如果需要的话，等待以满足速率限制

        策略：
        1. 检查最近1分钟内的请求数
        2. 如果超过限制，等待直到最早的请求过期
        3. 确保两次请求之间有最小间隔
        """
        async with self.lock:
            now = time.time()

            # 移除1分钟前的请求记录
            cutoff = now - 60.0
            self.request_times = [t for t in self.request_times if t > cutoff]

            # 如果请求数达到上限，等待直到最早的请求过期
            if len(self.request_times) >= self.max_requests:
                oldest = self.request_times[0]
                wait_time = 60.0 - (now - oldest) + 0.1  # 加0.1秒缓冲
                if wait_time > 0:
                    # print(f"   [RateLimiter] 达到速率限制，等待 {wait_time:.1f}秒...")
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    # 重新清理过期记录
                    cutoff = now - 60.0
                    self.request_times = [t for t in self.request_times if t > cutoff]

            # 确保最小间隔（防止突发请求）
            if self.request_times:
                time_since_last = now - self.request_times[-1]
                if time_since_last < self.min_interval:
                    wait_time = self.min_interval - time_since_last
                    await asyncio.sleep(wait_time)
                    now = time.time()

            # 记录本次请求时间
            self.request_times.append(now)


class WorksExtractor:
    """智能论文数据提取工具（混合 API + 数据库）"""

    def __init__(
        self,
        query_fn: Optional[Callable] = None,
        email: Optional[str] = None,
        auto_switch: bool = True,
        max_requests_per_minute: int = 90  # 新增：速率限制（默认90，留缓冲）
    ):
        """
        初始化

        Args:
            query_fn: 异步数据库查询函数（可选，如不提供则仅使用API）
            email: PyAlex API 邮箱（可选，如不提供则使用配置文件中的邮箱）
            auto_switch: 是否启用自动切换策略
            max_requests_per_minute: API速率限制（默认90请求/分钟）
        """
        self.query_fn = query_fn
        self.auto_switch = auto_switch

        # 配置 PyAlex 邮箱
        # 优先级：参数传入 > 配置文件 > None
        if email:
            config.email = email
        elif PYALEX_EMAIL:
            config.email = PYALEX_EMAIL

        # 初始化速率限制器
        # 如果配置了邮箱，使用90请求/分钟；否则使用9请求/分钟
        if config.email:
            self.rate_limiter = RateLimiter(max_requests_per_minute=max_requests_per_minute)
        else:
            # 未认证，降低到9请求/分钟（OpenAlex限制10请求/分钟）
            self.rate_limiter = RateLimiter(max_requests_per_minute=9)

    # ==================== 辅助查询方法（重构版）====================

    async def search(self, entity_type: str, query: str, limit: int = 10) -> List[Dict]:
        """
        通用搜索方法（重构版 - 减少代码冗余 + SSL重试）

        Args:
            entity_type: 实体类型 ("topics", "authors", "institutions", "sources")
            query: 搜索字符串
            limit: 返回结果数量

        Returns:
            标准化的结果列表

        Examples:
            # 搜索主题
            topics = await extractor.search("topics", "machine learning")

            # 搜索作者
            authors = await extractor.search("authors", "Geoffrey Hinton")

            # 搜索机构
            institutions = await extractor.search("institutions", "Stanford")

            # 搜索期刊
            sources = await extractor.search("sources", "Nature")
        """
        from pyalex import Topics, Authors, Institutions, Sources
        import ssl

        # 映射实体类型到 PyAlex 类
        entity_classes = {
            "topics": Topics,
            "authors": Authors,
            "institutions": Institutions,
            "sources": Sources,
        }

        # 标准化处理器（提取关键字段）
        def standardize_topic(item):
            return {
                "id": item.get("id", "").replace("https://openalex.org/", ""),
                "name": item.get("display_name", ""),
                "description": item.get("description", ""),
                "works_count": item.get("works_count", 0)
            }

        def standardize_author(item):
            affiliation = ""
            if item.get("last_known_institution"):
                affiliation = item["last_known_institution"].get("display_name", "")
            return {
                "id": item.get("id", "").replace("https://openalex.org/", ""),
                "name": item.get("display_name", ""),
                "works_count": item.get("works_count", 0),
                "cited_by_count": item.get("cited_by_count", 0),
                "affiliation": affiliation
            }

        def standardize_institution(item):
            return {
                "id": item.get("id", "").replace("https://openalex.org/", ""),
                "name": item.get("display_name", ""),
                "country": item.get("country_code", ""),
                "type": item.get("type", ""),
                "works_count": item.get("works_count", 0)
            }

        def standardize_source(item):
            return {
                "id": item.get("id", "").replace("https://openalex.org/", ""),
                "name": item.get("display_name", ""),
                "type": item.get("type", ""),
                "publisher": item.get("host_organization_name", ""),
                "works_count": item.get("works_count", 0)
            }

        # 标准化处理器映射
        standardizers = {
            "topics": standardize_topic,
            "authors": standardize_author,
            "institutions": standardize_institution,
            "sources": standardize_source,
        }

        if entity_type not in entity_classes:
            raise ValueError(f"Unknown entity_type: {entity_type}. Must be one of {list(entity_classes.keys())}")

        def fetch():
            entity_class = entity_classes[entity_type]
            standardizer = standardizers[entity_type]

            items = entity_class().search(query).get()
            results = []
            for item in items[:limit]:
                results.append(standardizer(item))
            return results

        # ✅ 添加重试机制（处理SSL错误）
        max_retries = 3
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(fetch)
            except ssl.SSLEOFError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2秒、4秒、6秒
                    print(f"⚠️  SSL连接错误（尝试 {attempt+1}/{max_retries}），{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    # 最后一次尝试也失败
                    print(f"❌ SSL连接持续失败，无法搜索 {entity_type}: {query}")
                    raise
            except Exception as e:
                # 其他类型的错误，立即抛出
                if "SSL" in str(e) or "EOF" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"⚠️  网络错误（尝试 {attempt+1}/{max_retries}），{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ 网络错误持续，无法搜索 {entity_type}: {query}")
                        raise
                else:
                    raise

    # ==================== 兼容性方法（保留向后兼容）====================

    async def search_topics(self, query: str, limit: int = 10) -> List[Dict]:
        """通过名称搜索主题（兼容性方法）"""
        return await self.search("topics", query, limit)

    async def search_authors(self, query: str, limit: int = 10) -> List[Dict]:
        """通过名字搜索作者（兼容性方法）"""
        return await self.search("authors", query, limit)

    async def search_institutions(self, query: str, limit: int = 10) -> List[Dict]:
        """通过名称搜索机构（兼容性方法）"""
        return await self.search("institutions", query, limit)

    async def search_sources(self, query: str, limit: int = 10) -> List[Dict]:
        """通过名称搜索期刊/来源（兼容性方法）"""
        return await self.search("sources", query, limit)

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        标准化文本用于匹配

        规则：
        - 转小写
        - 去除多余空格
        - 复数转单数（sciences → science）
        """
        if not text:
            return ""
        text = text.lower().strip()
        # 处理复数
        text = text.replace('sciences', 'science')
        text = text.replace('studies', 'study')
        # 移除多余空格
        text = ' '.join(text.split())
        return text

    @staticmethod
    def _hierarchical_match(query: str, target: str) -> bool:
        """
        层级化匹配（支持部分匹配）

        匹配规则：
        1. 完全相等（标准化后）
        2. 前缀匹配（query 是 target 的开头）
        3. 词级别匹配（query 的所有词都在 target 中）

        示例：
        - "Physical" 匹配 "Physical Sciences" ✓（前缀）
        - "Computer" 匹配 "Computer Science" ✓（前缀）
        - "AI" 匹配 "Artificial Intelligence" ✗（需要完整词）
        """
        q_norm = WorksExtractor._normalize_text(query)
        t_norm = WorksExtractor._normalize_text(target)

        # 1. 完全相等
        if q_norm == t_norm:
            return True

        # 2. 前缀匹配
        if t_norm.startswith(q_norm):
            return True

        # 3. 词级别匹配（所有查询词都在目标中）
        q_words = set(q_norm.split())
        t_words = set(t_norm.split())
        if q_words and q_words.issubset(t_words):
            return True

        return False

    # 常用主题ID缓存（作为SSL错误的fallback）
    COMMON_TOPICS = {
        "artificial intelligence": {"id": "subfields/1702", "name": "Artificial Intelligence", "type": "subfield"},
        "machine learning": {"id": "T11001", "name": "Machine Learning", "type": "topic"},
        "deep learning": {"id": "T10577", "name": "Deep Learning", "type": "topic"},
        "natural language processing": {"id": "T10181", "name": "Natural Language Processing Techniques", "type": "topic"},
        "computer vision": {"id": "T10466", "name": "Computer Vision Techniques", "type": "topic"},
        "neural networks": {"id": "T10891", "name": "Neural Network Architectures", "type": "topic"},
        "computer science": {"id": "fields/17", "name": "Computer Science", "type": "field"},
        "physics": {"id": "fields/31", "name": "Physics", "type": "field"},
        "medicine": {"id": "fields/27", "name": "Medicine", "type": "field"},
        "biology": {"id": "fields/18", "name": "Biology", "type": "field"},
        "chemistry": {"id": "fields/19", "name": "Chemistry", "type": "field"},
    }

    async def hierarchical_topic_search(self, query: str) -> Dict[str, any]:
        """
        层级化主题搜索（Domain → Field → Subfield → Topic）+ SSL重试 + Fallback缓存

        匹配顺序：
        1. Domain（精确匹配）
        2. Field（精确匹配）
        3. Subfield（精确匹配）
        4. Topic（模糊匹配）

        Args:
            query: 查询字符串（如 "Physical", "Computer Science", "Machine Learning"）

        Returns:
            {
                'id': 'domains/3' or 'T11948',
                'type': 'domain' | 'field' | 'subfield' | 'topic',
                'name': '匹配到的名称',
                'match_level': 'exact' | 'partial' | 'fuzzy'
            }
        """
        from pyalex import Topics
        import ssl

        # ✅ 先检查缓存（快速fallback）
        query_lower = query.lower().strip()
        if query_lower in self.COMMON_TOPICS:
            cached = self.COMMON_TOPICS[query_lower]
            print(f"💾 使用缓存主题: '{query}' → '{cached['name']}' ({cached['id']})")
            return {
                'id': cached['id'],
                'type': cached['type'],
                'name': cached['name'],
                'match_level': 'cached'
            }

        # 搜索相关 topics（获取更多结果以提高匹配率）
        def search_topics():
            return Topics().search(query).get()

        # ✅ 添加重试机制（处理SSL错误）
        max_retries = 3
        topics = None
        for attempt in range(max_retries):
            try:
                topics = await asyncio.to_thread(search_topics)
                break  # 成功则跳出
            except ssl.SSLEOFError as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"⚠️  主题搜索SSL错误（尝试 {attempt+1}/{max_retries}），{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    print(f"❌ 主题搜索持续失败: '{query}'")
                    # ✅ 最后的fallback：尝试模糊匹配缓存
                    for cached_key, cached_val in self.COMMON_TOPICS.items():
                        if query_lower in cached_key or cached_key in query_lower:
                            print(f"💾 使用模糊匹配缓存: '{query}' → '{cached_val['name']}'")
                            return {
                                'id': cached_val['id'],
                                'type': cached_val['type'],
                                'name': cached_val['name'],
                                'match_level': 'cached_fuzzy'
                            }
                    raise  # 无法fallback，抛出异常
            except Exception as e:
                if "SSL" in str(e) or "EOF" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        print(f"⚠️  主题搜索网络错误（尝试 {attempt+1}/{max_retries}），{wait_time}秒后重试...")
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"❌ 主题搜索网络错误持续: '{query}'")
                        raise
                else:
                    raise

        if not topics:
            return None

        # 按层级匹配
        for topic in topics[:20]:  # 检查前20个结果
            # 检查 Domain
            domain = topic.get('domain', {})
            if domain and self._hierarchical_match(query, domain.get('display_name', '')):
                domain_id = domain['id'].replace('https://openalex.org/', '')
                return {
                    'id': domain_id,
                    'type': 'domain',
                    'name': domain['display_name'],
                    'match_level': 'exact',
                    'works_count': None  # Domain 级别没有作品数
                }

            # 检查 Field
            field = topic.get('field', {})
            if field and self._hierarchical_match(query, field.get('display_name', '')):
                field_id = field['id'].replace('https://openalex.org/', '')
                return {
                    'id': field_id,
                    'type': 'field',
                    'name': field['display_name'],
                    'match_level': 'exact',
                    'works_count': None
                }

            # 检查 Subfield
            subfield = topic.get('subfield', {})
            if subfield and self._hierarchical_match(query, subfield.get('display_name', '')):
                subfield_id = subfield['id'].replace('https://openalex.org/', '')
                return {
                    'id': subfield_id,
                    'type': 'subfield',
                    'name': subfield['display_name'],
                    'match_level': 'exact',
                    'works_count': None
                }

        # 都不匹配，返回最佳 Topic（模糊匹配）
        best_topic = topics[0]
        topic_id = best_topic['id'].replace('https://openalex.org/', '')
        return {
            'id': topic_id,
            'type': 'topic',
            'name': best_topic['display_name'],
            'match_level': 'fuzzy',
            'works_count': best_topic.get('works_count', 0)
        }

    async def smart_search(self, query_type: str, query: str, auto_select: bool = False) -> Union[List[Dict], str]:
        """
        智能搜索辅助函数 - 统一入口

        Args:
            query_type: 查询类型 ("topic", "author", "institution", "source")
            query: 查询字符串
            auto_select: 是否自动选择第一个结果（返回 ID）

        Returns:
            如果 auto_select=False: 返回候选列表
            如果 auto_select=True: 返回第一个结果的 ID

        Examples:
            # 获取候选列表
            topics = await extractor.smart_search("topic", "machine learning")
            # 输出: [{"id": "T10001", "name": "Machine learning", ...}, ...]

            # 自动选择第一个
            topic_id = await extractor.smart_search("topic", "machine learning", auto_select=True)
            # 输出: "T10001"
        """
        search_methods = {
            "topic": self.search_topics,
            "author": self.search_authors,
            "institution": self.search_institutions,
            "source": self.search_sources
        }

        if query_type not in search_methods:
            raise ValueError(f"Unknown query_type: {query_type}. Must be one of {list(search_methods.keys())}")

        results = await search_methods[query_type](query)

        if auto_select:
            return results[0]["id"] if results else None
        else:
            return results

    async def fetch_works(
        self,
        # 通用查询参数
        keywords: Optional[str] = None,
        topic_id: Optional[str] = None,
        publication_year: Optional[Union[int, str, tuple]] = None,

        # 高级过滤参数
        author_id: Optional[str] = None,
        institution_id: Optional[str] = None,
        country_code: Optional[str] = None,
        source_id: Optional[str] = None,
        work_type: Optional[str] = None,
        is_oa: Optional[bool] = None,
        cited_by_count: Optional[Union[int, str, tuple]] = None,

        # 智能参数（通过名称自动转换为 ID）
        topic_name: Optional[str] = None,
        author_name: Optional[str] = None,
        institution_name: Optional[str] = None,
        source_name: Optional[str] = None,

        # 结果控制参数
        limit: Optional[int] = None,  # None表示获取全部数据
        sort_by: str = "cited_by_count:desc",
        fields: Optional[List[str]] = None,

        # 数据源控制
        force_api: bool = False,
        force_db: bool = False,

        # 性能控制
        include_details: bool = True  # 是否包含作者、来源、主题详情（大批量查询时可设为False）
    ) -> Dict[str, Any]:
        """
        提取论文数据（支持智能名称转换）

        Args:
            keywords: 关键词搜索
            topic_id: 主题ID（如 'T10028'）
            publication_year: 年份，支持：
                - 单个年份: 2023
                - 年份范围: "2020-2023" 或 (2020, 2023)
                - 最近N年: ">2020"

            author_id: 作者ID（OpenAlex格式）
            institution_id: 机构ID
            country_code: 国家代码（如 'US', 'CN'）
            source_id: 期刊/来源ID
            work_type: 论文类型（article, book-chapter等）
            is_oa: 是否开放获取
            cited_by_count: 被引次数，支持：
                - 单个值: 100
                - 范围: "100-500" 或 (100, 500)
                - 不等式: ">100", "<500"

            # 智能参数（新增）
            topic_name: 主题名称（如 'machine learning'）- 自动转换为 ID
            author_name: 作者名称（如 'Geoffrey Hinton'）- 自动转换为 ID
            institution_name: 机构名称（如 'Stanford University'）- 自动转换为 ID
            source_name: 期刊名称（如 'Nature'）- 自动转换为 ID

            limit: 返回结果数量上限
            sort_by: 排序字段（格式：field:asc|desc）
            fields: 返回字段列表（None表示返回所有）

            force_api: 强制使用API
            force_db: 强制使用数据库

        Returns:
            {
                "works": [...],          # 论文列表
                "total": int,            # 总数
                "source": "api|database", # 数据源
                "filters": {...},        # 使用的过滤条件
                "execution_time": float  # 执行时间（秒）
            }

        Examples:
            # 方式1：使用ID（原有方式）
            result = await extractor.fetch_works(
                topic_id="T10028",
                author_id="A2345678",
                limit=100
            )

            # 方式2：使用名称（新方式 - 自动转换）
            result = await extractor.fetch_works(
                topic_name="machine learning",
                author_name="Geoffrey Hinton",
                institution_name="Stanford University",
                source_name="Nature",
                limit=100
            )

            # 方式3：混合使用
            result = await extractor.fetch_works(
                topic_name="artificial intelligence",  # 用名称
                author_id="A2345678",                   # 用ID
                limit=100
            )
        """
        start_time = asyncio.get_event_loop().time()

        # ==================== 智能名称转换 ====================
        # 如果提供了 name 参数，自动转换为 ID
        # 保存解析结果（用于返回给调用者查看匹配情况）
        resolved_names = {}

        if topic_name and not topic_id:
            # 使用层级化搜索
            result = await self.hierarchical_topic_search(topic_name)
            if not result:
                raise ValueError(f"未找到主题: '{topic_name}'")

            # 保存匹配信息
            resolved_names['topic'] = {
                'input': topic_name,
                'matched': result['name'],
                'id': result['id'],
                'type': result['type'],
                'match_level': result['match_level']
            }

            # 直接设置 topic_id（数据库会根据 ID 格式自动识别层级）
            topic_id = result['id']

        if author_name and not author_id:
            results = await self.smart_search("author", author_name, auto_select=False)
            if not results:
                raise ValueError(f"未找到作者: '{author_name}'")
            author_id = results[0]["id"]
            resolved_names['author'] = {
                'input': author_name,
                'matched': results[0]["name"],
                'id': author_id
            }

        if institution_name and not institution_id:
            results = await self.smart_search("institution", institution_name, auto_select=False)
            if not results:
                raise ValueError(f"未找到机构: '{institution_name}'")
            institution_id = results[0]["id"]
            resolved_names['institution'] = {
                'input': institution_name,
                'matched': results[0]["name"],
                'id': institution_id
            }

        if source_name and not source_id:
            results = await self.smart_search("source", source_name, auto_select=False)
            if not results:
                raise ValueError(f"未找到期刊/来源: '{source_name}'")
            source_id = results[0]["id"]
            resolved_names['source'] = {
                'input': source_name,
                'matched': results[0]["name"],
                'id': source_id
            }

        # 决策：使用 API 还是数据库
        use_api = self._should_use_api(
            limit=limit,
            publication_year=publication_year,
            force_api=force_api,
            force_db=force_db
        )

        # 收集过滤条件（用于记录）
        filters = {
            "keywords": keywords,
            "topic_id": topic_id,
            "publication_year": publication_year,
            "author_id": author_id,
            "institution_id": institution_id,
            "country_code": country_code,
            "source_id": source_id,
            "work_type": work_type,
            "is_oa": is_oa,
            "cited_by_count": cited_by_count,
        }
        # 移除 None 值
        filters = {k: v for k, v in filters.items() if v is not None}

        # 执行查询
        if use_api:
            works = await self._fetch_via_api(
                keywords=keywords,
                topic_id=topic_id,
                publication_year=publication_year,
                author_id=author_id,
                institution_id=institution_id,
                country_code=country_code,
                source_id=source_id,
                work_type=work_type,
                is_oa=is_oa,
                cited_by_count=cited_by_count,
                limit=limit,
                sort_by=sort_by,
                fields=fields,
                include_details=include_details
            )
            source = "api"
        else:
            if not self.query_fn:
                raise ValueError("数据库查询函数未配置，无法使用数据库模式")

            works = await self._fetch_via_db(
                keywords=keywords,
                topic_id=topic_id,
                publication_year=publication_year,
                author_id=author_id,
                institution_id=institution_id,
                country_code=country_code,
                source_id=source_id,
                work_type=work_type,
                is_oa=is_oa,
                cited_by_count=cited_by_count,
                limit=limit,
                sort_by=sort_by,
                fields=fields,
                include_details=include_details
            )
            source = "database"

        execution_time = asyncio.get_event_loop().time() - start_time

        result = {
            "works": works,
            "total": len(works),
            "source": source,
            "filters": filters,
            "execution_time": execution_time
        }

        # 添加名称解析信息（如果有的话）
        if resolved_names:
            result['resolved_names'] = resolved_names

        return result

    async def fetch_works_by_ids(
        self,
        work_ids: List[str],
        batch_size: int = 50,
        force_api: bool = False,
        force_db: bool = False
    ) -> Dict[str, Any]:
        """
        通过ID列表批量获取论文详情

        Args:
            work_ids: 论文ID列表（支持完整URL或短ID格式）
                例如: ["https://openalex.org/W123", "W456"]
            batch_size: API批量查询的批次大小（默认50）
            force_api: 强制使用API
            force_db: 强制使用数据库

        Returns:
            {
                "works": [...],          # 论文列表
                "total": int,            # 成功获取的数量
                "source": "api|database", # 数据源
                "execution_time": float  # 执行时间（秒）
            }
        """
        import time
        start_time = time.time()

        if not work_ids:
            return {"works": [], "total": 0, "source": "none", "execution_time": 0}

        # 去重
        unique_ids = list(set(work_ids))

        # 决定使用哪个数据源
        use_api = force_api or (not force_db and (not self.query_fn or len(unique_ids) < 1000))

        if use_api:
            works = await self._fetch_by_ids_via_api(unique_ids, batch_size)
            source = "api"
        else:
            works = await self._fetch_by_ids_via_db(unique_ids)
            source = "database"

        execution_time = time.time() - start_time

        return {
            "works": works,
            "total": len(works),
            "source": source,
            "execution_time": execution_time
        }

    async def _fetch_by_ids_via_api(
        self,
        work_ids: List[str],
        batch_size: int = 50
    ) -> List[Dict]:
        """通过API批量获取论文详情"""

        def extract_short_id(work_id: str) -> str:
            """提取短ID（W123456）"""
            if work_id.startswith("https://openalex.org/"):
                return work_id.replace("https://openalex.org/", "")
            elif work_id.startswith("http://openalex.org/"):
                return work_id.replace("http://openalex.org/", "")
            return work_id

        results = []
        total_batches = (len(work_ids) + batch_size - 1) // batch_size

        for i in range(0, len(work_ids), batch_size):
            batch_ids = work_ids[i:i+batch_size]

            def fetch_batch():
                # 提取短ID并用 | 分隔
                short_ids = [extract_short_id(wid) for wid in batch_ids]
                filter_str = '|'.join(short_ids)

                # OpenAlex API支持通过openalex_id过滤批量查询
                query = Works().filter(openalex_id=filter_str)
                return query.get()

            # 添加重试机制（最多3次）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    batch_works = await asyncio.to_thread(fetch_batch)
                    results.extend(batch_works)
                    break  # 成功则跳出重试循环
                except Exception as e:
                    if attempt < max_retries - 1:
                        # 还有重试机会，等待后重试
                        import time
                        wait_time = (attempt + 1) * 2  # 递增等待时间：2秒、4秒、6秒
                        print(f"[WorksExtractor] 批次 {i//batch_size + 1}/{total_batches} 获取失败（尝试 {attempt+1}/{max_retries}），{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        # 最后一次尝试也失败
                        print(f"[WorksExtractor] 批次 {i//batch_size + 1}/{total_batches} 最终失败: {e}")
                        print(f"[WorksExtractor] 提示：可能是网络问题或SSL证书问题，请检查网络连接")

        return results

    async def _fetch_by_ids_via_db(
        self,
        work_ids: List[str]
    ) -> List[Dict]:
        """通过数据库批量获取论文详情（分批查询以避免SQL过长）"""
        if not self.query_fn:
            raise ValueError("未提供数据库查询函数，无法使用数据库模式")

        # 标准化ID格式（去除URL前缀）
        clean_ids = []
        for wid in work_ids:
            if isinstance(wid, str) and wid:  # 确保是非空字符串
                clean_id = wid.replace("https://openalex.org/", "").strip()
                if clean_id:  # 再次确保处理后不为空
                    clean_ids.append(clean_id)
            elif wid:  # 非字符串但不为None
                clean_ids.append(str(wid))

        # 检查是否有有效的ID
        if not clean_ids:
            print(f"[WorksExtractor] 警告：没有有效的ID可查询（原始数量: {len(work_ids)}）")
            return []

        # 分批查询（每批1000个，避免SQL过长）
        batch_size = 1000
        all_results = []

        try:
            for i in range(0, len(clean_ids), batch_size):
                batch_ids = clean_ids[i:i + batch_size]

                # 跳过空批次
                if not batch_ids:
                    continue

                # 构造IN子句
                id_list = ','.join([f"'{wid}'" for wid in batch_ids])

                # 再次检查（防御性编程）
                if not id_list:
                    print(f"[WorksExtractor] 警告：批次 {i//batch_size + 1} ID列表为空，跳过")
                    continue

                # PostgreSQL批量查询
                query = f"""
                    SELECT *
                    FROM works
                    WHERE id IN ({id_list})
                """

                # 调试：打印查询信息（仅第一批）
                if i == 0:
                    print(f"[WorksExtractor] 数据库查询：总计{len(clean_ids)}个ID，分{(len(clean_ids) + batch_size - 1) // batch_size}批")
                    print(f"[WorksExtractor] 第一批示例ID: {batch_ids[:3]}")
                    print(f"[WorksExtractor] SQL长度: {len(query)} 字符")

                batch_results = await self.query_fn(query)
                all_results.extend(batch_results)

            return all_results
        except Exception as e:
            print(f"[WorksExtractor] 数据库查询失败: {e}")
            print(f"[WorksExtractor] 调试信息: work_ids数量={len(work_ids)}, clean_ids数量={len(clean_ids)}")
            if clean_ids:
                print(f"[WorksExtractor] 前3个clean_id: {clean_ids[:3]}")
            return []

    async def fetch_works_cursor(
        self,
        keywords: Optional[str] = None,
        topic_id: Optional[str] = None,
        publication_year: Optional[Union[int, str, tuple]] = None,
        author_id: Optional[str] = None,
        institution_id: Optional[str] = None,
        country_code: Optional[str] = None,
        source_id: Optional[str] = None,
        work_type: Optional[str] = None,
        is_oa: Optional[bool] = None,
        cited_by_count: Optional[Union[int, str, tuple]] = None,
        # 智能参数（新增）
        topic_name: Optional[str] = None,
        author_name: Optional[str] = None,
        institution_name: Optional[str] = None,
        source_name: Optional[str] = None,
        limit: int = 10000,
        sort_by: str = "cited_by_count:desc",
        fields: Optional[List[str]] = None
    ) -> Dict:
        """
        使用游标分页批量提取大量论文数据（推荐用于 >1000 条记录）

        现支持智能名称转换：可以直接传入名称而非 ID

        相比 fetch_works，此方法：
        - 专门使用游标分页（paginate_with_cursor）
        - 避免深度分页限制，更适合大批量数据获取
        - 仅支持 API 数据源（游标分页是 API 特性）
        - 推荐用于获取 1000+ 条记录

        Args:
            keywords: 关键词搜索
            topic_id: 主题ID（如 'T10028'）
            publication_year: 年份，支持：
                - 单个年份: 2023
                - 年份范围: "2020-2023" 或 (2020, 2023)
                - 最近N年: ">2020"

            author_id: 作者ID（OpenAlex格式）
            institution_id: 机构ID
            country_code: 国家代码（如 'US', 'CN'）
            source_id: 期刊/来源ID
            work_type: 论文类型（article, book-chapter等）
            is_oa: 是否开放获取
            cited_by_count: 被引次数，支持：
                - 单个值: 100
                - 范围: "100-500" 或 (100, 500)
                - 不等式: ">100", "<500"

            # 智能参数（新增）
            topic_name: 主题名称 - 自动转换为 ID
            author_name: 作者名称 - 自动转换为 ID
            institution_name: 机构名称 - 自动转换为 ID
            source_name: 期刊名称 - 自动转换为 ID

            limit: 返回结果数量上限（默认 10000）
            sort_by: 排序字段（格式：field:asc|desc）
            fields: 返回字段列表（None表示返回所有）

        Returns:
            {
                "works": [...],          # 论文列表
                "total": int,            # 总数
                "source": "api",         # 数据源（固定为api）
                "filters": {...},        # 使用的过滤条件
                "execution_time": float  # 执行时间（秒）
            }

        Examples:
            # 方式1：使用ID
            result = await extractor.fetch_works_cursor(
                topic_id="T10028",
                limit=5000
            )

            # 方式2：使用名称（新功能）
            result = await extractor.fetch_works_cursor(
                topic_name="machine learning",
                author_name="Geoffrey Hinton",
                limit=5000
            )
        """
        start_time = asyncio.get_event_loop().time()

        # ==================== 智能名称转换 ====================
        if topic_name and not topic_id:
            topic_id = await self.smart_search("topic", topic_name, auto_select=True)
            if not topic_id:
                raise ValueError(f"未找到主题: '{topic_name}'")

        if author_name and not author_id:
            author_id = await self.smart_search("author", author_name, auto_select=True)
            if not author_id:
                raise ValueError(f"未找到作者: '{author_name}'")

        if institution_name and not institution_id:
            institution_id = await self.smart_search("institution", institution_name, auto_select=True)
            if not institution_id:
                raise ValueError(f"未找到机构: '{institution_name}'")

        if source_name and not source_id:
            source_id = await self.smart_search("source", source_name, auto_select=True)
            if not source_id:
                raise ValueError(f"未找到期刊/来源: '{source_name}'")

        # 收集过滤条件（用于记录）
        filters = {
            "keywords": keywords,
            "topic_id": topic_id,
            "publication_year": publication_year,
            "author_id": author_id,
            "institution_id": institution_id,
            "country_code": country_code,
            "source_id": source_id,
            "work_type": work_type,
            "is_oa": is_oa,
            "cited_by_count": cited_by_count,
        }
        # 移除 None 值
        filters = {k: v for k, v in filters.items() if v is not None}

        # 使用 API 获取数据（已内置游标分页）
        works = await self._fetch_via_api(
            keywords=keywords,
            topic_id=topic_id,
            publication_year=publication_year,
            author_id=author_id,
            institution_id=institution_id,
            country_code=country_code,
            source_id=source_id,
            work_type=work_type,
            is_oa=is_oa,
            cited_by_count=cited_by_count,
            limit=limit,
            sort_by=sort_by,
            fields=fields
        )

        execution_time = asyncio.get_event_loop().time() - start_time

        return {
            "works": works,
            "total": len(works),
            "source": "api",
            "filters": filters,
            "execution_time": execution_time
        }

    def _should_use_api(
        self,
        limit: int,
        publication_year: Optional[Union[int, str, tuple]],
        force_api: bool,
        force_db: bool
    ) -> bool:
        """
        决定使用API还是数据库（优化版）

        优化策略：
        1. 小批量（<2000）优先用API（快速、完整）
        2. 最新数据必须用API
        3. 大批量历史数据用数据库
        """

        # 强制指定
        if force_api:
            return True
        if force_db:
            return False

        # 如果没有数据库连接，只能用API
        if not self.query_fn:
            return True

        # 如果不启用自动切换，默认使用API
        if not self.auto_switch:
            return True

        # ============================================================
        # 优化策略 1: 提高 API 优先级（从 1000 提高到 2000）
        # ============================================================
        # 原因：API 速度快（21秒 vs 数据库41秒），且搜索更完整
        # 适用场景：大部分文献综述需求（通常 500-2000 篇）
        if limit < 2000:
            return True

        # 策略2: 最新数据（2025-04之后）必须用API
        if publication_year:
            if isinstance(publication_year, int) and publication_year >= 2025:
                return True
            elif isinstance(publication_year, str):
                if "-" in publication_year:
                    end_year = int(publication_year.split("-")[1])
                    if end_year >= 2025:
                        return True
                elif publication_year.startswith(">"):
                    year = int(publication_year[1:])
                    if year >= 2024:
                        return True
            elif isinstance(publication_year, tuple):
                # 处理 tuple 类型: (2020, 2024)
                end_year = publication_year[1]
                if end_year >= 2025:
                    return True

        # 策略3: 大批量历史数据使用数据库
        # 只有 limit >= 2000 且是历史数据才会走到这里
        return False

    async def _fetch_via_api(
        self,
        keywords: Optional[str],
        topic_id: Optional[str],
        publication_year: Optional[Union[int, str, tuple]],
        author_id: Optional[str],
        institution_id: Optional[str],
        country_code: Optional[str],
        source_id: Optional[str],
        work_type: Optional[str],
        is_oa: Optional[bool],
        cited_by_count: Optional[Union[int, str, tuple]],
        limit: Optional[int],
        sort_by: str,
        fields: Optional[List[str]],
        include_details: bool = True  # API 模式忽略此参数（API本身返回完整信息）
    ) -> List[Dict]:
        """
        通过 PyAlex API 获取数据（重构版 - 统一使用游标分页）

        特性：
        - 默认使用游标分页（n_max=None），可突破 10000 条限制
        - 适用于任何规模的数据获取
        - 减少代码冗余（合并了原 _fetch_via_api_cursor）
        """

        def fetch():
            import sys  # ✅ 在函数开头导入，避免作用域问题

            # 警告：当 limit=None 时可能获取大量数据
            if limit is None and (keywords or topic_id):
                print(f"⚠️  警告: limit=None 将获取所有匹配的论文，可能导致：", file=sys.stderr)
                print(f"  1. 数据量过大", file=sys.stderr)
                print(f"  2. API 请求超时或 JSON 解析失败", file=sys.stderr)
                print(f"  3. 内存占用过高", file=sys.stderr)
                print(f"  建议: 设置合理的 limit（如 limit=1000）", file=sys.stderr)
                print(f"", file=sys.stderr)

            query = Works()

            # 关键词搜索标题和摘要
            if keywords:
                query = query.search(keywords)

            # 主题过滤（支持所有层级）
            if topic_id:
                # 根据 ID 格式判断层级，使用对应的嵌套过滤器
                if '/domains/' in topic_id or topic_id.startswith('domains/'):
                    # Domain 层级：使用 topics.domain.id
                    query = query.filter(topics={"domain": {"id": topic_id}})
                elif '/fields/' in topic_id or topic_id.startswith('fields/'):
                    # Field 层级：使用 topics.field.id
                    query = query.filter(topics={"field": {"id": topic_id}})
                elif '/subfields/' in topic_id or topic_id.startswith('subfields/'):
                    # Subfield 层级：使用 topics.subfield.id
                    query = query.filter(topics={"subfield": {"id": topic_id}})
                else:
                    # Topic 层级：使用 topics.id
                    query = query.filter(topics={"id": topic_id})

            # 年份过滤
            if publication_year is not None:
                if isinstance(publication_year, tuple):
                    query = query.filter(publication_year=f"{publication_year[0]}-{publication_year[1]}")
                else:
                    query = query.filter(publication_year=publication_year)

            # 作者过滤
            if author_id:
                query = query.filter(authorships={"author": {"id": author_id}})

            # 机构过滤
            if institution_id:
                query = query.filter(authorships={"institutions": {"id": institution_id}})

            # 国家过滤
            if country_code:
                query = query.filter(authorships={"institutions": {"country_code": country_code}})

            # 来源过滤
            if source_id:
                query = query.filter(primary_location={"source": {"id": source_id}})

            # 论文类型过滤
            if work_type:
                query = query.filter(type=work_type)

            # 开放获取过滤
            if is_oa is not None:
                query = query.filter(open_access={"is_oa": is_oa})

            # 被引次数过滤
            if cited_by_count is not None:
                if isinstance(cited_by_count, tuple):
                    query = query.filter(cited_by_count=f"{cited_by_count[0]}-{cited_by_count[1]}")
                else:
                    query = query.filter(cited_by_count=cited_by_count)

            # 排序
            if sort_by:
                field, order = sort_by.split(":")
                query = query.sort(**{field: order})

            # 选择字段
            # ⚠️ 重要：referenced_works 字段在 PyAlex select() 中不支持！
            # 当使用 select() 时，referenced_works 会被忽略，导致该字段不返回
            # 解决方案：如果 fields 包含 referenced_works，完全不使用 select()
            if fields:
                if 'referenced_works' in fields:
                    # 不使用 select()，让 API 返回所有默认字段（包括 referenced_works）
                    # 这样虽然会返回更多字段，但能确保 referenced_works 被包含
                    pass
                else:
                    # 不需要 referenced_works，可以安全使用 select() 来限制字段
                    query = query.select(fields)

            # 使用游标分页获取数据（默认方式）
            # n_max=None: 不限制最大记录数，由 limit 手动控制
            # 优点：可以突破默认的 10000 条限制
            #
            # per_page 设置：
            # - 100 条/页：更稳定，降低单页 JSON 被截断的风险
            # - 200 条/页：更快，但大批量时可能出现 JSONDecodeError
            per_page = 100 if limit is None or limit > 1000 else 200

            all_works = []
            page_count = 0
            start_time = time.time()

            try:
                for page in query.paginate(per_page=per_page, n_max=None):
                    page_count += 1

                    # ✅ 速率限制：在每次请求前等待（如果需要）
                    # 注意：这是在线程中运行的，需要用同步方式处理
                    # 由于 asyncio.to_thread 的限制，我们在外层处理速率限制

                    # ⚠️ 注意：由于 pyalex 使用迭代器，JSON 解析错误发生在迭代器内部
                    # 一旦某一页失败，无法真正"重试"同一页（迭代器已前进）
                    # 这个 try-except 主要用于：
                    # 1. 捕获异常，避免整个程序崩溃
                    # 2. 跳过失败的页面，继续获取后续数据
                    # 真正有效的解决方案：降低 per_page + 速率限制（已实现）
                    try:
                        for work in page:
                            if work is not None:
                                all_works.append(work)
                                # 如果设置了limit，检查是否达到限制
                                if limit is not None and len(all_works) >= limit:
                                    break

                    except Exception as e:
                        # 记录错误但继续处理下一页
                        error_msg = str(e)
                        if 'JSONDecodeError' in error_msg or 'Unterminated string' in error_msg:
                            print(f"⚠️  第 {page_count} 页 JSON 解析失败（可能是网络问题导致数据截断）", file=sys.stderr)
                            print(f"  已成功获取前 {len(all_works)} 篇论文，继续尝试下一页...", file=sys.stderr)
                        else:
                            print(f"⚠️  第 {page_count} 页处理失败: {error_msg[:100]}", file=sys.stderr)

                    # 达到限制后停止
                    if limit is not None and len(all_works) >= limit:
                        break

                    # ✅ 进度显示（每10页或大批量时）
                    if page_count % 10 == 0 or (limit and limit > 1000):
                        elapsed = time.time() - start_time
                        rate = len(all_works) / elapsed if elapsed > 0 else 0
                        if limit:
                            progress = len(all_works) / limit * 100
                            eta = (limit - len(all_works)) / rate if rate > 0 else 0
                            print(f"  📊 进度: {len(all_works)}/{limit} ({progress:.1f}%) | "
                                  f"速度: {rate:.1f}篇/秒 | 预计剩余: {eta:.0f}秒", file=sys.stderr)
                        else:
                            print(f"  已获取 {len(all_works)} 篇论文 (速度: {rate:.1f}篇/秒)...", file=sys.stderr)

                    # ✅ 添加请求间延迟（防止速率限制）
                    # 每页请求后暂停，确保不超过速率限制
                    # 由于这在同步代码中，使用 time.sleep
                    time.sleep(self.rate_limiter.min_interval)

            except Exception as e:
                # 捕获分页过程中的致命错误
                print(f"⚠️  API 分页过程出错: {str(e)[:200]}", file=sys.stderr)
                print(f"  已成功获取 {len(all_works)} 篇论文", file=sys.stderr)

            # 如果设置了limit，截取结果；否则返回全部
            return all_works[:limit] if limit is not None else all_works

        # 在线程池中执行（PyAlex 是同步的）
        works = await asyncio.to_thread(fetch)

        # 标准化输出格式
        return self._standardize_works(works, source="api")

    async def _fetch_via_db(
        self,
        keywords: Optional[str],
        topic_id: Optional[str],
        publication_year: Optional[Union[int, str, tuple]],
        author_id: Optional[str],
        institution_id: Optional[str],
        country_code: Optional[str],
        source_id: Optional[str],
        work_type: Optional[str],
        is_oa: Optional[bool],
        cited_by_count: Optional[Union[int, str, tuple]],
        limit: Optional[int],
        sort_by: str,
        fields: Optional[List[str]],
        include_details: bool = True
    ) -> List[Dict]:
        """
        通过 PostgreSQL 数据库获取数据（优化版）

        优化策略：
        1. 搜索 title + abstract（更完整）
        2. 优化 WHERE 子句顺序（选择性高的条件放前面）
        3. 使用 JSONB 操作符搜索 abstract
        4. 支持层级主题查询（自动识别 Domain/Field/Subfield ID）

        Args:
            limit: None 表示获取全部数据
            topic_id: 主题ID，支持所有层级（Topic/Subfield/Field/Domain）
        """

        # 构建 SQL 查询
        where_clauses = []
        join_clauses = []

        # ============================================================
        # 优化 1: 先应用选择性高的过滤条件（减少扫描范围）
        # ============================================================

        # 来源/期刊过滤（选择性高，需要 JOIN）
        if source_id:
            join_clauses.append("JOIN works_primary_locations wpl ON w.id = wpl.work_id")
            where_clauses.append(f"wpl.source_id = '{source_id}'")

        # 作者过滤（需要 JOIN）
        if author_id:
            join_clauses.append("JOIN works_authorships wa ON w.id = wa.work_id")
            where_clauses.append(f"wa.author_id = '{author_id}'")

        # 机构过滤（需要 JOIN）
        if institution_id:
            join_clauses.append("JOIN works_authorships wa2 ON w.id = wa2.work_id")
            join_clauses.append("JOIN works_authorships_institutions wai ON wa2.work_id = wai.work_id AND wa2.author_position = wai.author_position")
            where_clauses.append(f"wai.institution_id = '{institution_id}'")

        # 国家代码过滤（需要 JOIN）
        if country_code:
            join_clauses.append("JOIN works_authorships wa3 ON w.id = wa3.work_id")
            join_clauses.append("JOIN works_authorships_institutions wai2 ON wa3.work_id = wai2.work_id AND wa3.author_position = wai2.author_position")
            join_clauses.append("JOIN institutions i ON wai2.institution_id = i.id")
            where_clauses.append(f"i.country_code = '{country_code}'")

        # 主题过滤（支持层级查询：自动识别 Domain/Field/Subfield/Topic）
        if topic_id:
            join_clauses.append("JOIN works_topics wt ON w.id = wt.work_id")

            # 根据 topic_id 格式自动识别层级
            if '/domains/' in topic_id or topic_id.startswith('domains/'):
                # Domain 级别：通过 topics 表的 domain_id 过滤
                join_clauses.append("JOIN topics t ON wt.topic_id = t.id")
                where_clauses.append(f"t.domain_id = '{topic_id}'")
            elif '/fields/' in topic_id or topic_id.startswith('fields/'):
                # Field 级别：通过 topics 表的 field_id 过滤
                join_clauses.append("JOIN topics t ON wt.topic_id = t.id")
                where_clauses.append(f"t.field_id = '{topic_id}'")
            elif '/subfields/' in topic_id or topic_id.startswith('subfields/'):
                # Subfield 级别：通过 topics 表的 subfield_id 过滤
                join_clauses.append("JOIN topics t ON wt.topic_id = t.id")
                where_clauses.append(f"t.subfield_id = '{topic_id}'")
            else:
                # Topic 级别：直接用 topic_id
                where_clauses.append(f"wt.topic_id = '{topic_id}'")

        # 年份过滤（选择性高，有索引）
        if publication_year is not None:
            if isinstance(publication_year, tuple):
                where_clauses.append(
                    f"w.publication_year BETWEEN {publication_year[0]} AND {publication_year[1]}"
                )
            elif isinstance(publication_year, str):
                if "-" in publication_year:
                    start, end = publication_year.split("-")
                    where_clauses.append(f"w.publication_year BETWEEN {start} AND {end}")
                elif publication_year.startswith(">"):
                    year = publication_year[1:]
                    where_clauses.append(f"w.publication_year > {year}")
                elif publication_year.startswith("<"):
                    year = publication_year[1:]
                    where_clauses.append(f"w.publication_year < {year}")
            else:
                where_clauses.append(f"w.publication_year = {publication_year}")

        # 被引次数过滤（选择性高）
        if cited_by_count is not None:
            if isinstance(cited_by_count, tuple):
                where_clauses.append(
                    f"w.cited_by_count BETWEEN {cited_by_count[0]} AND {cited_by_count[1]}"
                )
            elif isinstance(cited_by_count, str):
                if "-" in cited_by_count:
                    start, end = cited_by_count.split("-")
                    where_clauses.append(f"w.cited_by_count BETWEEN {start} AND {end}")
                elif cited_by_count.startswith(">"):
                    count = cited_by_count[1:]
                    where_clauses.append(f"w.cited_by_count > {count}")
                elif cited_by_count.startswith("<"):
                    count = cited_by_count[1:]
                    where_clauses.append(f"w.cited_by_count < {count}")
            else:
                where_clauses.append(f"w.cited_by_count = {cited_by_count}")

        # 论文类型过滤（选择性中等）
        if work_type:
            where_clauses.append(f"w.type = '{work_type}'")

        # 开放获取过滤
        if is_oa is not None:
            where_clauses.append(f"w.is_oa = {is_oa}")

        # ============================================================
        # 优化 2: 关键词搜索 - 搜索 title + abstract（更完整）
        # ============================================================
        if keywords:
            keywords_escaped = keywords.replace("'", "''")

            # 搜索 title 或 abstract
            # 使用 JSONB ? 操作符搜索 abstract_inverted_index
            # 如果数据库有 JSONB GIN 索引，这会比较快
            where_clauses.append(f"""(
                w.title ILIKE '%{keywords_escaped}%' OR
                (w.abstract_inverted_index IS NOT NULL AND
                 w.abstract_inverted_index::jsonb ? '{keywords_escaped.lower()}')
            )""")

        # 选择字段
        if fields:
            # 过滤掉数据库不支持的字段（如 referenced_works 在单独的表中）
            db_supported_fields = [f for f in fields if f != 'referenced_works']
            if db_supported_fields:
                select_fields = ", ".join([f"w.{f}" for f in db_supported_fields])
            else:
                # 如果所有字段都被过滤了，至少返回基本字段
                select_fields = "w.id, w.title, w.publication_year, w.cited_by_count"
        else:
            select_fields = "w.*"

        # WHERE 子句
        where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

        # JOIN 子句（去重）
        join_sql = "\n".join(dict.fromkeys(join_clauses))  # 去重复的 JOIN

        # 排序
        order_by = ""
        if sort_by:
            field, order = sort_by.split(":")
            order_by = f"ORDER BY w.{field} {order.upper()}"

        # ============================================================
        # 优化 3: 使用子查询优化（先排序再限制）
        # ============================================================
        # 如果有 JOIN，需要去重（避免一篇论文因为多个作者/机构而重复）
        if join_clauses:
            # 使用子查询：先去重，再排序和限制
            # 这样可以保证正确的排序和去重
            limit_clause = f"LIMIT {limit}" if limit is not None else ""
            sql = f"""
            SELECT {select_fields}
            FROM (
                SELECT DISTINCT w.id
                FROM works w
                {join_sql}
                WHERE {where_sql}
            ) AS work_ids
            JOIN works w ON work_ids.id = w.id
            {order_by}
            {limit_clause}
            """
        else:
            # 没有 JOIN，直接查询
            limit_clause = f"LIMIT {limit}" if limit is not None else ""
            sql = f"""
            SELECT {select_fields}
            FROM works w
            WHERE {where_sql}
            {order_by}
            {limit_clause}
            """

        # 执行查询
        results = await self.query_fn(sql)

        # 补充关联信息（大批量自动跳过详细信息）
        if include_details and results:
            if len(results) >= 10000:
                # 大数据集：自动跳过详细信息
                print(f"⚠️  数据量较大({len(results):,}篇)，自动跳过详细信息查询")
                print(f"    只返回基本8字段（id, title, year, citations, doi, type, is_oa, date）")
                print(f"    如需详细信息，请使用 limit 限制数量或设置 include_details=True 强制获取")
                # 不查询详细信息，results 保持原样
            else:
                # 小数据集：一次性处理
                results = await self._enrich_db_works(results)

        # 标准化输出格式
        return self._standardize_works(results, source="database")

    async def _enrich_db_works_batched(self, works: List[Dict], batch_size: int = 2000) -> List[Dict]:
        """
        分批补充数据库查询结果的关联信息（适合大数据集）

        Args:
            works: 从数据库查询的论文基本信息
            batch_size: 每批处理的数量

        Returns:
            补充了关联信息的论文列表
        """
        if not works:
            return works

        total_batches = (len(works) + batch_size - 1) // batch_size
        print(f"   分批处理：总计 {len(works):,} 篇，分 {total_batches} 批...")

        for i in range(0, len(works), batch_size):
            batch = works[i:i + batch_size]
            batch_num = i // batch_size + 1

            print(f"   处理第 {batch_num}/{total_batches} 批 ({len(batch):,} 篇)...", end=" ")

            # 处理这一批
            enriched_batch = await self._enrich_db_works(batch)

            # 更新原列表
            works[i:i + batch_size] = enriched_batch

            print("✓")

        print(f"   ✅ 完成！共处理 {len(works):,} 篇论文")
        return works

    async def _enrich_db_works(self, works: List[Dict]) -> List[Dict]:
        """
        补充数据库查询结果的关联信息（作者、来源、主题）

        Args:
            works: 从数据库查询的论文基本信息

        Returns:
            补充了关联信息的论文列表
        """
        if not works:
            return works

        work_ids = [w['id'] for w in works]

        # 批量查询作者信息
        authors_map = await self._fetch_authors_for_works(work_ids)

        # 批量查询来源信息
        sources_map = await self._fetch_sources_for_works(work_ids)

        # 批量查询主题信息
        topics_map = await self._fetch_topics_for_works(work_ids)

        # 将关联信息添加到每篇论文
        for work in works:
            work_id = work['id']
            work['authors'] = authors_map.get(work_id, [])
            work['source'] = sources_map.get(work_id, {})
            work['topics'] = topics_map.get(work_id, [])

        return works

    async def _fetch_authors_for_works(self, work_ids: List[str]) -> Dict[str, List[Dict]]:
        """批量查询论文的作者信息（支持超大批次，自动分批）"""
        if not work_ids:
            return {}

        # 如果 ID 太多，分批查询（避免 SQL 过长）
        max_ids_per_query = 5000
        if len(work_ids) > max_ids_per_query:
            authors_map = {}
            for i in range(0, len(work_ids), max_ids_per_query):
                batch_ids = work_ids[i:i + max_ids_per_query]
                batch_result = await self._fetch_authors_for_works(batch_ids)
                authors_map.update(batch_result)
            return authors_map

        placeholders = ','.join([f"'{wid}'" for wid in work_ids])
        sql = f"""
            SELECT
                wa.work_id,
                wa.author_id,
                a.display_name as author_name,
                wa.author_position
            FROM works_authorships wa
            LEFT JOIN authors a ON wa.author_id = a.id
            WHERE wa.work_id IN ({placeholders})
            ORDER BY wa.work_id, wa.author_position
        """

        records = await self.query_fn(sql)

        # 组织成字典
        authors_map = {}
        for rec in records:
            work_id = rec['work_id']
            if work_id not in authors_map:
                authors_map[work_id] = []
            authors_map[work_id].append({
                'id': rec['author_id'] or '',
                'name': rec['author_name'] or '',
                'position': rec['author_position'] or ''
            })

        return authors_map

    async def _fetch_sources_for_works(self, work_ids: List[str]) -> Dict[str, Dict]:
        """批量查询论文的来源信息（支持超大批次，自动分批）"""
        if not work_ids:
            return {}

        # 如果 ID 太多，分批查询
        max_ids_per_query = 5000
        if len(work_ids) > max_ids_per_query:
            sources_map = {}
            for i in range(0, len(work_ids), max_ids_per_query):
                batch_ids = work_ids[i:i + max_ids_per_query]
                batch_result = await self._fetch_sources_for_works(batch_ids)
                sources_map.update(batch_result)
            return sources_map

        placeholders = ','.join([f"'{wid}'" for wid in work_ids])
        sql = f"""
            SELECT
                wpl.work_id,
                wpl.source_id,
                s.display_name as source_name,
                s.publisher as source_publisher
            FROM works_primary_locations wpl
            LEFT JOIN sources s ON wpl.source_id = s.id
            WHERE wpl.work_id IN ({placeholders})
        """

        records = await self.query_fn(sql)

        # 组织成字典
        sources_map = {}
        for rec in records:
            sources_map[rec['work_id']] = {
                'id': rec['source_id'] or '',
                'name': rec['source_name'] or '',
                'publisher': rec['source_publisher'] or ''
            }

        return sources_map

    async def _fetch_topics_for_works(self, work_ids: List[str]) -> Dict[str, List[Dict]]:
        """批量查询论文的主题信息（支持超大批次，自动分批）"""
        if not work_ids:
            return {}

        # 如果 ID 太多，分批查询
        max_ids_per_query = 5000
        if len(work_ids) > max_ids_per_query:
            topics_map = {}
            for i in range(0, len(work_ids), max_ids_per_query):
                batch_ids = work_ids[i:i + max_ids_per_query]
                batch_result = await self._fetch_topics_for_works(batch_ids)
                topics_map.update(batch_result)
            return topics_map

        placeholders = ','.join([f"'{wid}'" for wid in work_ids])
        sql = f"""
            SELECT
                wt.work_id,
                wt.topic_id,
                t.display_name as topic_name,
                wt.score
            FROM works_topics wt
            LEFT JOIN topics t ON wt.topic_id = t.id
            WHERE wt.work_id IN ({placeholders})
            ORDER BY wt.work_id, wt.score DESC
        """

        records = await self.query_fn(sql)

        # 组织成字典
        topics_map = {}
        for rec in records:
            work_id = rec['work_id']
            if work_id not in topics_map:
                topics_map[work_id] = []
            # 只保留前5个主题
            if len(topics_map[work_id]) < 5:
                topics_map[work_id].append({
                    'id': rec['topic_id'] or '',
                    'name': rec['topic_name'] or '',
                    'score': rec['score'] or 0
                })

        return topics_map

    def _standardize_works(self, works: List[Dict], source: str) -> List[Dict]:
        """标准化输出格式（确保API和数据库返回格式一致）"""

        standardized = []

        for work in works:
            # 跳过 None 值
            if work is None:
                continue

            if source == "api":
                # PyAlex API 格式 → 标准格式
                std_work = {
                    "id": (work.get("id") or "").replace("https://openalex.org/", ""),
                    "doi": work.get("doi") or "",
                    "title": work.get("title") or "",
                    "publication_year": work.get("publication_year"),
                    "publication_date": work.get("publication_date"),
                    "type": work.get("type"),
                    "cited_by_count": work.get("cited_by_count", 0),
                    "is_oa": (work.get("open_access") or {}).get("is_oa", False),

                    # 提取作者信息
                    "authors": [
                        {
                            "id": ((auth.get("author") or {}).get("id") or "").replace("https://openalex.org/", ""),
                            "name": (auth.get("author") or {}).get("display_name") or "",
                            "position": auth.get("author_position") or ""
                        }
                        for auth in (work.get("authorships") or [])
                        if auth is not None
                    ],

                    # 提取来源信息
                    "source": {
                        "id": (((work.get("primary_location") or {}).get("source") or {}).get("id") or "").replace("https://openalex.org/", ""),
                        "name": ((work.get("primary_location") or {}).get("source") or {}).get("display_name") or "",
                        "type": ((work.get("primary_location") or {}).get("source") or {}).get("type") or "",
                        "publisher": work.get("source", {}).get("publisher", "")
                    },

                    # 提取主题/概念
                    "topics": [
                        {
                            "id": (topic.get("id") or "").replace("https://openalex.org/", ""),
                            "name": topic.get("display_name") or "",
                            "score": topic.get("score", 0)
                        }
                        for topic in (work.get("topics") or [])
                        if topic is not None
                    ][:5],  # 只保留前5个主题

                    # 被引文献（RPYS分析需要）
                    "referenced_works": [
                        ref.replace("https://openalex.org/", "") if isinstance(ref, str) else ref
                        for ref in (work.get("referenced_works") or [])
                    ],

                    # 原始数据（可选）
                    "_raw": work
                }
            else:
                # 数据库格式 → 标准格式
                std_work = {
                    "id": work.get("id") or "",
                    "doi": work.get("doi") or "",
                    "title": work.get("title") or "",
                    "publication_year": work.get("publication_year"),
                    "publication_date": work.get("publication_date"),
                    "type": work.get("type"),
                    "cited_by_count": work.get("cited_by_count", 0),
                    "is_oa": work.get("is_oa", False),

                    # 从补充查询中获取的关联信息
                    "authors": work.get("authors", []),
                    "source": work.get("source", {}),  # {id, name, publisher}
                    "topics": work.get("topics", []),

                    # 被引文献（如果有）
                    "referenced_works": work.get("referenced_works", []),

                    "_raw": work
                }

            standardized.append(std_work)

        return standardized


# ==================== 测试代码 ====================
if __name__ == "__main__":
    import sys
    import os

    # 添加项目根目录到路径
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)

    async def test_works_extractor():
        """
        测试 WorksExtractor 工具

        测试场景：
        1. 科学计量学领域（Scientometrics）- API模式
        2. AI for Education 领域 - API模式
        3. 大批量历史数据 - 数据库模式（如果配置了数据库）
        """

        # 导入数据库配置
        try:
            from config.db_config import DB_CONFIG
            import asyncpg
            db_available = True
        except (ImportError, ModuleNotFoundError):
            print("⚠️  数据库配置未找到，仅测试 API 模式")
            print("   提示：请配置 config/db_config.py 文件")
            db_available = False
            DB_CONFIG = None

        # 创建输出目录（在工具文件夹下）
        tool_dir = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(tool_dir, "test_output")
        os.makedirs(output_dir, exist_ok=True)

        output = []
        output.append("=" * 80)
        output.append("WorksExtractor 工具测试")
        output.append("=" * 80)
        output.append(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output.append("")

        # 配置数据库查询函数
        conn = None
        query_fn = None

        if db_available and DB_CONFIG:
            try:
                conn = await asyncpg.connect(**DB_CONFIG)

                async def query_fn(sql: str):
                    records = await conn.fetch(sql)
                    return [dict(record) for record in records]

                output.append("✅ 数据库连接成功")
            except Exception as e:
                output.append(f"⚠️  数据库连接失败: {e}")
                output.append("   仅测试 API 模式")
                db_available = False

        # 创建工具实例（自动从配置文件读取邮箱）
        extractor = WorksExtractor(
            query_fn=query_fn,
            # email 参数不传，自动使用配置文件中的 PYALEX_EMAIL
            auto_switch=True
        )

        # 显示使用的邮箱配置
        if config.email:
            output.append(f"✅ PyAlex 邮箱配置: {config.email}")
        else:
            output.append("⚠️  未配置 PyAlex 邮箱，建议在 config/api_config.py 中设置")

        output.append("")
        output.append("=" * 80)
        output.append("测试 1: 科学计量学领域（Scientometrics）- 小批量 API 模式")
        output.append("=" * 80)

        print("\n测试 1: 科学计量学领域...")

        result1 = await extractor.fetch_works(
            keywords="scientometrics",
            publication_year=(2020, 2023),
            work_type="article",
            cited_by_count=">10",
            limit=100,
            sort_by="cited_by_count:desc"
        )

        output.append(f"数据源: {result1['source']}")
        output.append(f"返回结果: {result1['total']} 篇论文")
        output.append(f"执行时间: {result1['execution_time']:.2f} 秒")
        output.append(f"过滤条件: {result1['filters']}")
        output.append("")
        output.append("Top 10 高被引论文:")

        for i, work in enumerate(result1['works'][:10], 1):
            title = work['title']
            if len(title) > 70:
                title = title[:70] + "..."
            output.append(f"{i:2d}. {title}")
            output.append(f"    年份: {work['publication_year']} | 被引: {work['cited_by_count']}次 | DOI: {work['doi']}")

        output.append("")
        output.append("=" * 80)
        output.append("测试 2: AI for Education 领域 - 小批量 API 模式")
        output.append("=" * 80)

        print("\n测试 2: AI for Education 领域...")

        result2 = await extractor.fetch_works(
            keywords="artificial intelligence education",
            publication_year=(2022, 2024),
            work_type="article",
            cited_by_count=">5",
            limit=50,
            sort_by="publication_year:desc"
        )

        output.append(f"数据源: {result2['source']}")
        output.append(f"返回结果: {result2['total']} 篇论文")
        output.append(f"执行时间: {result2['execution_time']:.2f} 秒")
        output.append(f"过滤条件: {result2['filters']}")
        output.append("")
        output.append("最新 10 篇论文:")

        for i, work in enumerate(result2['works'][:10], 1):
            title = work['title']
            if len(title) > 70:
                title = title[:70] + "..."
            output.append(f"{i:2d}. {title}")
            output.append(f"    年份: {work['publication_year']} | 被引: {work['cited_by_count']}次")

            # 显示主题
            if work['topics']:
                topics_str = ", ".join([t['name'] for t in work['topics'][:3]])
                output.append(f"    主题: {topics_str}")

        # 测试 3: 大批量数据（如果数据库可用）
        if db_available:
            output.append("")
            output.append("=" * 80)
            output.append("测试 3: 机器学习领域大批量数据 - 数据库模式")
            output.append("=" * 80)

            print("\n测试 3: 大批量数据（数据库模式）...")

            result3 = await extractor.fetch_works(
                keywords="machine learning",
                publication_year=(2018, 2022),
                work_type="article",
                cited_by_count=">50",
                limit=5000,  # 大批量
                sort_by="cited_by_count:desc"
            )

            output.append(f"数据源: {result3['source']}")
            output.append(f"返回结果: {result3['total']} 篇论文")
            output.append(f"执行时间: {result3['execution_time']:.2f} 秒")
            output.append(f"过滤条件: {result3['filters']}")

            # 统计信息
            if result3['works']:
                years = [w['publication_year'] for w in result3['works'] if w['publication_year']]
                citations = [w['cited_by_count'] for w in result3['works']]

                output.append("")
                output.append("统计信息:")
                output.append(f"  年份范围: {min(years)} - {max(years)}")
                output.append(f"  总被引次数: {sum(citations):,}")
                output.append(f"  平均被引次数: {sum(citations) / len(citations):.1f}")
                output.append(f"  最高被引次数: {max(citations)}")

        # 测试 4: 最新数据（强制 API）
        output.append("")
        output.append("=" * 80)
        output.append("测试 4: 最新数据（2024-2025）- 强制 API 模式")
        output.append("=" * 80)

        print("\n测试 4: 最新数据...")

        result4 = await extractor.fetch_works(
            keywords="large language model",
            publication_year=">2023",
            work_type="article",
            limit=30,
            sort_by="publication_year:desc",
            force_api=True
        )

        output.append(f"数据源: {result4['source']}")
        output.append(f"返回结果: {result4['total']} 篇论文")
        output.append(f"执行时间: {result4['execution_time']:.2f} 秒")
        output.append("")
        output.append("2024-2025年最新论文:")

        for i, work in enumerate(result4['works'][:10], 1):
            title = work['title']
            if len(title) > 70:
                title = title[:70] + "..."
            output.append(f"{i:2d}. {title}")
            output.append(f"    年份: {work['publication_year']} | 发表日期: {work['publication_date']}")

        # 总结
        output.append("")
        output.append("=" * 80)
        output.append("测试总结")
        output.append("=" * 80)
        output.append("")
        output.append("智能数据源切换策略:")
        output.append("  ✅ 小批量（< 1000条）→ PyAlex API（快速、最新）")
        output.append("  ✅ 大批量（≥ 1000条）→ PostgreSQL（高效、无限制）")
        output.append("  ✅ 最新数据（≥ 2025-04）→ 强制使用 API")
        output.append("")
        output.append("测试结果:")
        output.append(f"  • 测试 1（科学计量学）: {result1['total']} 篇，来源: {result1['source']}")
        output.append(f"  • 测试 2（AI教育）: {result2['total']} 篇，来源: {result2['source']}")
        if db_available:
            output.append(f"  • 测试 3（大批量）: {result3['total']} 篇，来源: {result3['source']}")
        output.append(f"  • 测试 4（最新数据）: {result4['total']} 篇，来源: {result4['source']}")

        # 保存结果
        output_file = os.path.join(output_dir, f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(output))

        print(f"\n✅ 测试完成，结果已保存到: {output_file}")

        # 同时保存JSON格式的详细数据
        import json

        json_output = {
            "test1_scientometrics": {
                "metadata": {
                    "source": result1['source'],
                    "total": result1['total'],
                    "execution_time": result1['execution_time'],
                    "filters": result1['filters']
                },
                "works": result1['works'][:20]  # 保存前20条
            },
            "test2_ai_education": {
                "metadata": {
                    "source": result2['source'],
                    "total": result2['total'],
                    "execution_time": result2['execution_time'],
                    "filters": result2['filters']
                },
                "works": result2['works'][:20]
            },
            "test4_latest": {
                "metadata": {
                    "source": result4['source'],
                    "total": result4['total'],
                    "execution_time": result4['execution_time'],
                    "filters": result4['filters']
                },
                "works": result4['works'][:20]
            }
        }

        if db_available:
            json_output["test3_large_batch"] = {
                "metadata": {
                    "source": result3['source'],
                    "total": result3['total'],
                    "execution_time": result3['execution_time'],
                    "filters": result3['filters']
                },
                "works": result3['works'][:20]
            }

        json_file = os.path.join(output_dir, f"test_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(json_output, f, ensure_ascii=False, indent=2)

        print(f"✅ 详细数据已保存到: {json_file}")

        # 关闭数据库连接
        if conn:
            await conn.close()

    # 运行测试
    asyncio.run(test_works_extractor())
