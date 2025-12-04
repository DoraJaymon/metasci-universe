"""
Internal utilities for AuthorTool

内部依赖函数，供 author_query.py 使用
不对外暴露
"""

import time
import asyncpg
from typing import Dict, List, Optional, Any, Union
from pyalex import Works, Authors, config
from pathlib import Path
import sys

# 添加项目根目录
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# 导入配置
try:
    from config.db_config import PYALEX_EMAIL, DB_CONFIG
    if PYALEX_EMAIL:
        config.email = PYALEX_EMAIL
except ImportError:
    DB_CONFIG = None


# ==================== API 相关函数 ====================

def _safe_api_call(call_func, attempt: int = 1, sleep_time: float = 0.5,
                    retry_delay: float = 2, max_retries: int = 3,
                    verbose: bool = False):
    """安全的API调用，带重试逻辑"""
    if attempt > 1 and verbose:
        print(f"Retry attempt {attempt} of {max_retries}")

    if attempt > 1:
        wait_time = retry_delay * (2 ** (attempt - 2))
        if verbose:
            print(f"Waiting {wait_time:.2f} seconds before API call...")
        time.sleep(wait_time)
    elif sleep_time > 0:
        if verbose:
            print(f"Waiting {sleep_time:.2f} seconds before API call...")
        time.sleep(sleep_time)

    try:
        result = call_func()
        return result
    except Exception as e:
        error_msg = str(e)

        if "429" in error_msg or "Too Many Requests" in error_msg.lower():
            if attempt < max_retries:
                if verbose:
                    print("Rate limit hit (HTTP 429). Retrying with exponential backoff...")
                return _safe_api_call(call_func, attempt + 1, sleep_time,
                                     retry_delay, max_retries, verbose)
            else:
                raise Exception(f"Rate limit exceeded after {max_retries} attempts.")

        if any(code in error_msg for code in ["500", "502", "503", "504"]) or "timeout" in error_msg.lower():
            if attempt < max_retries:
                if verbose:
                    print("Temporary server error. Retrying...")
                return _safe_api_call(call_func, attempt + 1, sleep_time,
                                     retry_delay, max_retries, verbose)

        raise


def get_author_bio(doi: str,
                   author_position: int = 1,
                   verbose: bool = False,
                   return_all_authors: bool = False,
                   sleep_time: float = 1.0,
                   max_retries: int = 3,
                   retry_delay: float = 2.0,
                   email: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """从 OpenAlex 检索作者传记信息"""
    if email:
        config.email = email

    if verbose:
        print(f"Retrieving article information for DOI: {doi}")

    try:
        work_list = _safe_api_call(
            lambda: Works().filter(doi=doi).get(),
            sleep_time=sleep_time,
            retry_delay=retry_delay,
            max_retries=max_retries,
            verbose=verbose
        )
        work = work_list[0] if work_list else None
    except Exception as e:
        raise Exception(f"Error retrieving article: {str(e)}")

    if not work:
        raise Exception(f"No article found for DOI: {doi}")

    authorships = work.get('authorships', [])

    if not authorships:
        raise Exception("No author information found")

    if author_position > len(authorships):
        raise Exception(f"Author position ({author_position}) > total authors ({len(authorships)})")

    if verbose:
        print(f"Article found: {work.get('display_name', 'Unknown')}")
        print(f"Total authors: {len(authorships)}")

    # 返回所有作者
    if return_all_authors:
        if verbose:
            print(f"\nRetrieving information for all {len(authorships)} authors...")

        all_authors = []
        for i, authorship in enumerate(authorships, 1):
            author_info = authorship.get('author', {})
            if verbose:
                print(f"Processing author {i}/{len(authorships)}: {author_info.get('display_name', 'Unknown')}")

            author_id = author_info.get('id', '')
            if author_id:
                clean_id = author_id.replace('https://openalex.org/', '')

                try:
                    author_list = _safe_api_call(
                        lambda: Authors().filter(openalex_id=clean_id).get(),
                        sleep_time=sleep_time,
                        retry_delay=retry_delay,
                        max_retries=max_retries,
                        verbose=verbose
                    )
                    author_detail = author_list[0] if author_list else None

                    if author_detail:
                        enriched_author = _enrich_author_data(author_detail, authorship, work, i, doi)
                        all_authors.append(enriched_author)

                except Exception as e:
                    if verbose:
                        print(f"Error for author {i}: {str(e)}")

        return all_authors

    # 返回单个作者
    authorship = authorships[author_position - 1]
    author_info = authorship.get('author', {})
    author_id = author_info.get('id', '')

    if not author_id:
        raise Exception(f"Invalid author ID at position {author_position}")

    clean_id = author_id.replace('https://openalex.org/', '')

    if verbose:
        print(f"\nRetrieving info for author at position {author_position}: {author_info.get('display_name', 'Unknown')}")

    try:
        author_list = _safe_api_call(
            lambda: Authors().filter(openalex_id=clean_id).get(),
            sleep_time=sleep_time,
            retry_delay=retry_delay,
            max_retries=max_retries,
            verbose=verbose
        )
        author_detail = author_list[0] if author_list else None
    except Exception as e:
        raise Exception(f"Error retrieving author information: {str(e)}")

    if not author_detail:
        raise Exception(f"No information found for author at position {author_position}")

    enriched_author = _enrich_author_data(author_detail, authorship, work, author_position, doi)

    if verbose:
        print(f"\nSuccessfully retrieved: {author_detail.get('display_name', 'Unknown')}")

    return enriched_author


def _enrich_author_data(author_detail: Dict, authorship: Dict,
                        work: Dict, position: int, doi: str) -> Dict[str, Any]:
    """用论文特定信息丰富作者数据"""
    enriched = author_detail.copy()

    enriched['author_position_in_paper'] = position
    enriched['original_author_name'] = authorship.get('author', {}).get('display_name', '')
    enriched['is_corresponding'] = authorship.get('is_corresponding', False)
    enriched['author_position_type'] = authorship.get('author_position', '')

    institutions = authorship.get('institutions', [])
    if institutions:
        primary_inst = institutions[0]
        enriched['primary_affiliation'] = primary_inst.get('display_name', '')
        enriched['primary_affiliation_country'] = primary_inst.get('country_code', '')
        enriched['primary_affiliation_ror'] = primary_inst.get('ror', '')
    else:
        enriched['primary_affiliation'] = None
        enriched['primary_affiliation_country'] = None
        enriched['primary_affiliation_ror'] = None

    enriched['affiliation_raw'] = authorship.get('raw_affiliation_string', '')
    enriched['source_doi'] = doi
    enriched['source_title'] = work.get('display_name', '')
    enriched['query_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')

    return enriched


def get_authors_summary(doi: str,
                        verbose: bool = False,
                        sleep_time: float = 0.2,
                        max_retries: int = 3,
                        email: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取作者摘要（不查询详细档案，速度快）"""
    if verbose:
        print(f"Retrieving author summary for DOI: {doi}")

    if email:
        config.email = email

    try:
        work_list = _safe_api_call(
            lambda: Works().filter(doi=doi).get(),
            sleep_time=sleep_time,
            retry_delay=2,
            max_retries=max_retries,
            verbose=verbose
        )
        work = work_list[0] if work_list else None
    except Exception as e:
        raise Exception(f"Error retrieving article: {str(e)}")

    if not work:
        raise Exception(f"No article found for DOI: {doi}")

    authorships = work.get('authorships', [])

    summary_list = []
    for i, authorship in enumerate(authorships, 1):
        author_info = authorship.get('author', {})
        institutions = authorship.get('institutions', [])

        # 提取主要机构的详细信息
        primary_inst = institutions[0] if institutions else {}

        summary = {
            'position': i,
            'display_name': author_info.get('display_name', ''),
            'author_position_type': authorship.get('author_position', ''),
            'is_corresponding': authorship.get('is_corresponding', False),
            'orcid': author_info.get('orcid', ''),
            'openalex_id': author_info.get('id', ''),
            'primary_affiliation': primary_inst.get('display_name', '') if primary_inst else None,
            'primary_affiliation_country': primary_inst.get('country_code', '') if primary_inst else None,
            'primary_affiliation_ror': primary_inst.get('ror', '') if primary_inst else None,
            'primary_affiliation_type': primary_inst.get('type', '') if primary_inst else None,
            'raw_affiliation_string': authorship.get('raw_affiliation_string', '')
        }
        summary_list.append(summary)

    if verbose:
        print(f"Successfully retrieved summary for {len(summary_list)} authors")

    return summary_list


# ==================== 数据库相关函数 ====================

async def create_db_connection():
    """创建数据库连接"""
    if not DB_CONFIG:
        raise ValueError("Database configuration not found")
    return await asyncpg.connect(**DB_CONFIG)


async def query_author_by_id(author_id: str, conn=None) -> Optional[Dict[str, Any]]:
    """通过作者 ID 查询作者详情"""
    if not DB_CONFIG:
        raise ValueError("Database configuration not found")

    clean_id = author_id.replace('https://openalex.org/', '')
    should_close = False

    try:
        if conn is None:
            conn = await asyncpg.connect(**DB_CONFIG)
            should_close = True

        query = """
        SELECT id, orcid, display_name, display_name_alternatives,
               works_count, cited_by_count,
               last_known_institution, last_known_institution_ror,
               last_known_institution_display_name,
               last_known_institution_country_code,
               last_known_institution_type,
               works_api_url, updated_date
        FROM authors
        WHERE id = $1
        """

        row = await conn.fetchrow(query, clean_id)

        if not row:
            return None

        author = dict(row)

        # 处理 JSON 字段
        if author.get('display_name_alternatives'):
            try:
                import json
                if isinstance(author['display_name_alternatives'], str):
                    author['display_name_alternatives'] = json.loads(author['display_name_alternatives'])
            except:
                pass

        author['id'] = f"https://openalex.org/{clean_id}"

        return author

    finally:
        if should_close and conn:
            await conn.close()


async def query_authors_by_doi(doi: str, conn=None) -> List[Dict[str, Any]]:
    """通过 DOI 查询论文的所有作者"""
    if not DB_CONFIG:
        raise ValueError("Database configuration not found")

    should_close = False

    try:
        if conn is None:
            conn = await asyncpg.connect(**DB_CONFIG)
            should_close = True

        # 获取论文ID
        work_query = """
        SELECT id, display_name
        FROM works
        WHERE doi = $1 OR doi = $2
        """

        doi_url = f"https://doi.org/{doi}" if not doi.startswith('http') else doi
        doi_simple = doi.replace('https://doi.org/', '')

        work = await conn.fetchrow(work_query, doi_simple, doi_url)

        if not work:
            return []

        work_id = work['id'].replace('https://openalex.org/', '')

        # 查询作者
        authorship_query = """
        SELECT
            wa.author_id, wa.author_position,
            wa.institution_id, wa.raw_affiliation_string,
            a.orcid, a.display_name, a.display_name_alternatives,
            a.works_count, a.cited_by_count,
            a.last_known_institution, a.last_known_institution_ror,
            a.last_known_institution_display_name,
            a.last_known_institution_country_code,
            a.last_known_institution_type,
            i.display_name as institution_display_name,
            i.ror as institution_ror,
            i.country_code as institution_country_code,
            i.type as institution_type
        FROM works_authorships wa
        LEFT JOIN authors a ON wa.author_id = a.id
        LEFT JOIN institutions i ON wa.institution_id = i.id
        WHERE wa.work_id = $1
        ORDER BY
            CASE
                WHEN wa.author_position = 'first' THEN 1
                WHEN wa.author_position = 'middle' THEN 2
                WHEN wa.author_position = 'last' THEN 3
                ELSE 4
            END
        """

        rows = await conn.fetch(authorship_query, work_id)

        authors = []
        for idx, row in enumerate(rows, 1):
            author = {
                'id': row['author_id'],
                'orcid': row['orcid'],
                'display_name': row['display_name'],
                'display_name_alternatives': row['display_name_alternatives'],
                'works_count': row['works_count'],
                'cited_by_count': row['cited_by_count'],
                'author_position_in_paper': idx,
                'author_position_type': row['author_position'],
                'raw_affiliation_string': row['raw_affiliation_string'],
                'primary_affiliation': row['institution_display_name'],
                'primary_affiliation_country': row['institution_country_code'],
                'primary_affiliation_ror': row['institution_ror'],
                'primary_affiliation_type': row['institution_type'],
                'last_known_institution': row['last_known_institution'],
                'last_known_institution_ror': row['last_known_institution_ror'],
                'last_known_institution_display_name': row['last_known_institution_display_name'],
                'last_known_institution_country_code': row['last_known_institution_country_code'],
                'last_known_institution_type': row['last_known_institution_type'],
                'source_doi': doi,
                'source_title': work['display_name'],
                'data_source': 'database'
            }

            # 处理 JSON
            if author.get('display_name_alternatives'):
                try:
                    import json
                    if isinstance(author['display_name_alternatives'], str):
                        author['display_name_alternatives'] = json.loads(author['display_name_alternatives'])
                except:
                    pass

            authors.append(author)

        return authors

    finally:
        if should_close and conn:
            await conn.close()


async def get_author_with_position(doi: str, author_position: int = 1, conn=None) -> Optional[Dict[str, Any]]:
    """获取论文中特定位置的作者"""
    authors = await query_authors_by_doi(doi, conn)

    if not authors or author_position > len(authors):
        return None

    return authors[author_position - 1]


async def query_authors_batch(author_ids: List[str], conn=None) -> List[Dict[str, Any]]:
    """批量查询作者"""
    if not DB_CONFIG:
        raise ValueError("Database configuration not found")

    if not author_ids:
        return []

    clean_ids = [aid.replace('https://openalex.org/', '') for aid in author_ids]
    should_close = False

    try:
        if conn is None:
            conn = await asyncpg.connect(**DB_CONFIG)
            should_close = True

        query = """
        SELECT id, orcid, display_name, display_name_alternatives,
               works_count, cited_by_count,
               last_known_institution, last_known_institution_ror,
               last_known_institution_display_name,
               last_known_institution_country_code,
               last_known_institution_type,
               works_api_url, updated_date
        FROM authors
        WHERE id = ANY($1::varchar[])
        """

        rows = await conn.fetch(query, clean_ids)

        authors = []
        for row in rows:
            author = dict(row)

            if author.get('display_name_alternatives'):
                try:
                    import json
                    if isinstance(author['display_name_alternatives'], str):
                        author['display_name_alternatives'] = json.loads(author['display_name_alternatives'])
                except:
                    pass

            author['id'] = f"https://openalex.org/{author['id']}"
            authors.append(author)

        return authors

    finally:
        if should_close and conn:
            await conn.close()


async def search_authors_by_name(name: str, limit: int = 10, conn=None) -> List[Dict[str, Any]]:
    """通过名字搜索作者（模糊匹配）"""
    if not DB_CONFIG:
        raise ValueError("Database configuration not found")

    should_close = False

    try:
        if conn is None:
            conn = await asyncpg.connect(**DB_CONFIG)
            should_close = True

        query = """
        SELECT
            id, orcid, display_name, display_name_alternatives,
            works_count, cited_by_count,
            last_known_institution, last_known_institution_ror,
            last_known_institution_display_name,
            last_known_institution_country_code,
            last_known_institution_type,
            works_api_url, updated_date,
            CASE
                WHEN LOWER(display_name) = LOWER($1) THEN 1
                WHEN LOWER(display_name) LIKE LOWER($1 || '%') THEN 2
                WHEN LOWER(display_name) LIKE LOWER('%' || $1 || '%') THEN 3
                ELSE 4
            END as relevance
        FROM authors
        WHERE LOWER(display_name) LIKE LOWER('%' || $1 || '%')
        ORDER BY relevance, cited_by_count DESC
        LIMIT $2
        """

        rows = await conn.fetch(query, name, limit)

        authors = []
        for row in rows:
            author = dict(row)
            author.pop('relevance', None)

            if author.get('display_name_alternatives'):
                try:
                    import json
                    if isinstance(author['display_name_alternatives'], str):
                        author['display_name_alternatives'] = json.loads(author['display_name_alternatives'])
                except:
                    pass

            author['id'] = f"https://openalex.org/{author['id']}"
            authors.append(author)

        return authors

    finally:
        if should_close and conn:
            await conn.close()
