# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MetaSciToolUniverse** is a toolkit for scientometrics analysis and literature review, designed for AI agent consumption (primarily OpenAlex Agent). openalex agent 用于辅助AI for Research与科学计量.


## Development Workflow

### Package Management
```bash
# Using uv for dependency management
uv pip install -e .
uv pip install -e ".[dev]"  # With dev dependencies
```

## 数据获取
有两种数据获取方式, 1. 通过API(pyalex). 2. 通过本地数据库PostgreSQL直接连接并获取. 
一般来说, 如果预估调用API次数大于1000,则调用本地数据库；如果是小批量数据或是最近的数据(2025年4月之后的)需要使用API；

## 文件管理规范
1. 数据库信息在MetaSciToolUniverse/config/db_config.py中
2. 核心文档放在doc/下
3. 核心代码放在src/下
4. 通过uv实现对python包的安装与管理
6. 所有jupyter之前都需要通过设置%load_ext autoreload, %autoreload 2启用自动重载

## 测试规范
1. 测试非必要时可以不单独写测试代码,也可以不需要有预期输出,我可以自己手工检查
2. 测试的输出需在该类工具的文件夹下新建文件夹和文件保存
3. 'MetaSciToolUniverse/src/require_test.md'这个文件是我用于记录工具要求和测试要求的文档,不要修改它!!
4. 测试代码需放在每个工具文件夹下的testpy中,例如'MetaSciToolUniverse/src/DataExtractorTool/testpy'
5. 最后为了可以直观看到效果或方便修改参数和调试,有的功能需要在MetaSciToolUniverse/pyNoteBook中的notebook中写代码调用
   1. jupyter之中写的不是正式的测试代码,只是给人以直观理解就行,其次是期忘仿照LLM调用工具的情况,因此正常调用不要写太多代码
6. 在数据分析阶段,优先使用本地已存的数据进行分析避免再次通过API或数据库获取数据!
   1. 请使用数据:MetaSciToolUniverse/data/works_cache/works_query_all_1bf7ea910a2a.json (21到24年所有Scientometrics期刊的论文)；MetaSciToolUniverse/data/works_cache/works_query_5000_129d16cc9c10.json(24年topic是'Natural Language Processing Techniques'的5000篇论文)
7. 非必要不使用keyword在本地数据库搜索,因为搜索效率很慢