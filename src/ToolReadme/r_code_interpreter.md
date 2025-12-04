# R Code Interpreter 使用指南

## 工具简介

R Code Interpreter 允许 Agent 动态生成并执行 R 代码，特别适用于：
- **文献计量分析** (使用 bibliometrix)
- **数据获取** (使用 openalexR)
- **统计分析和可视化**

**核心优势**：Agent 根据任务需求生成定制化的 R 代码，无需预定义固定流程。

## 快速开始

```python
from openalex_agent.tools.r_code_interpreter import RCodeInterpreter

interpreter = RCodeInterpreter()

# 执行 R 代码
r_code = """
library(openalexR)
works <- oa_fetch(entity = "works", search = "machine learning", per_page = 5)
print(works$display_name)
"""

result = await interpreter.execute(r_code, description="ml_search")
print(result["stdout"])
```

## 核心功能

### 1. 基础代码执行

```python
# 简单计算
code = """
x <- 1:100
cat("平均值:", mean(x), "\\n")
cat("标准差:", sd(x), "\\n")
"""
result = await interpreter.execute(code)
```

### 2. 带输入数据执行

```python
# 传递 Python 数据到 R
input_data = {
    "work_ids": ["W2755950973", "W2964141474"],
    "year_range": [2020, 2023]
}

code = """
cat("分析年份范围:", input_data$year_range[1], "-", input_data$year_range[2], "\\n")
"""

result = await interpreter.execute_with_data(code, input_data)
```

### 3. 生成图形

```python
code = """
png("test_output/my_plot.png", width=800, height=600)
x <- 1:10
y <- x^2
plot(x, y, type="b", main="My Plot")
dev.off()
cat("图形已保存\\n")
"""
result = await interpreter.execute(code)
```

## 常用 R 包示例

### openalexR - 数据获取

```r
library(openalexR)

# 设置 Polite Pool（速度提升10倍）
options(openalexR.mailto = "your.email@example.com")

# 获取数据
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",  # 引用某篇论文的文献
    from_publication_date = "2020-01-01",
    to_publication_date = "2023-12-31",
    per_page = 100
)

# 查看结果
cat("获取了", nrow(works), "条记录\\n")
```

### bibliometrix - 文献计量分析

```r
library(bibliometrix)

# 注意：bibliometrix 的 convert2df() 不支持 openalexR 的数据对象
# 使用已弃用但仍然可用的 oa2bibliometrix()
library(openalexR)
M <- oa2bibliometrix(works_data)

# 执行分析
results <- biblioAnalysis(M, sep = ";")

# 输出统计
cat("文档总数:", results$Articles, "\\n")
cat("作者总数:", length(results$Authors), "\\n")
```

### 数据可视化

```r
# 年度发文趋势
years_count <- table(M$PY)
png("test_output/trend.png", width=800, height=600)
barplot(years_count,
        main="Annual Publications",
        xlab="Year",
        ylab="Count",
        col="steelblue")
dev.off()
```

## Agent 集成示例

### 场景 1: 动态引文分析

Agent 可以根据用户请求生成定制化的分析代码：

**用户**: "分析引用了 bibliometrix 论文的最新文献的主题分布"

**Agent 生成的 R 代码**:
```r
library(openalexR)
library(bibliometrix)

# 1. 获取数据
options(openalexR.mailto = "email@example.com")
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    from_publication_date = "2023-01-01",
    per_page = 200
)

# 2. 转换格式
M <- oa2bibliometrix(works)

# 3. 主题分析
results <- biblioAnalysis(M)

# 4. 输出主题词
cat("\\n=== 高频关键词 ===\\n")
if (!is.null(results$DE)) {
    top_keywords <- head(sort(table(unlist(strsplit(results$DE, ";"))), decreasing=TRUE), 20)
    for (i in 1:length(top_keywords)) {
        cat(sprintf("%d. %s: %d\\n", i, names(top_keywords)[i], top_keywords[i]))
    }
}

# 5. 保存可视化
png("test_output/keyword_cloud.png", width=1000, height=800)
# ... 词云代码 ...
dev.off()
```

### 场景 2: 批量数据处理

```python
# Agent 可以根据多个 Work IDs 批量分析
work_ids = ["W2755950973", "W2964141474", "W3123456789"]

for work_id in work_ids:
    code = f"""
    library(openalexR)

    # 获取该论文的引用数据
    citations <- oa_fetch(
        entity = "works",
        cites = "{work_id}",
        per_page = 50
    )

    cat("Work ID: {work_id}\\n")
    cat("被引次数:", nrow(citations), "\\n\\n")
    """

    result = await interpreter.execute(code, description=f"citations_{work_id}")
```

## 最佳实践

### 1. 输出到文件

R 代码中始终将重要结果保存到文件：

```r
# 保存数据
write.csv(results_df, "test_output/results.csv", row.names=FALSE)

# 保存图形
png("test_output/figure.png", width=800, height=600)
# ... plot code ...
dev.off()

# 保存分析报告
sink("test_output/report.txt")
cat("=== 分析报告 ===\\n")
# ... analysis output ...
sink()
```

### 2. 错误处理

```r
# 在 R 代码中使用 tryCatch
result <- tryCatch({
    works <- oa_fetch(entity = "works", search = query)
    cat("成功获取", nrow(works), "条数据\\n")
    works
}, error = function(e) {
    cat("错误:", e$message, "\\n")
    NULL
})
```

### 3. 进度提示

对于长时间运行的任务，添加进度提示：

```r
cat("开始获取数据...\\n")
works <- oa_fetch(...)  # 可能需要几分钟
cat("数据获取完成！\\n")

cat("开始分析...\\n")
results <- biblioAnalysis(M)
cat("分析完成！\\n")
```

## openalexR 常用过滤器

```r
# 按引用关系
oa_fetch(entity = "works", cites = "W2755950973")  # 引用了某篇论文
oa_fetch(entity = "works", cited_by = "W2755950973")  # 被某篇论文引用

# 按时间
oa_fetch(
    entity = "works",
    from_publication_date = "2020-01-01",
    to_publication_date = "2023-12-31"
)

# 按主题
oa_fetch(entity = "works", concepts.id = "C41008148")  # Computer Science

# 按作者
oa_fetch(entity = "works", author.id = "A2755950973")

# 按期刊
oa_fetch(entity = "works", locations.source.id = "S137773608")

# 组合过滤
oa_fetch(
    entity = "works",
    search = "machine learning",
    from_publication_date = "2023-01-01",
    cited_by_count = ">100"  # 被引超过100次
)
```

## bibliometrix 核心分析

```r
library(bibliometrix)

# 基础统计分析
results <- biblioAnalysis(M, sep = ";")

# 主要信息
cat("文档数:", results$Articles, "\\n")
cat("作者数:", results$nAuthors, "\\n")
cat("期刊数:", length(results$Sources), "\\n")
cat("时间跨度:", min(results$Years), "-", max(results$Years), "\\n")

# 高产作者
top_authors <- head(sort(results$Authors, decreasing=TRUE), 10)

# 高影响论文
top_papers <- head(results$MostCitedPapers, 10)

# 协作网络分析
NetMatrix <- biblioNetwork(M, analysis = "collaboration", network = "authors")

# 引文网络
NetMatrix <- biblioNetwork(M, analysis = "co-citation", network = "references")
```

## 注意事项

1. **API 速率限制**
   - 无邮箱：10 请求/秒
   - Polite Pool (有邮箱)：100 请求/秒
   - 大数据集建议配置邮箱

2. **数据格式兼容性**
   - `bibliometrix::convert2df()` 暂不支持 openalexR 数据对象
   - 使用 `openalexR::oa2bibliometrix()` (虽然已弃用但仍可用)

3. **性能优化**
   - 小数据集 (<500 条)：直接使用 API
   - 大数据集 (>1000 条)：考虑使用本地数据库

4. **文件路径**
   - R 工作目录为项目根目录
   - 输出文件保存到 `test_output/`
   - 使用相对路径：`"test_output/result.csv"`

## 常见问题

### Q: 如何调试 R 代码？

A: 在 R 代码中添加 `cat()` 打印调试信息：
```r
cat("调试: 数据维度 =", dim(works), "\\n")
cat("调试: 前5个标题:\\n")
print(head(works$display_name, 5))
```

### Q: 执行超时怎么办？

A:
- 减少数据量 (调小 `per_page`)
- 增加超时时间（工具默认 120 秒）
- 将大任务拆分为多个小任务

### Q: 如何返回结果给 Python？

A: 保存为文件，在 Python 中读取：
```r
# R 代码
write.csv(results, "test_output/results.csv")
```

```python
# Python 代码
import pandas as pd
df = pd.read_csv("test_output/results.csv")
```

## 输出文件说明

执行后自动生成以下文件：

```
test_output/
├── r_{description}_{timestamp}_{id}.R      # R 脚本
├── output_{description}_{timestamp}_{id}.txt  # 标准输出
└── [用户自定义输出文件]                       # 图形、数据等
```

## 完整示例：端到端分析

```python
# Python 代码
from openalex_agent.tools.r_code_interpreter import RCodeInterpreter

interpreter = RCodeInterpreter()

# 定义完整的分析流程
full_analysis = """
library(openalexR)
library(bibliometrix)

# 配置
options(openalexR.mailto = "email@example.com")

# 1. 数据获取
cat("=== 第1步: 数据获取 ===\\n")
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    from_publication_date = "2020-01-01",
    per_page = 200
)
cat("获取了", nrow(works), "条记录\\n\\n")

# 2. 数据转换
cat("=== 第2步: 数据转换 ===\\n")
M <- oa2bibliometrix(works)
cat("转换完成，数据维度:", dim(M), "\\n\\n")

# 3. 文献计量分析
cat("=== 第3步: 文献计量分析 ===\\n")
results <- biblioAnalysis(M, sep = ";")
cat("分析完成\\n\\n")

# 4. 输出结果
cat("=== 分析结果 ===\\n")
cat("文档总数:", results$Articles, "\\n")
cat("作者总数:", length(results$Authors), "\\n")
cat("时间跨度:", min(results$Years), "-", max(results$Years), "\\n")

# 5. 保存可视化
png("test_output/analysis_trend.png", width=1000, height=600)
Y <- results$Years
barplot(Y, main="Annual Production", xlab="Year", ylab="Articles", col="steelblue")
dev.off()
cat("\\n图表已保存: test_output/analysis_trend.png\\n")
"""

# 执行分析
result = await interpreter.execute(full_analysis, description="full_analysis")

# 检查结果
if result["success"]:
    print("✓ 分析成功完成")
    print(f"✓ 执行时间: {result['execution_time']}s")
    print(f"✓ 输出:\n{result['stdout']}")
else:
    print("✗ 分析失败")
    print(f"✗ 错误:\n{result['stderr']}")
```

## 总结

R Code Interpreter 为 Agent 提供了强大的 R 语言执行能力，特别适合：
- ✅ 动态生成分析代码
- ✅ 文献计量分析 (bibliometrix)
- ✅ OpenAlex 数据获取 (openalexR)
- ✅ 统计分析和可视化

**核心理念**: Agent 作为"智能分析师"，根据任务需求灵活生成 R 代码，而不是调用预定义的固定流程。
