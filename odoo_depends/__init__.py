"""
Odoo Module Dependency Analyzer
分析Odoo模块的依赖关系，生成可视化依赖图
"""

__version__ = "1.0.0"
__author__ = "Galaxy"

from .analyzer import OdooModuleAnalyzer
from .visualizer import DependencyVisualizer

__all__ = ["OdooModuleAnalyzer", "DependencyVisualizer"]
