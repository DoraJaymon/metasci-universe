## Tools
1. 论文数据的提取工具, 需要实现两种方式:1. 最新或小批量数据, 利用pyalex. 2. 大批量数据, 利用本地数据库连接；关于这两种方式的实现可以参考MetaSciToolUniverse/src/DataExtractorTool/get_citations.py. 需要考虑多种查询过滤包括但不限于主题,领域,年份等, pyalex可以参考MetaSciToolUniverse/docs/pyalex使用指南/PyAlex完全使用指南.md,；两种数据获取方式需要对应；
   1. 测试这两种方式, 但是大批量数据也尽量不要超过10000条数据；
   2. 测试用例可以在'科学计量学','AI for Education'等我感兴趣的领域进行选取
   3. 测试代码尽量与工具代码写在一个文件中
   --------
   11.17新需求
   目前还没有实现的是1. 通过API进行批量数据获取,使用cursor分页(当数据大于200时就需要分页读取), 可以阅读RefRepo/pyalex的文档. 2.通过本地数据库获取数据
2. 基本文献计量分析工具: 我们现在已经有了论文数据提取工具了,接下来实现的是对获取的论文数据进行基本描述性统计分析,可以包括以下的数据特征:
   - Annual scientific production
   - Most productive authors
   - Most cited manuscripts
   - Most relevant sources (journals)
   - Most frequent keywords
  你需要在MetaSciToolUniverse/src/CitationAnalysisTool中开发, 返回的是一个字典
  - 测试的时候可以先保存一批数据在data中,便于之后复用
  - 测试用例可以是"量化交易","量化投资"."AI+金融"相关的话题
3. RPYS:你分析RefRepo/bibliometrix项目中RPYS的实现,我想在我的MetaSciToolUniverse项目中复现这个工具
4. 大批量论文获取的几种用户需求:
   1. 很少有用关键词直接在全库中搜索,如果不限定领域和主题则没有意义
   2. 因此,一开始很多的论文数据提取是建立在前期初筛上
   3. 一个典型的筛选是期刊,大多数人的活动范围是从期刊到期刊
   4. 再一个筛选是年份,新的更有价值
   --------------------------------------------------------------------
   综上所述,我在此模拟一些批量数据获取的需求用于测试数据获取与管理的入口: WorksDataManager
   1. 获取2021年以来在scientometrics, journal of informetrics, JASIST上发表的论文；缓存到本地,保留必要的元数据信息
   2. 获取主题是"Language model"的2022年以来的论文(注意:用topic name进行筛选搜索)的所有论文；缓存到本地,保留必要的元数据信息
   3. 获取2021年以来有关键词(用keyword搜索)"benchmark"的论文,且是计算机或AI领域；缓存到本地,保留必要的元数据信息
5. 主题类工具实现:
   1. 主要使用的主题建模工具是bertopic；在MetaSciToolUniverse/src/TopicTool中写一个类；你可以借鉴参考pybibx中实现的主题建模类的功能,包括可视化；但是你需要进行一些修改,例如在可视化时,需要写明topic,而不是用topic_1这样替代；其次,展示主题分布的柱状图请使用类似bibfile.get_top_ngrams()的风格；使用数据"MetaSciToolUniverse/data/works_cache/works_query_all_1bf7ea910a2a.json"进行测试.