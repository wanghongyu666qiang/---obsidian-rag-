"""
智学 (ZhiXue) - 测试配置
pytest 配置文件
"""
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保测试可以导入 app 包
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# pytest 配置
pytest_plugins = []
