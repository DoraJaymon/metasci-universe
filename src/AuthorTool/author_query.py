"""
AuthorQuery - 统一作者查询类

提供统一的查询入口，智能选择API/数据库，支持灵活的输出格式。

特性:
- 单一查询入口 query()
- 支持 DOI / 作者ID 输入
- 批量查询(>200)自动用DB，找不到回退API
- 灵活输出: summary / full / 自定义字段
- DOI查询支持指定作者位置

使用示例:
    # 初始化
    aq = AuthorQuery(verbose=True)

    # 查询单篇论文的第一作者(摘要)
    result = await aq.query("10.1016/j.joi.2017.08.007")

    # 查询单篇论文的第二作者(详细)
    result = await aq.query("10.1016/j.joi.2017.08.007", author_position=2, detail_level='full')

    # 批量查询多篇论文
    dois = ["10.1016/j.joi.2017.08.007", "10.1007/s11192-009-0146-3"]
    results = await aq.query(dois)

    # 通过作者ID查询
    result = await aq.query("A5069892096", detail_level='full')

    # 自定义返回字段
    result = await aq.query("10.1016/j.joi.2017.08.007", fields=['display_name', 'works_count', 'cited_by_count'])
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
import sys

# 添加项目根目录到路径
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 导入配置
try:
    from config.db_config import PYALEX_EMAIL
    from pyalex import config
    if PYALEX_EMAIL:
        config.email = PYALEX_EMAIL
except ImportError:
    pass

# 导入内部依赖函数
from src.AuthorTool._internal import (
    get_author_bio,
    get_authors_summary,
    _safe_api_call,
    query_author_by_id,
    query_authors_by_doi,
    get_author_with_position,
    query_authors_batch,
    create_db_connection,
    search_authors_by_name as _search_authors_by_name
)


class AuthorQuery:
    """
    统一作者查询类

    提供单一查询入口，智能路由API/数据库，支持灵活输出。
    """

    # 摘要字段（默认输出）
    SUMMARY_FIELDS = [
        'id', 'display_name', 'orcid',
        'works_count', 'cited_by_count',
        'author_position_in_paper', 'author_position_type',
        'is_corresponding', 'primary_affiliation',
        'primary_affiliation_country',
        'data_source', 'query_timestamp'  # 元数据
    ]

    def __init__(self, email: Optional[str] = None, verbose: bool = False):
        """
        初始化查询器

        Args:
            email: OpenAlex API 邮箱（提高速率限制）
            verbose: 是否打印详细日志
        """
        self.email = email
        self.verbose = verbose

        # 设置 PyAlex 邮箱
        if email:
            try:
                from pyalex import config
                config.email = email
            except ImportError:
                pass

    async def query(
        self,
        identifiers: Union[str, List[str]],
        author_position: int = 1,
        all_authors: bool = False,
        detail_level: str = 'summary',
        fields: Optional[List[str]] = None,
        batch_threshold: int = 200,
        force_source: Optional[str] = None
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        统一查询入口

        Args:
            identifiers:
                - 单个DOI: "10.1016/j.joi.2017.08.007"
                - 多个DOI: ["10.1016/...", "10.1007/..."]
                - 单个作者ID: "A5069892096"
                - 多个作者ID: ["A5069892096", "A5049136342"]
            author_position: 如果是DOI，指定作者位置（1=第一作者，2=第二作者，...）
                - 当 all_authors=True 时此参数被忽略
            all_authors: 如果是DOI，返回所有共同作者（默认False）
                - True: 返回论文的所有作者列表
                - False: 只返回指定位置的作者
            detail_level: 输出详细程度（默认'summary'）
                - 'basic': 基本信息（只调用Works API，不查作者档案，速度快10倍）
                  包含：姓名、ORCID、位置、机构等基本字段
                - 'summary': 标准信息（查询作者档案，返回核心字段）
                  包含：works_count, cited_by_count 等文献计量指标
                - 'full': 完整信息（查询作者档案，返回所有字段）
                  包含：h-index, i10-index, topics, counts_by_year 等所有字段
                - 注意：'basic' 只对DOI查询有效，作者ID查询会自动使用 'summary'
            fields: 自定义返回字段列表（如果指定，覆盖 detail_level）
                - 例如: ['display_name', 'works_count', 'cited_by_count']
            batch_threshold: 批量查询阈值，超过此数量自动用数据库（默认200）
            force_source: 强制使用数据源
                - 'api': 强制使用 API
                - 'db': 强制使用数据库
                - None: 自动选择（默认）

        Returns:
            - 如果输入单个identifier且all_authors=False: 返回单个作者字典
            - 其他情况: 返回作者字典列表

        Examples:
            # 查询单篇论文第一作者（标准信息）
            result = await aq.query("10.1016/j.joi.2017.08.007")

            # 查询所有共同作者（基本信息，速度快）
            authors = await aq.query(
                "10.1016/j.joi.2017.08.007",
                all_authors=True,
                detail_level='basic'
            )

            # 查询所有共同作者（完整信息）
            authors = await aq.query(
                "10.1016/j.joi.2017.08.007",
                all_authors=True,
                detail_level='full'
            )

            # 批量查询多篇论文（自动用DB）
            results = await aq.query([
                "10.1016/j.joi.2017.08.007",
                "10.1007/s11192-009-0146-3"
            ])

            # 通过作者ID查询
            result = await aq.query("A5069892096", detail_level='full')

            # 自定义字段
            result = await aq.query("10.1016/j.joi.2017.08.007",
                                   fields=['display_name', 'works_count', 'h_index'])
        """
        # 参数验证
        if not identifiers:
            raise ValueError("identifiers 不能为空")

        if detail_level not in ['basic', 'summary', 'full']:
            raise ValueError("detail_level 必须是 'basic', 'summary' 或 'full'")

        if force_source and force_source not in ['api', 'db']:
            raise ValueError("force_source 必须是 'api', 'db' 或 None")

        # 统一转为列表处理
        is_single = isinstance(identifiers, str)
        id_list = [identifiers] if is_single else identifiers

        # 判断查询类型
        is_author_ids = all(self._is_author_id(id_) for id_ in id_list)
        is_dois = all(not self._is_author_id(id_) for id_ in id_list)

        if not (is_author_ids or is_dois):
            raise ValueError("identifiers 必须全部是DOI或全部是作者ID，不能混合")

        # 作者ID查询不支持 all_authors 和 basic 模式
        if is_author_ids:
            if all_authors:
                if self.verbose:
                    print("警告: 作者ID查询不支持 all_authors 参数，将被忽略")
                all_authors = False
            if detail_level == 'basic':
                if self.verbose:
                    print("警告: 作者ID查询不支持 basic 模式，自动切换到 summary")
                detail_level = 'summary'

        # Basic 模式：只从 Works API 获取基本信息（不查作者档案）
        if detail_level == 'basic' and is_dois:
            if self.verbose:
                print("使用 basic 模式：只获取基本信息，不查询作者详细档案")

            result = []
            for doi in id_list:
                try:
                    authors = await self._query_doi_quick(doi)
                    if all_authors:
                        result.extend(authors)
                    else:
                        # 只返回指定位置的作者
                        if author_position <= len(authors):
                            result.append(authors[author_position - 1])
                except Exception as e:
                    if self.verbose:
                        print(f"Basic 模式查询失败 {doi}: {str(e)}")

            # 处理输出格式
            if result:
                if fields:
                    result = self._filter_fields(result, fields)
                # basic 模式已经是基本信息，不需要再过滤

            # 返回
            if is_single and not all_authors:
                return result[0] if result else None
            else:
                return result

        # 决定数据源
        query_count = len(id_list)

        if force_source:
            source = force_source
            if self.verbose:
                print(f"强制使用数据源: {source}")
        else:
            # 自动选择：批量查询(>threshold) 用DB，否则用API
            if query_count >= batch_threshold:
                source = 'db'
                if self.verbose:
                    print(f"批量查询({query_count}个) >= {batch_threshold}，自动使用数据库")
            else:
                source = 'api'
                if self.verbose:
                    print(f"小批量查询({query_count}个) < {batch_threshold}，使用API")

        # 执行查询
        if query_count == 1:
            # 单个查询
            result = await self._query_single(
                id_list[0], author_position, source, is_author_ids, all_authors
            )
        else:
            # 批量查询
            result = await self._query_batch(
                id_list, author_position, source, is_author_ids, all_authors
            )

        # 处理输出格式
        if result:
            # 应用字段过滤
            if fields:
                result = self._filter_fields(result, fields)
            elif detail_level == 'summary':
                result = self._to_summary(result)
            # detail_level == 'full' 则返回完整数据

        # 返回单个或列表
        if is_single and not all_authors:
            return result[0] if result else None
        else:
            return result

    def _is_author_id(self, identifier: str) -> bool:
        """
        判断是否为作者ID

        Args:
            identifier: 标识符

        Returns:
            True: 作者ID (如 'A5069892096' 或 'https://openalex.org/A5069892096')
            False: DOI (如 '10.1016/...' 或 'https://doi.org/...')
        """
        identifier = identifier.strip()

        # 检查是否为 OpenAlex 作者 ID
        if identifier.startswith('https://openalex.org/A') or identifier.startswith('A'):
            return True

        # 检查是否为 DOI
        if identifier.startswith('10.') or identifier.startswith('https://doi.org/'):
            return False

        # 默认判断为 DOI
        return False

    async def _query_single(
        self,
        identifier: str,
        position: int,
        source: str,
        is_author_id: bool,
        all_authors: bool = False
    ) -> List[Dict[str, Any]]:
        """
        查询单个标识符

        Args:
            identifier: DOI 或 作者ID
            position: 作者位置（仅DOI有效）
            source: 'api' 或 'db'
            is_author_id: 是否为作者ID
            all_authors: 是否返回所有作者（仅DOI有效）

        Returns:
            包含作者的列表
        """
        if self.verbose:
            type_str = "作者ID" if is_author_id else "DOI"
            print(f"\n查询{type_str}: {identifier}")
            if all_authors and not is_author_id:
                print("  返回所有共同作者")

        try:
            if source == 'api':
                # 使用 API
                if is_author_id:
                    result = await self._query_author_by_id_api(identifier)
                else:
                    result = await self._query_by_doi_api(identifier, position, return_all=all_authors)
            else:
                # 使用数据库，失败则回退到 API
                try:
                    if is_author_id:
                        result = await self._query_author_by_id_db(identifier)
                    else:
                        result = await self._query_by_doi_db(identifier, position, return_all=all_authors)

                    # 如果DB找不到，回退到API
                    if not result:
                        if self.verbose:
                            print("  数据库中未找到，回退到API...")
                        if is_author_id:
                            result = await self._query_author_by_id_api(identifier)
                        else:
                            result = await self._query_by_doi_api(identifier, position, return_all=all_authors)

                except Exception as e:
                    if self.verbose:
                        print(f"  数据库查询失败: {str(e)}")
                        print("  回退到API...")
                    if is_author_id:
                        result = await self._query_author_by_id_api(identifier)
                    else:
                        result = await self._query_by_doi_api(identifier, position, return_all=False)

            return [result] if result else []

        except Exception as e:
            if self.verbose:
                print(f"  查询失败: {str(e)}")
            return []

    async def _query_batch(
        self,
        identifiers: List[str],
        position: int,
        source: str,
        is_author_id: bool,
        all_authors: bool = False
    ) -> List[Dict[str, Any]]:
        """
        批量查询多个标识符

        Args:
            identifiers: DOI列表 或 作者ID列表
            position: 作者位置（仅DOI有效）
            source: 'api' 或 'db'
            is_author_id: 是否为作者ID
            all_authors: 是否返回所有作者（仅DOI有效）

        Returns:
            作者字典列表
        """
        if self.verbose:
            type_str = "作者ID" if is_author_id else "DOI"
            print(f"\n批量查询 {len(identifiers)} 个{type_str}")
            if all_authors and not is_author_id:
                print("  返回所有共同作者")

        results = []

        if source == 'api':
            # API 批量查询（逐个）
            for i, identifier in enumerate(identifiers, 1):
                if self.verbose:
                    print(f"[{i}/{len(identifiers)}] 查询: {identifier}")

                try:
                    if is_author_id:
                        result = await self._query_author_by_id_api(identifier)
                        if result:
                            results.append(result)
                    else:
                        result = await self._query_by_doi_api(identifier, position, return_all=all_authors)
                        if result:
                            if all_authors:
                                results.extend(result)  # 扩展列表
                            else:
                                results.append(result)  # 添加单个

                except Exception as e:
                    if self.verbose:
                        print(f"  查询失败: {str(e)}")

        else:
            # 数据库批量查询（高效）
            try:
                conn = await create_db_connection()

                try:
                    if is_author_id:
                        # 批量查询作者ID
                        db_results = await query_authors_batch(identifiers, conn)
                        results = db_results

                        # 找出DB中没有的ID，用API补充
                        found_ids = {r['id'].replace('https://openalex.org/', '') for r in db_results}
                        missing_ids = [
                            id_ for id_ in identifiers
                            if id_.replace('https://openalex.org/', '') not in found_ids
                        ]

                        if missing_ids:
                            if self.verbose:
                                print(f"  数据库缺失 {len(missing_ids)} 个作者，用API补充...")

                            for missing_id in missing_ids:
                                try:
                                    result = await self._query_author_by_id_api(missing_id)
                                    if result:
                                        results.append(result)
                                except Exception as e:
                                    if self.verbose:
                                        print(f"  API补充失败 {missing_id}: {str(e)}")

                    else:
                        # 批量查询DOI
                        for i, doi in enumerate(identifiers, 1):
                            if self.verbose:
                                print(f"[{i}/{len(identifiers)}] 查询DOI: {doi}")

                            try:
                                result = await self._query_by_doi_db(doi, position, return_all=all_authors, conn=conn)

                                # 如果DB找不到，用API补充
                                if not result:
                                    if self.verbose:
                                        print(f"  数据库未找到，用API补充...")
                                    result = await self._query_by_doi_api(doi, position, return_all=all_authors)

                                if result:
                                    if all_authors:
                                        results.extend(result)  # 扩展列表
                                    else:
                                        results.append(result)  # 添加单个

                            except Exception as e:
                                if self.verbose:
                                    print(f"  查询失败: {str(e)}")

                finally:
                    await conn.close()

            except Exception as e:
                if self.verbose:
                    print(f"数据库批量查询失败: {str(e)}")
                    print("回退到API批量查询...")

                # 完全回退到API
                for i, identifier in enumerate(identifiers, 1):
                    if self.verbose:
                        print(f"[{i}/{len(identifiers)}] API查询: {identifier}")

                    try:
                        if is_author_id:
                            result = await self._query_author_by_id_api(identifier)
                            if result:
                                results.append(result)
                        else:
                            result = await self._query_by_doi_api(identifier, position, return_all=all_authors)
                            if result:
                                if all_authors:
                                    results.extend(result)  # 扩展列表
                                else:
                                    results.append(result)  # 添加单个

                    except Exception as e:
                        if self.verbose:
                            print(f"  查询失败: {str(e)}")

        if self.verbose:
            print(f"\n批量查询完成: 成功 {len(results)}/{len(identifiers)}")

        return results

    async def _query_by_doi_api(
        self,
        doi: str,
        position: int,
        return_all: bool = False
    ) -> Optional[Dict[str, Any]]:
        """通过DOI从API查询"""
        # 在事件循环中运行同步函数
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: get_author_bio(
                doi=doi,
                author_position=position,
                verbose=False,
                return_all_authors=return_all,
                email=self.email
            )
        )
        return result

    async def _query_by_doi_db(
        self,
        doi: str,
        position: int,
        return_all: bool = False,
        conn=None
    ) -> Optional[Dict[str, Any]]:
        """通过DOI从数据库查询"""
        should_close = False

        try:
            if conn is None:
                conn = await create_db_connection()
                should_close = True

            if return_all:
                authors = await query_authors_by_doi(doi, conn)
                return authors
            else:
                author = await get_author_with_position(doi, position, conn)
                return author

        finally:
            if should_close and conn:
                await conn.close()

    async def _query_author_by_id_api(self, author_id: str) -> Optional[Dict[str, Any]]:
        """通过作者ID从API查询"""
        from pyalex import Authors

        # 清理ID
        clean_id = author_id.replace('https://openalex.org/', '')

        # 在事件循环中运行同步API调用
        loop = asyncio.get_event_loop()

        def api_call():
            return _safe_api_call(
                lambda: Authors().filter(openalex_id=clean_id).get(),
                sleep_time=0.5,
                verbose=self.verbose
            )

        author_list = await loop.run_in_executor(None, api_call)

        if author_list:
            author = author_list[0]
            # 添加元数据
            author['query_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            author['data_source'] = 'api'
            return author

        return None

    async def _query_author_by_id_db(self, author_id: str) -> Optional[Dict[str, Any]]:
        """通过作者ID从数据库查询"""
        author = await query_author_by_id(author_id)

        if author:
            author['query_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            author['data_source'] = 'database'

        return author

    def _to_summary(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        转换为摘要格式（只包含关键字段）

        Args:
            data: 单个作者字典或列表

        Returns:
            摘要格式的数据
        """
        if isinstance(data, list):
            return [self._to_summary_single(item) for item in data]
        else:
            return self._to_summary_single(data)

    def _to_summary_single(self, author: Dict[str, Any]) -> Dict[str, Any]:
        """转换单个作者为摘要格式"""
        summary = {}
        for field in self.SUMMARY_FIELDS:
            if field in author:
                summary[field] = author[field]
            else:
                # 处理一些字段的别名
                if field == 'author_position_in_paper' and 'position' in author:
                    summary[field] = author['position']
                elif field == 'is_corresponding' and field not in author:
                    summary[field] = False  # 默认值

        return summary

    def _filter_fields(
        self,
        data: Union[Dict[str, Any], List[Dict[str, Any]]],
        fields: List[str]
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        过滤字段（只返回指定字段）

        Args:
            data: 单个作者字典或列表
            fields: 要保留的字段列表

        Returns:
            过滤后的数据
        """
        if isinstance(data, list):
            return [self._filter_fields_single(item, fields) for item in data]
        else:
            return self._filter_fields_single(data, fields)

    def _filter_fields_single(
        self,
        author: Dict[str, Any],
        fields: List[str]
    ) -> Dict[str, Any]:
        """过滤单个作者的字段"""
        filtered = {}
        for field in fields:
            if field in author:
                filtered[field] = author[field]
            # 处理嵌套字段（如 summary_stats.h_index）
            elif '.' in field:
                parts = field.split('.')
                value = author
                try:
                    for part in parts:
                        value = value[part]
                    filtered[field] = value
                except (KeyError, TypeError):
                    pass

        return filtered

    async def _query_doi_quick(self, doi: str) -> List[Dict[str, Any]]:
        """
        快速查询DOI的所有作者（不查询详细档案）

        Args:
            doi: 论文DOI

        Returns:
            作者基本信息列表
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: get_authors_summary(
                doi=doi,
                verbose=False,
                email=self.email
            )
        )

        # 添加元数据
        for author in result:
            author['query_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
            author['data_source'] = 'api_quick'

        return result

    async def search_by_name(
        self,
        name: str,
        limit: int = 10,
        detail_level: str = 'summary',
        fields: Optional[List[str]] = None,
        use_db: bool = True
    ) -> List[Dict[str, Any]]:
        """
        按名字搜索作者（模糊匹配）

        Args:
            name: 作者名字（支持部分匹配）
            limit: 返回结果数量限制（默认10）
            detail_level: 输出详细程度
                - 'summary': 摘要（默认）
                - 'full': 完整信息
            fields: 自定义返回字段列表（如果指定，覆盖 detail_level）
            use_db: 是否使用数据库（默认True，速度快）

        Returns:
            作者信息列表（按相关度和引用数排序）

        Examples:
            # 搜索作者
            authors = await aq.search_by_name("Massimo Aria", limit=10)

            # 搜索并返回详细信息
            authors = await aq.search_by_name(
                "Aria",
                limit=20,
                detail_level='full'
            )

            # 自定义字段
            authors = await aq.search_by_name(
                "Aria",
                fields=['display_name', 'works_count', 'cited_by_count']
            )
        """
        if self.verbose:
            print(f"按名字搜索: {name} (最多{limit}个结果)")

        if use_db:
            try:
                # 使用数据库搜索
                authors = await _search_authors_by_name(name, limit=limit)

                if self.verbose:
                    print(f"找到 {len(authors)} 位作者")

                # 处理输出格式
                if authors:
                    if fields:
                        authors = self._filter_fields(authors, fields)
                    elif detail_level == 'summary':
                        authors = self._to_summary(authors)

                return authors

            except Exception as e:
                if self.verbose:
                    print(f"数据库搜索失败: {str(e)}")
                    print("数据库搜索暂不支持，请使用API查询特定作者ID")
                return []
        else:
            if self.verbose:
                print("API不支持按名字搜索，请使用数据库（use_db=True）")
            return []


# 便捷函数（兼容旧接口）
async def query_authors(
    identifiers: Union[str, List[str]],
    author_position: int = 1,
    detail_level: str = 'summary',
    fields: Optional[List[str]] = None,
    verbose: bool = False
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """
    便捷函数：查询作者信息

    这是 AuthorQuery.query() 的快捷方式，无需手动创建实例。

    Args:
        identifiers: DOI 或 作者ID（单个或列表）
        author_position: 作者位置（默认1）
        detail_level: 'summary' 或 'full'
        fields: 自定义字段列表
        verbose: 是否打印详细日志

    Returns:
        作者信息字典或列表

    Examples:
        # 查询单篇论文第一作者
        result = await query_authors("10.1016/j.joi.2017.08.007")

        # 批量查询
        results = await query_authors([
            "10.1016/j.joi.2017.08.007",
            "10.1007/s11192-009-0146-3"
        ], verbose=True)
    """
    aq = AuthorQuery(verbose=verbose)
    return await aq.query(
        identifiers=identifiers,
        author_position=author_position,
        detail_level=detail_level,
        fields=fields
    )
