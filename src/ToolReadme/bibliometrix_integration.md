# bibliometrix 与 openalexR 集成指南

## 概述

本文档总结了 bibliometrix 包与 openalexR 数据集成的探索过程和最佳实践。

## 核心发现

### oa2bibliometrix() vs convert2df()

| 函数 | 状态 | 易用性 | 推荐度 |
|------|------|--------|--------|
| **oa2bibliometrix()** | 已弃用但**仍可用** | ⭐⭐⭐⭐⭐ 简单 | ✅ **推荐** |
| **convert2df()** | 官方推荐但**使用复杂** | ⭐⭐ 复杂 | ⚠️ 不推荐 |

## 方法对比

### ✅ 推荐：oa2bibliometrix()

**优势**：
- 一步转换，简单直接
- 专门为 openalexR 数据设计
- 稳定可靠，经过大量使用验证

**用法**：
```r
library(openalexR)

# 获取数据（默认 output = "tibble"）
works_data <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    per_page = 100
)

# 转换为 bibliometrix 格式
M <- oa2bibliometrix(works_data)

# 忽略弃用警告（该函数仍然完全可用）
M <- suppressWarnings(oa2bibliometrix(works_data))
```

**测试结果**：
- ✅ 成功转换 5,242 条记录
- ✅ 输出维度：5242 × 58

### ⚠️ convert2df() - 复杂且易错

**问题**：
1. 不支持直接传入 data.frame
2. 需要特定的数据格式（list）
3. 需要特定的文件格式（.RData，不是 .rds）
4. 需要3个步骤才能完成

**正确用法**（复杂）：
```r
# 步骤 1: 获取数据 - 必须指定 output = 'list'
works_list <- oa_fetch(
    entity = 'works',
    cites = "W2755950973",
    output = 'list',  # ← 关键！默认是 'tibble'
    verbose = FALSE
)

# 步骤 2: 保存为 .RData 文件
save(works_list, file = "works.RData")

# 步骤 3: 使用 convert2df 转换
M <- convert2df("works.RData",
                dbsource = "openalex_api",  # 注意：不是 "openalex"
                format = "api")
```

**常见错误**：

| 错误用法 | 错误信息 | 原因 |
|----------|----------|------|
| `convert2df(works_data, "openalex", "api")` | `file` is not one of the supported inputs | 传入了 data.frame 而不是文件路径 |
| `convert2df(works_data, "openalex_api", "api")` | bad 'file' argument | 同上 |
| `convert2df("file.rds", "openalex_api", "api")` | bad 'file' argument | 需要 .RData 而不是 .rds |
| `convert2df(data.frame, "openalex_api", "api")` | Must use existing variables | 数据类型必须是 list |

## 源码分析

### convert2df() 的内部逻辑

```r
# convert2df.R
switch(dbsource,
    openalex = {
        M <- csvOA2df(file)  # 处理 CSV 文件
    },
    openalex_api = {
        M <- apiOA2df(file)  # 处理 API 数据
    }
)

# apiOA2df() 内部
apiOA2df <- function(file) {
    DATA <- importOAFiles(file)  # ← 关键函数
    # ...
}

# importOAFiles() 期望的输入
importOAFiles <- function(file) {
    objName <- load(file)  # ← 使用 load()，期望 .RData 文件
    # 检查对象类型是否为 list
    if (!isTRUE(inherits(eval(parse(text = objName)), c("list")))) {
        message("...must set output='list' when use oa_fetch...")
    }
}
```

### 为什么会有 "bad 'file' argument" 错误

`importOAFiles()` 第一行调用 `load(file)`，这要求：
1. `file` 必须是**文件路径字符串**
2. 文件必须是 **`.RData` 或 `.rda`** 格式
3. 文件中的对象必须是 **`list`** 类型

## 数据格式对比

### openalexR 的两种输出格式

```r
# 格式 1: tibble (默认)
works_tibble <- oa_fetch(entity = "works", ...)
class(works_tibble)  # "tbl_df" "tbl" "data.frame"

# 格式 2: list (用于 convert2df)
works_list <- oa_fetch(entity = "works", output = "list", ...)
class(works_list)  # "list"
```

### 转换后的输出对比

| 方法 | 输入格式 | 输出维度 | 列数 |
|------|----------|----------|------|
| oa2bibliometrix() | tibble | 5242 × 58 | 58 |
| convert2df() | list → .RData | 2386 × 54 | 54 |

## 最佳实践

### 推荐工作流

```r
library(openalexR)
library(bibliometrix)

# 配置 Polite Pool（速度提升10倍）
options(openalexR.mailto = "your.email@example.com")

# 1. 获取数据
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    from_publication_date = "2020-01-01",
    per_page = 200
)

# 2. 转换为 bibliometrix 格式（忽略弃用警告）
M <- suppressWarnings(oa2bibliometrix(works))

# 3. 文献计量分析
results <- biblioAnalysis(M, sep = ";")

# 4. 查看结果
summary(results, k = 10)
```

### 注意：bibliometrix 分析可能失败

即使数据转换成功，`biblioAnalysis()` 有时会因数据兼容性问题失败：

```r
# 错误示例
results <- biblioAnalysis(M, sep = ";")
# Error: arguments must have same length
```

**解决方案**：使用更简单的分析方法

```r
# 方法 1: 直接统计（推荐）
# 年度分布
year_dist <- table(M$PY)
barplot(year_dist, main = "Annual Production")

# 高产作者
if (!is.null(M$AU)) {
    authors <- unlist(strsplit(M$AU, ";"))
    top_authors <- head(sort(table(authors), decreasing = TRUE), 10)
    print(top_authors)
}

# 方法 2: 使用 openalexR 原始数据分析
top_cited <- works[order(-works$cited_by_count), ][1:10,
    c("display_name", "publication_year", "cited_by_count")]
```

## 实际应用示例

### 示例 1: 引文趋势分析

```r
# 获取数据
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    from_publication_date = "2020-01-01",
    to_publication_date = "2024-12-31",
    per_page = 200
)

# 年度统计
year_counts <- table(works$publication_year)

# 可视化
png("test_output/bibliometrix_results/citation_trend.png",
    width = 800, height = 600)
barplot(year_counts,
        main = "Citation Trend Over Years",
        xlab = "Year",
        ylab = "Number of Citations",
        col = "steelblue")
dev.off()
```

### 示例 2: 被引最多的论文

```r
# 使用原始数据（更简单）
top_papers <- works %>%
    select(display_name, publication_year, cited_by_count, doi) %>%
    arrange(desc(cited_by_count)) %>%
    head(10)

print(top_papers)
```

## Agent 集成建议

在 R Code Interpreter 中使用时：

```python
# Python 代码
from openalex_agent.tools.r_code_interpreter import RCodeInterpreter

interpreter = RCodeInterpreter()

# Agent 生成的 R 代码
r_code = """
library(openalexR)

options(openalexR.mailto = "email@example.com")

# 获取数据
works <- oa_fetch(
    entity = "works",
    cites = "W2755950973",
    per_page = 100
)

# 简单统计（避免使用复杂的 bibliometrix 分析）
cat("总数:", nrow(works), "\\n")
cat("年份范围:", min(works$publication_year), "-",
    max(works$publication_year), "\\n")

# 年度分布
year_dist <- table(works$publication_year)
print(year_dist)

# 保存图表
png("test_output/bibliometrix_results/analysis.png", width=800, height=600)
barplot(year_dist, main="Annual Distribution", col="steelblue")
dev.off()
"""

result = await interpreter.execute(r_code, description="citation_analysis")
```

## 总结

**核心建议**：

1. ✅ **使用 oa2bibliometrix()**
   - 简单、稳定、可靠
   - 虽然标记为"弃用"，但完全可用

2. ❌ **避免 convert2df()**
   - 过于复杂，容易出错
   - 需要多个步骤和特定格式

3. ⚠️ **谨慎使用 biblioAnalysis()**
   - 可能因数据兼容性问题失败
   - 优先使用简单的直接统计

4. ✅ **优先使用 openalexR 原始数据**
   - 更灵活，更可控
   - 可以根据需求定制分析

## 参考资源

- openalexR 文档: https://docs.ropensci.org/openalexR/
- bibliometrix 文档: https://www.bibliometrix.org/
- 源码分析: `bibliometrix/R/convert2df.R`
- 测试代码: `test_output/bibliometrix_results/`
