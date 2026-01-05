"""
Odoo模块解析器 - 扫描和分析Odoo模块的依赖关系
"""

import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
import networkx as nx


@dataclass
class OdooModule:
    """表示一个Odoo模块的数据类"""
    name: str
    path: str
    version: str = "1.0"
    summary: str = ""
    description: str = ""
    author: str = ""
    category: str = ""
    depends: List[str] = field(default_factory=list)
    data: List[str] = field(default_factory=list)
    installable: bool = True
    application: bool = False
    auto_install: bool = False
    license: str = "LGPL-3"
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "version": self.version,
            "summary": self.summary,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "depends": self.depends,
            "data": self.data,
            "installable": self.installable,
            "application": self.application,
            "auto_install": self.auto_install,
            "license": self.license,
        }


class OdooModuleAnalyzer:
    """Odoo模块依赖分析器"""
    
    # Odoo核心模块列表（通常预装）
    CORE_MODULES = {
        'base', 'web', 'mail', 'portal', 'auth_signup', 'contacts',
        'sale', 'purchase', 'stock', 'account', 'mrp', 'project',
        'hr', 'crm', 'website', 'point_of_sale', 'fleet', 'lunch',
        'calendar', 'note', 'board', 'fetchmail', 'bus', 'im_livechat',
        'utm', 'http_routing', 'digest', 'phone_validation',
        'base_import', 'base_setup', 'web_editor', 'web_tour',
        'iap', 'sms', 'snailmail', 'product', 'uom', 'analytic',
        'payment', 'delivery', 'rating', 'resource', 'survey'
    }
    
    def __init__(self, paths: Optional[List[str]] = None):
        """
        初始化分析器
        
        Args:
            paths: Odoo模块目录路径列表
        """
        self.paths: List[str] = paths or []
        self.modules: Dict[str, OdooModule] = {}
        self.graph: Optional[nx.DiGraph] = None
        
    def add_path(self, path: str) -> None:
        """添加一个模块扫描路径"""
        if path not in self.paths:
            self.paths.append(path)
            
    def scan_modules(self) -> Dict[str, OdooModule]:
        """
        扫描所有路径下的Odoo模块
        
        Returns:
            模块名到模块对象的映射字典
        """
        self.modules.clear()
        
        for base_path in self.paths:
            base_path = Path(base_path).resolve()
            if not base_path.exists():
                print(f"警告: 路径不存在 - {base_path}")
                continue
                
            # 扫描目录
            if base_path.is_dir():
                self._scan_directory(base_path)
                    
        return self.modules
    
    def _scan_directory(self, directory: Path) -> None:
        """扫描目录下的所有模块"""
        # 检查当前目录是否是Odoo模块
        if self._is_odoo_module(directory):
            module = self._parse_module(directory)
            if module:
                self.modules[module.name] = module
            return
            
        # 递归扫描子目录
        try:
            for item in directory.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    if self._is_odoo_module(item):
                        module = self._parse_module(item)
                        if module:
                            self.modules[module.name] = module
                    else:
                        # 继续向下扫描一层
                        for subitem in item.iterdir():
                            if subitem.is_dir() and self._is_odoo_module(subitem):
                                module = self._parse_module(subitem)
                                if module:
                                    self.modules[module.name] = module
        except PermissionError:
            print(f"警告: 无法访问目录 - {directory}")
    
    def _is_odoo_module(self, path: Path) -> bool:
        """判断路径是否是Odoo模块"""
        manifest_files = ['__manifest__.py', '__openerp__.py']
        init_file = path / '__init__.py'
        
        if not init_file.exists():
            return False
            
        for manifest in manifest_files:
            if (path / manifest).exists():
                return True
        return False
    
    def _parse_module(self, path: Path) -> Optional[OdooModule]:
        """解析Odoo模块的manifest文件"""
        manifest_path = path / '__manifest__.py'
        if not manifest_path.exists():
            manifest_path = path / '__openerp__.py'
            if not manifest_path.exists():
                return None
                
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 尝试多种解析方式
            manifest_data = self._safe_parse_manifest(content, manifest_path)
            
            if manifest_data is None or not isinstance(manifest_data, dict):
                return None
                
            module = OdooModule(
                name=path.name,
                path=str(path),
                version=str(manifest_data.get('version', '1.0')),
                summary=manifest_data.get('summary', '') or '',
                description=manifest_data.get('description', '') or '',
                author=manifest_data.get('author', '') or '',
                category=manifest_data.get('category', '') or '',
                depends=manifest_data.get('depends', []) or [],
                data=manifest_data.get('data', []) or [],
                installable=manifest_data.get('installable', True),
                application=manifest_data.get('application', False),
                auto_install=manifest_data.get('auto_install', False),
                license=manifest_data.get('license', 'LGPL-3'),
            )
            return module
            
        except Exception as e:
            # 静默处理大多数错误，只在调试时显示
            return None
    
    def _safe_parse_manifest(self, content: str, manifest_path: Path) -> Optional[dict]:
        """安全地解析manifest内容，支持多种格式"""
        import re
        
        # 方法1: 尝试直接使用ast.literal_eval
        try:
            tree = ast.parse(content, mode='eval')
            return ast.literal_eval(compile(tree, '<string>', 'eval'))
        except:
            pass
        
        # 方法2: 使用正则提取关键字段
        try:
            result = {}
            
            # 提取 name
            name_match = re.search(r"['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]", content)
            if name_match:
                result['name'] = name_match.group(1)
            
            # 提取 version
            version_match = re.search(r"['\"]version['\"]\s*:\s*['\"]([^'\"]+)['\"]", content)
            if version_match:
                result['version'] = version_match.group(1)
            
            # 提取 summary
            summary_match = re.search(r"['\"]summary['\"]\s*:\s*['\"]([^'\"]*)['\"]", content)
            if summary_match:
                result['summary'] = summary_match.group(1)
            
            # 提取 author
            author_match = re.search(r"['\"]author['\"]\s*:\s*['\"]([^'\"]*)['\"]", content)
            if author_match:
                result['author'] = author_match.group(1)
            
            # 提取 category
            category_match = re.search(r"['\"]category['\"]\s*:\s*['\"]([^'\"]*)['\"]", content)
            if category_match:
                result['category'] = category_match.group(1)
            
            # 提取 depends 列表
            depends_match = re.search(r"['\"]depends['\"]\s*:\s*\[(.*?)\]", content, re.DOTALL)
            if depends_match:
                deps_str = depends_match.group(1)
                deps = re.findall(r"['\"]([^'\"]+)['\"]", deps_str)
                result['depends'] = deps
            else:
                result['depends'] = []
            
            # 提取 installable
            installable_match = re.search(r"['\"]installable['\"]\s*:\s*(True|False)", content)
            if installable_match:
                result['installable'] = installable_match.group(1) == 'True'
            else:
                result['installable'] = True
            
            # 提取 application
            application_match = re.search(r"['\"]application['\"]\s*:\s*(True|False)", content)
            if application_match:
                result['application'] = application_match.group(1) == 'True'
            else:
                result['application'] = False
            
            # 提取 auto_install
            auto_install_match = re.search(r"['\"]auto_install['\"]\s*:\s*(True|False|\[.*?\])", content, re.DOTALL)
            if auto_install_match:
                val = auto_install_match.group(1)
                result['auto_install'] = val == 'True' or val.startswith('[')
            else:
                result['auto_install'] = False
            
            # 提取 license
            license_match = re.search(r"['\"]license['\"]\s*:\s*['\"]([^'\"]*)['\"]", content)
            if license_match:
                result['license'] = license_match.group(1)
            
            if result.get('depends') is not None:
                return result
                
        except Exception:
            pass
        
        return None
    
    def build_dependency_graph(self) -> nx.DiGraph:
        """
        构建依赖关系图
        
        Returns:
            NetworkX有向图
        """
        self.graph = nx.DiGraph()
        
        # 添加所有模块作为节点
        for name, module in self.modules.items():
            self.graph.add_node(
                name,
                version=module.version,
                category=module.category,
                application=module.application,
                is_core=name in self.CORE_MODULES,
                installable=module.installable,
                path=module.path,
            )
            
        # 添加依赖边
        for name, module in self.modules.items():
            for dep in module.depends:
                # 如果依赖不在已扫描模块中，添加为外部模块
                if dep not in self.graph:
                    self.graph.add_node(
                        dep,
                        is_external=True,
                        is_core=dep in self.CORE_MODULES,
                    )
                self.graph.add_edge(name, dep)
                
        return self.graph
    
    def get_all_dependencies(self, module_name: str, include_core: bool = True) -> Set[str]:
        """
        获取模块的所有依赖（递归）
        
        Args:
            module_name: 模块名
            include_core: 是否包含核心模块
            
        Returns:
            所有依赖模块的集合
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        if module_name not in self.graph:
            return set()
            
        deps = nx.descendants(self.graph, module_name)
        
        if not include_core:
            deps = {d for d in deps if d not in self.CORE_MODULES}
            
        return deps
    
    def get_reverse_dependencies(self, module_name: str) -> Set[str]:
        """
        获取依赖于指定模块的所有模块（反向依赖）
        
        Args:
            module_name: 模块名
            
        Returns:
            反向依赖模块的集合
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        if module_name not in self.graph:
            return set()
            
        return nx.ancestors(self.graph, module_name)
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        检测循环依赖
        
        Returns:
            循环依赖列表，每个元素是形成循环的模块列表
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        try:
            cycles = list(nx.simple_cycles(self.graph))
            return cycles
        except:
            return []
    
    def find_missing_dependencies(self) -> Dict[str, List[str]]:
        """
        查找缺失的依赖（依赖的模块不在扫描路径中且不是核心模块）
        
        Returns:
            模块名到其缺失依赖列表的映射
        """
        missing = {}
        
        for name, module in self.modules.items():
            missing_deps = []
            for dep in module.depends:
                if dep not in self.modules and dep not in self.CORE_MODULES:
                    missing_deps.append(dep)
            if missing_deps:
                missing[name] = missing_deps
                
        return missing
    
    def get_install_order(self, module_names: Optional[List[str]] = None) -> List[str]:
        """
        获取模块的正确安装顺序（拓扑排序）
        
        Args:
            module_names: 要安装的模块列表，None表示所有模块
            
        Returns:
            按安装顺序排列的模块列表
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        try:
            # 反转依赖方向后进行拓扑排序
            reversed_graph = self.graph.reverse()
            order = list(nx.topological_sort(reversed_graph))
            
            if module_names:
                # 只返回指定模块及其依赖
                required = set()
                for name in module_names:
                    required.add(name)
                    required.update(self.get_all_dependencies(name))
                order = [m for m in order if m in required]
                
            return order
        except nx.NetworkXUnfeasible:
            print("警告: 存在循环依赖，无法确定安装顺序")
            return []
    
    def get_dependency_depth(self, module_name: str) -> int:
        """
        获取模块的依赖深度
        
        Args:
            module_name: 模块名
            
        Returns:
            依赖深度（最长依赖链长度）
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        if module_name not in self.graph:
            return 0
            
        try:
            # 找到从该模块出发的最长路径
            lengths = nx.single_source_shortest_path_length(self.graph, module_name)
            return max(lengths.values()) if lengths else 0
        except:
            return 0
    
    def get_statistics(self) -> dict:
        """
        获取依赖分析统计信息
        
        Returns:
            包含各项统计数据的字典
        """
        if self.graph is None:
            self.build_dependency_graph()
            
        total_modules = len(self.modules)
        external_deps = set()
        all_deps = []
        
        for module in self.modules.values():
            for dep in module.depends:
                if dep not in self.modules:
                    external_deps.add(dep)
            all_deps.extend(module.depends)
            
        # 统计每个模块被依赖的次数
        dep_counts = defaultdict(int)
        for module in self.modules.values():
            for dep in module.depends:
                dep_counts[dep] += 1
                
        most_depended = sorted(dep_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "total_modules": total_modules,
            "total_dependencies": len(all_deps),
            "unique_dependencies": len(set(all_deps)),
            "external_dependencies": list(external_deps),
            "core_dependencies": [d for d in external_deps if d in self.CORE_MODULES],
            "missing_dependencies": self.find_missing_dependencies(),
            "circular_dependencies": self.find_circular_dependencies(),
            "most_depended_modules": most_depended,
            "applications": [m.name for m in self.modules.values() if m.application],
            "categories": list(set(m.category for m in self.modules.values() if m.category)),
        }
    
    def export_to_json(self, output_path: str) -> None:
        """导出分析结果为JSON"""
        data = {
            "modules": {name: module.to_dict() for name, module in self.modules.items()},
            "statistics": self.get_statistics(),
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    def export_to_dot(self, output_path: str) -> None:
        """导出依赖图为DOT格式（用于Graphviz）"""
        if self.graph is None:
            self.build_dependency_graph()
            
        nx.drawing.nx_pydot.write_dot(self.graph, output_path)
