# MetaSci Universe - 快速开始指南

## 📦 包已配置完成！

你的项目现在已经成功打包为 **metasci-universe**，可以优雅地被其他项目调用。

## ✅ 完成的配置

1. **pyproject.toml** - 包配置文件，定义了包名、版本、依赖等
2. **MANIFEST.in** - 指定要包含的非Python文件
3. **src/__init__.py** - 包入口，导出主要工具类
4. **src/metasci_universe.py** - 统一的导入接口模块
5. **README.md** - 详细的使用文档
6. **docs/MIGRATION_GUIDE.md** - OpenAlex Agent 迁移指南

## 🚀 在本项目中使用

### 开发模式安装（已安装）

```bash
cd /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse
uv pip install -e .
```

### 验证安装

```bash
python -c "import metasci_universe; print(metasci_universe.__version__)"
# 输出: 0.1.0
```

### 导入和使用

```python
# 统一导入接口
from metasci_universe import (
    WorksExtractor,      # 数据提取
    FindWork,            # 论文搜索
    AuthorQuery,         # 作者查询
    RPYS,                # RPYS分析
    TopicModeling,       # 主题建模
    TopicAnalyzer        # 主题分析
)

# 使用示例
import asyncio

async def main():
    # 数据提取
    extractor = WorksExtractor(email="your@email.com")
    works = await extractor.query(
        source_name="Nature",
        limit=100
    )

    # 作者查询
    author_query = AuthorQuery()
    author = await author_query.query("10.1038/...")

asyncio.run(main())
```

## 📚 在 OpenAlex Agent 项目中使用

### 步骤1: 安装包

在 openalex_agent 项目中：

```bash
cd /home/dell/Desktop/OAAgent/alexer/openalex_agent

# 激活虚拟环境（如果有）
source .venv/bin/activate

# 安装 metasci-universe
uv pip install -e /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse
```

### 步骤2: 修改导入

#### 修改前（硬编码路径）

```python
import sys
sys.path.insert(0, '/home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse/src')

from DataExtractorTool.works_extractor import WorksExtractor
```

#### 修改后（优雅导入）

```python
from metasci_universe import WorksExtractor
```

### 步骤3: 批量修改

在 openalex_agent 项目中查找所有需要修改的文件：

```bash
# 查找硬编码路径
grep -r "sys.path.insert.*MetaSciToolUniverse" --include="*.py"

# 查找旧的导入语句
grep -r "from DataExtractorTool\|from SearchTool\|from AuthorTool" --include="*.py"
```

## 🔧 具体文件修改示例

### tools/data_extraction/data_extraction_tools.py

修改前 18 行代码，修改后仅需 2 行：

**修改前:**
```python
"""
Data Extraction Tools
"""
import sys
import logging
from typing import Optional, Dict

sys.path.insert(0, '/home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse/src')
sys.path.insert(0, '/home/dell/Desktop/OAAgent/alexer/light_agent')

from DataExtractorTool.works_extractor import WorksExtractor
from light_agent.core.registry import TOOL

logger = logging.getLogger(__name__)


class DataExtractionTools:
    """数据提取工具类"""
    def __init__(self, email: Optional[str] = None):
        self._extractor = WorksExtractor(email=email)
```

**修改后:**
```python
"""
Data Extraction Tools
"""
import logging
from typing import Optional, Dict

from metasci_universe import WorksExtractor
from light_agent.core.registry import TOOL

logger = logging.getLogger(__name__)


class DataExtractionTools:
    """数据提取工具类"""
    def __init__(self, email: Optional[str] = None):
        self._extractor = WorksExtractor(email=email)
```

## 📖 详细文档

- **README.md** - 完整的安装和使用指南
- **docs/MIGRATION_GUIDE.md** - 详细的迁移步骤和示例
- **CLAUDE.md** - 开发指南

## 🎯 核心优势

### 修改前的问题
- ❌ 硬编码绝对路径，不可移植
- ❌ 需要手动管理 sys.path
- ❌ 跨项目使用困难
- ❌ 无法进行版本管理
- ❌ 不符合 Python 生态规范

### 修改后的优势
- ✅ 标准 Python 包，可通过 pip/uv 安装
- ✅ 优雅的导入语句 `from metasci_universe import ...`
- ✅ 支持版本管理和依赖追踪
- ✅ 可以发布到 PyPI 或私有仓库
- ✅ 开发模式（-e）支持代码实时更新
- ✅ 符合 Python 最佳实践

## 🔄 开发模式的好处

使用 `-e` (editable mode) 安装后：
- 修改 MetaSciToolUniverse 的代码会立即生效
- 无需重新安装
- 适合同时开发两个项目

## 📊 包信息

```bash
# 查看包信息
uv pip show metasci-universe

# 查看已安装的包
uv pip list | grep metasci

# 卸载包
uv pip uninstall metasci-universe
```

## 🎉 下一步

1. **在 OpenAlex Agent 中安装包**
   ```bash
   cd /home/dell/Desktop/OAAgent/alexer/openalex_agent
   uv pip install -e /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse
   ```

2. **修改导入语句**
   - 移除所有 `sys.path.insert` 语句
   - 将 `from DataExtractorTool import ...` 改为 `from metasci_universe import ...`

3. **测试功能**
   - 运行现有的测试确保一切正常

4. **享受优雅的代码** 🎊

## 💡 提示

- 如果修改了 MetaSciToolUniverse 的代码，无需重新安装，直接使用即可
- 如果更新了包的配置（pyproject.toml），需要重新运行 `uv pip install -e .`
- 可以使用相对路径或绝对路径安装，建议使用绝对路径以避免混淆

## 🐛 故障排除

### 问题: 找不到 metasci_universe 模块

**解决方案:**
```bash
# 确认包已安装
uv pip list | grep metasci-universe

# 如果没有，重新安装
cd /home/dell/Desktop/OAAgent/SciSciTool/MetaSciToolUniverse
uv pip install -e .
```

### 问题: 导入某个工具类失败

**解决方案:**
检查 `src/metasci_universe.py` 和对应工具的 `__init__.py` 是否正确导出了该类。

## 📝 总结

现在你的项目已经：
- ✅ 成为一个标准的 Python 包
- ✅ 可以被其他项目优雅地调用
- ✅ 支持版本管理和依赖追踪
- ✅ 符合 Python 生态最佳实践

恭喜！🎉
