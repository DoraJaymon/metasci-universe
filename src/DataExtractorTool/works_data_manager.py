"""
论文数据管理器 (Works Data Manager)

该模块提供统一的论文数据获取、缓存和管理功能。
所有分析工具应该通过这个管理器获取数据，而不是各自实现数据获取逻辑。

核心功能：
1. 统一的论文数据获取接口（API + 数据库）
2. 自动缓存管理（避免重复获取）
3. 被引文献详情补全
4. 数据验证和清洗

设计理念：
- 单一职责：只负责数据获取和管理，不涉及分析逻辑
- 智能缓存：自动检测并使用缓存，支持增量更新
- 灵活配置：支持API、数据库、本地文件多种数据源

Author: SciSciTool
Date: 2025-11-19
"""

from typing import Dict, List, Optional, Tuple, Callable
from pathlib import Path
import json
import hashlib
from datetime import datetime


class WorksDataManager:
    """
    论文数据管理器

    提供统一的数据获取、缓存和管理接口。

    Example:
        >>> manager = WorksDataManager()
        >>>
        >>> # 方式1: 获取论文数据（自动缓存）
        >>> works = await manager.fetch_works(
        ...     keywords="scientometrics",
        ...     year_range=(2020, 2024),
        ...     limit=100
        ... )
        >>>
        >>> # 方式2: 补充被引文献详情
        >>> works_with_refs = await manager.enrich_references(works)
        >>>
        >>> # 方式3: 一站式获取（论文+被引详情）
        >>> dataset = await manager.prepare_dataset(
        ...     keywords="scientometrics",
        ...     year_range=(2020, 2024),
        ...     limit=100,
        ...     include_references=True
        ... )
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        verbose: bool = True
    ):
        """
        初始化数据管理器

        Args:
            cache_dir: 缓存目录，默认为项目根目录的data文件夹
            verbose: 是否打印详细信息
        """
        self.verbose = verbose

        # 设置缓存目录
        if cache_dir is None:
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / "data" / "works_cache"
        else:
            self.cache_dir = Path(cache_dir)

        self.cache_dir.mkdir(exist_ok=True, parents=True)

    def _generate_cache_key(
        self,
        keywords: Optional[str] = None,
        year_range: Optional[Tuple[int, int]] = None,
        limit: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        生成缓存键

        基于查询参数生成唯一的缓存标识符。

        Args:
            keywords: 关键词
            year_range: 年份范围
            limit: 数量限制 (None表示无限制)
            **kwargs: 其他查询参数

        Returns:
            缓存键字符串
        """
        # 构建参数字典
        params = {
            'keywords': keywords,
            'year_range': year_range,
            'limit': limit,
            **kwargs
        }

        # 移除None值
        params = {k: v for k, v in params.items() if v is not None}

        # 生成哈希
        param_str = json.dumps(params, sort_keys=True)
        cache_hash = hashlib.md5(param_str.encode()).hexdigest()[:12]

        # 生成可读的缓存键
        safe_keywords = keywords.replace(" ", "_")[:20] if keywords else "query"
        limit_str = str(limit) if limit is not None else "all"
        cache_key = f"works_{safe_keywords}_{limit_str}_{cache_hash}"

        return cache_key

    def _get_cache_path(self, cache_key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{cache_key}.json"

    def load_from_cache(
        self,
        cache_key: Optional[str] = None,
        cache_file: Optional[str] = None
    ) -> Optional[List[Dict]]:
        """
        从缓存加载数据

        Args:
            cache_key: 缓存键（自动生成的）
            cache_file: 缓存文件路径（用户指定的）

        Returns:
            论文数据列表，如果缓存不存在则返回None
        """
        if cache_file:
            cache_path = Path(cache_file)
        elif cache_key:
            cache_path = self._get_cache_path(cache_key)
        else:
            raise ValueError("必须提供 cache_key 或 cache_file")

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if self.verbose:
                print(f"[DataManager] ✅ 从缓存加载: {cache_path}")
                print(f"[DataManager]    {len(data)} 篇论文")

            return data
        except Exception as e:
            if self.verbose:
                print(f"[DataManager] ⚠️  缓存加载失败: {e}")
            return None

    def save_to_cache(
        self,
        works: List[Dict],
        cache_key: Optional[str] = None,
        cache_file: Optional[str] = None
    ):
        """
        保存数据到缓存

        Args:
            works: 论文数据列表
            cache_key: 缓存键
            cache_file: 缓存文件路径
        """
        if cache_file:
            cache_path = Path(cache_file)
            cache_path.parent.mkdir(exist_ok=True, parents=True)
        elif cache_key:
            cache_path = self._get_cache_path(cache_key)
        else:
            raise ValueError("必须提供 cache_key 或 cache_file")

        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(works, f, ensure_ascii=False, indent=2)

            if self.verbose:
                print(f"[DataManager] ✅ 保存到缓存: {cache_path}")
        except Exception as e:
            if self.verbose:
                print(f"[DataManager] ⚠️  缓存保存失败: {e}")

    async def fetch_works(
        self,
        # 查询参数（字典形式）
        filters: Optional[Dict] = None,
        # 缓存和数据源控制
        use_cache: bool = True,
        force_refetch: bool = False,
        cache_file: Optional[str] = None,
        data_source: str = "auto",
        db_connection = None,
        # 性能控制
        include_details: bool = True,  # 是否包含作者、来源、主题（大批量时设为False）
        include_references: bool = True  # 是否包含参考文献ID列表（不需要时设为False）
    ) -> List[Dict]:
        """
        获取论文数据

        该方法会：
        1. 检查缓存（除非force_refetch=True）
        2. 从API或数据库获取数据
        3. 保存到缓存

        Args:
            filters: 查询过滤条件字典，包含所有 WorksExtractor.fetch_works 支持的参数
                - keywords: 关键词搜索
                - publication_year: 年份（单个、范围或元组）
                - topic_name: 主题名称（如 "machine learning"）
                - topic_id: 主题ID
                - source_name: 期刊名称（如 "Nature"）
                - source_id: 期刊ID
                - author_name: 作者名称
                - author_id: 作者ID
                - institution_name: 机构名称
                - institution_id: 机构ID
                - country_code: 国家代码
                - work_type: 论文类型
                - is_oa: 是否开放获取
                - cited_by_count: 被引次数
                - limit: 获取数量（默认100）
                - sort_by: 排序方式
                - fields: 返回字段列表
                - ... 等所有 WorksExtractor.fetch_works 支持的参数

            use_cache: 是否使用缓存
            force_refetch: 是否强制重新获取
            cache_file: 自定义缓存文件路径
            data_source: 数据源 "api"/"database"/"auto"
            db_connection: 数据库连接
            include_details: 是否包含作者、来源、主题详情（仅数据库模式有效）
                - True: 返回完整12字段（默认）
                - False: 只返回基本8字段，适合大批量数据（避免内存问题）
            include_references: 是否包含参考文献ID列表（仅数据库模式有效）
                - True: 包含 referenced_works 字段（默认）
                - False: 跳过参考文献查询，提升性能

        Returns:
            论文数据列表

        Examples:
            # 按关键词搜索
            works = await manager.fetch_works(
                filters={"keywords": "AI", "limit": 100}
            )

            # 按期刊筛选
            works = await manager.fetch_works(
                filters={
                    "source_name": "Nature",
                    "publication_year": (2020, 2024),
                    "limit": 500
                }
            )

            # 按主题筛选
            works = await manager.fetch_works(
                filters={
                    "topic_name": "machine learning",
                    "publication_year": (2022, 2024)
                }
            )

            # 复杂筛选
            works = await manager.fetch_works(
                filters={
                    "keywords": "benchmark",
                    "topic_name": "Artificial Intelligence",
                    "publication_year": (2021, 2024),
                    "is_oa": True
                }
            )
        """
        from .works_extractor import WorksExtractor

        # 处理查询参数
        if filters is None:
            filters = {}

        # 设置默认值（如果用户没有设置limit，默认为None表示获取全部）
        query_params = {
            'limit': filters.get('limit', None),  # 默认None表示获取全部
            **filters
        }

        # 从 query_params 中移除 include_details（这个参数只在内部使用）
        query_params.pop('include_details', None)

        # 生成缓存键
        cache_key = self._generate_cache_key(**query_params)

        # 尝试从缓存加载
        if use_cache and not force_refetch:
            cached_works = self.load_from_cache(
                cache_key=cache_key if not cache_file else None,
                cache_file=cache_file
            )
            if cached_works is not None:
                return cached_works

        # 从数据源获取
        if self.verbose:
            source_name = {
                "api": "API",
                "database": "数据库",
                "auto": "自动选择数据源"
            }.get(data_source, data_source)
            print(f"[DataManager] 从{source_name}获取论文数据...")
            # 打印主要查询条件
            query_summary = []
            if query_params.get('keywords'):
                query_summary.append(f"keywords={query_params['keywords']}")
            if query_params.get('publication_year'):
                query_summary.append(f"year={query_params['publication_year']}")
            if query_params.get('topic_name'):
                query_summary.append(f"topic={query_params['topic_name']}")
            if query_params.get('source_name'):
                query_summary.append(f"source={query_params['source_name']}")
            if query_summary:
                print(f"[DataManager] 查询: {', '.join(query_summary)}, limit={query_params.get('limit', 100)}")

        # 创建 WorksExtractor 并调用
        if data_source == "database" and db_connection:
            async def query_fn(sql):
                records = await db_connection.fetch(sql)
                return [dict(r) for r in records]

            extractor = WorksExtractor(query_fn=query_fn, auto_switch=False)
            result = await extractor.fetch_works(
                **query_params,
                force_db=True,
                include_details=include_details
            )
        elif data_source == "api":
            extractor = WorksExtractor()
            result = await extractor.fetch_works(
                **query_params,
                force_api=True,
                include_details=include_details  # API 模式会忽略此参数
            )
        else:  # auto
            extractor = WorksExtractor()
            result = await extractor.fetch_works(
                **query_params,
                include_details=include_details
            )

        works = result['works']

        if self.verbose:
            print(f"[DataManager] ✅ 获取了 {len(works)} 篇论文（数据源: {result['source']}）")

            # 如果使用了 smart_search (name -> id 转换)，打印匹配信息
            if result.get('resolved_names'):
                resolved = result['resolved_names']
                print(f"[DataManager] 🔍 智能匹配结果:")
                if 'topic' in resolved:
                    info = resolved['topic']
                    match_type = info.get('type', 'topic')
                    match_level = info.get('match_level', 'unknown')
                    print(f"  - 主题: '{info['input']}' → '{info['matched']}' ({info['id']})")
                    if match_type != 'topic':
                        print(f"    层级: {match_type}, 匹配度: {match_level}")
                if 'source' in resolved:
                    info = resolved['source']
                    print(f"  - 期刊: '{info['input']}' → '{info['matched']}' ({info['id']})")
                if 'author' in resolved:
                    info = resolved['author']
                    print(f"  - 作者: '{info['input']}' → '{info['matched']}' ({info['id']})")
                if 'institution' in resolved:
                    info = resolved['institution']
                    print(f"  - 机构: '{info['input']}' → '{info['matched']}' ({info['id']})")

        # 如果使用数据库且需要参考文献，获取 referenced_works
        if result['source'] == 'database' and db_connection and include_references:
            works = await self._fetch_referenced_works_from_db(works, db_connection)

        # 保存到缓存
        if use_cache:
            self.save_to_cache(
                works,
                cache_key=cache_key if not cache_file else None,
                cache_file=cache_file
            )

        return works

    async def _fetch_referenced_works_from_db(
        self,
        works: List[Dict],
        db_connection
    ) -> List[Dict]:
        """
        从数据库获取 referenced_works 字段

        Args:
            works: 论文列表
            db_connection: 数据库连接

        Returns:
            补充了 referenced_works 的论文列表
        """
        if self.verbose:
            print(f"[DataManager] 从数据库获取被引文献ID...")

        work_ids = [w['id'] for w in works]
        placeholders = ','.join([f"'{wid}'" for wid in work_ids])

        ref_query = f"""
            SELECT work_id, referenced_work_id
            FROM works_referenced_works
            WHERE work_id IN ({placeholders})
        """

        ref_records = await db_connection.fetch(ref_query)

        # 组织成字典
        refs_map = {}
        for rec in ref_records:
            work_id = rec['work_id']
            if work_id not in refs_map:
                refs_map[work_id] = []
            refs_map[work_id].append(rec['referenced_work_id'])

        # 添加到works中
        for work in works:
            work['referenced_works'] = refs_map.get(work['id'], [])

        if self.verbose:
            total_refs = sum(len(refs_map.get(w['id'], [])) for w in works)
            print(f"[DataManager] ✅ 获取了 {total_refs} 个被引文献ID")

        return works

    async def enrich_references(
        self,
        works: List[Dict],
        db_connection = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        为论文数据补充被引文献详情

        该方法会：
        1. 提取所有被引文献ID
        2. 优先从数据库获取详情
        3. 数据库缺失的从API补充
        4. 添加到原始数据的 referenced_works_details 字段

        Args:
            works: 论文数据列表（必须包含 referenced_works 字段）
            db_connection: 数据库连接（可选，用于优先查询）
            use_cache: 是否使用缓存

        Returns:
            补充了 referenced_works_details 的论文列表
        """
        from .works_extractor import WorksExtractor

        # 检查是否已有详情
        if works and works[0].get("referenced_works_details"):
            if self.verbose:
                print(f"[DataManager] 数据已包含被引文献详情")
            return works

        # 收集所有被引文献ID
        all_ref_ids = []
        for work in works:
            all_ref_ids.extend(work.get('referenced_works', []))

        unique_ref_ids = list(set(all_ref_ids))

        if self.verbose:
            print(f"[DataManager] 需要获取 {len(unique_ref_ids)} 篇被引文献详情...")

        if len(unique_ref_ids) == 0:
            if self.verbose:
                print(f"[DataManager] ⚠️  没有被引文献")
            return works

        # 获取被引文献详情
        ref_details_list = []

        # 优先使用数据库
        if db_connection:
            if self.verbose:
                print(f"[DataManager] 优先从数据库查找...")

            async def query_fn(sql):
                records = await db_connection.fetch(sql)
                return [dict(r) for r in records]

            db_extractor = WorksExtractor(query_fn=query_fn, auto_switch=False)
            db_result = await db_extractor.fetch_works_by_ids(
                work_ids=unique_ref_ids,
                force_db=True
            )

            ref_details_list = db_result['works']

            if self.verbose:
                print(f"[DataManager] 数据库找到 {len(ref_details_list)}/{len(unique_ref_ids)} 篇")

            # 检查缺失的，用API补充
            found_ids = set(ref['id'] for ref in ref_details_list)
            missing_ids = [ref_id for ref_id in unique_ref_ids if ref_id not in found_ids]

            if missing_ids:
                if self.verbose:
                    print(f"[DataManager] 从API补充 {len(missing_ids)} 篇...")

                try:
                    api_extractor = WorksExtractor()
                    api_result = await api_extractor.fetch_works_by_ids(
                        work_ids=missing_ids,
                        force_api=True
                    )
                    ref_details_list.extend(api_result['works'])

                    if self.verbose:
                        print(f"[DataManager] API补充了 {len(api_result['works'])} 篇")
                except Exception as e:
                    if self.verbose:
                        print(f"[DataManager] ⚠️  API补充失败: {e}")
        else:
            # 只能用API
            if self.verbose:
                print(f"[DataManager] 从API获取...")

            api_extractor = WorksExtractor()
            api_result = await api_extractor.fetch_works_by_ids(
                work_ids=unique_ref_ids,
                force_api=True
            )
            ref_details_list = api_result['works']

        if self.verbose:
            match_rate = len(ref_details_list) / len(unique_ref_ids) * 100
            print(f"[DataManager] ✅ 共获取 {len(ref_details_list)}/{len(unique_ref_ids)} 篇 ({match_rate:.1f}%)")

        # 构建字典
        ref_dict = {}
        for ref in ref_details_list:
            ref_id = ref['id']
            if isinstance(ref_id, str):
                ref_id = ref_id.replace("https://openalex.org/", "")
            ref_dict[ref_id] = ref

        # 添加详情到原始数据
        for work in works:
            work['referenced_works_details'] = [
                ref_dict[ref_id]
                for ref_id in work.get('referenced_works', [])
                if ref_id in ref_dict
            ]

        # 统计匹配率
        total_refs = sum(len(work.get('referenced_works', [])) for work in works)
        matched_refs = sum(len(work.get('referenced_works_details', [])) for work in works)
        match_rate = (matched_refs / total_refs * 100) if total_refs > 0 else 0

        if self.verbose:
            print(f"[DataManager] 引用匹配率: {match_rate:.1f}% ({matched_refs}/{total_refs})")

        return works

    async def prepare_dataset(
        self,
        # 查询参数（字典形式）
        filters: Optional[Dict] = None,
        # 数据增强选项
        include_references: bool = True,
        include_citations: bool = False,
        # 缓存和数据源控制
        data_source: str = "auto",
        db_connection = None,
        use_cache: bool = True,
        force_refetch: bool = False,
        cache_file: Optional[str] = None
    ) -> List[Dict]:
        """
        一站式数据准备接口

        该方法会完成完整的数据准备流程：
        1. 获取论文基本信息
        2. 可选：补充被引文献详情
        3. 可选：补充引用关系
        4. 自动缓存管理

        Args:
            filters: 查询过滤条件字典（与 fetch_works 相同）
            include_references: 是否包含被引文献详情
            include_citations: 是否包含引用关系（暂不支持）
            data_source: 数据源
            db_connection: 数据库连接
            use_cache: 是否使用缓存
            force_refetch: 是否强制重新获取
            cache_file: 自定义缓存文件路径

        Returns:
            完整的论文数据集

        Examples:
            # 需求1：按期刊筛选
            works = await manager.prepare_dataset(
                filters={
                    "source_name": "Scientometrics",
                    "publication_year": (2021, 2024),
                    "limit": 1000
                },
                include_references=True
            )

            # 需求2：按主题筛选
            works = await manager.prepare_dataset(
                filters={
                    "topic_name": "Language model",
                    "publication_year": (2022, 2024)
                },
                include_references=True
            )

            # 需求3：关键词+领域筛选
            works = await manager.prepare_dataset(
                filters={
                    "keywords": "benchmark",
                    "topic_name": "Artificial Intelligence",
                    "publication_year": (2021, 2024)
                },
                include_references=True
            )
        """
        # 步骤1: 获取论文数据
        works = await self.fetch_works(
            filters=filters,
            data_source=data_source,
            db_connection=db_connection,
            use_cache=use_cache,
            force_refetch=force_refetch,
            cache_file=cache_file
        )

        # 步骤2: 补充被引文献详情
        if include_references:
            works = await self.enrich_references(
                works=works,
                db_connection=db_connection,
                use_cache=use_cache
            )

            # 更新缓存（包含详情）
            if use_cache and not force_refetch:
                if cache_file:
                    self.save_to_cache(works, cache_file=cache_file)
                else:
                    # 使用 filters 生成缓存键
                    query_params = {'limit': 100, **(filters or {})}
                    cache_key = self._generate_cache_key(**query_params)
                    self.save_to_cache(works, cache_key=cache_key)

        # 步骤3: 补充引用关系（暂不实现）
        if include_citations:
            if self.verbose:
                print(f"[DataManager] ⚠️  include_citations 功能暂未实现")

        if self.verbose:
            print(f"[DataManager] ✅ 数据准备完成！")

        return works

    def clear_cache(
        self,
        cache_key: Optional[str] = None,
        cache_file: Optional[str] = None,
        clear_all: bool = False
    ):
        """
        清除缓存

        Args:
            cache_key: 要删除的缓存键
            cache_file: 要删除的缓存文件
            clear_all: 是否删除所有缓存
        """
        if clear_all:
            if self.cache_dir.exists():
                for f in self.cache_dir.glob("*.json"):
                    f.unlink()
                    if self.verbose:
                        print(f"[DataManager] ✅ 已删除: {f}")
        elif cache_file:
            cache_path = Path(cache_file)
            if cache_path.exists():
                cache_path.unlink()
                if self.verbose:
                    print(f"[DataManager] ✅ 已删除: {cache_path}")
        elif cache_key:
            cache_path = self._get_cache_path(cache_key)
            if cache_path.exists():
                cache_path.unlink()
                if self.verbose:
                    print(f"[DataManager] ✅ 已删除: {cache_path}")

    def get_dataset_info(self, works: List[Dict]) -> Dict:
        """
        获取数据集统计信息

        Args:
            works: 论文数据列表

        Returns:
            统计信息字典
        """
        if not works:
            return {}

        info = {
            'n_works': len(works),
            'year_range': None,
            'n_references': 0,
            'n_works_with_references': 0,
            'avg_references_per_work': 0,
            'has_reference_details': False
        }

        # 年份范围
        years = [w['publication_year'] for w in works if w.get('publication_year')]
        if years:
            info['year_range'] = (min(years), max(years))

        # 引用统计
        for work in works:
            refs = work.get('referenced_works', [])
            if refs:
                info['n_references'] += len(refs)
                info['n_works_with_references'] += 1

        if info['n_works'] > 0:
            info['avg_references_per_work'] = info['n_references'] / info['n_works']

        # 检查是否有详情
        if works[0].get('referenced_works_details'):
            info['has_reference_details'] = True

        return info


if __name__ == "__main__":
    print("WorksDataManager 模块已加载")
    print("使用示例：")
    print("  manager = WorksDataManager()")
    print("  works = await manager.fetch_works(keywords='AI', limit=100)")
    print("  works_with_refs = await manager.enrich_references(works)")
