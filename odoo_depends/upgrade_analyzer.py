"""
Odoo 升级分析器 - 版本对比、模型分析、影响评估
"""

import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict

from .analyzer import OdooModuleAnalyzer, OdooModule


@dataclass
class ModelField:
    """模型字段信息"""
    name: str
    field_type: str
    comodel_name: Optional[str] = None  # 关联模型
    related: Optional[str] = None
    compute: Optional[str] = None
    store: bool = True
    required: bool = False
    readonly: bool = False
    string: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "field_type": self.field_type,
            "comodel_name": self.comodel_name,
            "related": self.related,
            "compute": self.compute,
            "store": self.store,
            "required": self.required,
            "string": self.string,
        }


@dataclass
class OdooModel:
    """Odoo模型信息"""
    name: str  # _name
    inherit: List[str] = field(default_factory=list)  # _inherit
    inherits: Dict[str, str] = field(default_factory=dict)  # _inherits
    description: str = ""  # _description
    fields: Dict[str, ModelField] = field(default_factory=dict)
    methods: List[str] = field(default_factory=list)
    module: str = ""
    file_path: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "inherit": self.inherit,
            "inherits": self.inherits,
            "description": self.description,
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "methods": self.methods,
            "module": self.module,
            "file_path": self.file_path,
        }


@dataclass 
class VersionDiff:
    """版本差异信息"""
    added_modules: List[str] = field(default_factory=list)
    removed_modules: List[str] = field(default_factory=list)
    modified_modules: List[dict] = field(default_factory=list)
    dependency_changes: List[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "added_modules": self.added_modules,
            "removed_modules": self.removed_modules,
            "modified_modules": self.modified_modules,
            "dependency_changes": self.dependency_changes,
            "summary": {
                "added": len(self.added_modules),
                "removed": len(self.removed_modules),
                "modified": len(self.modified_modules),
            }
        }


@dataclass
class UpgradeImpact:
    """升级影响评估"""
    module_name: str
    direct_dependents: List[str] = field(default_factory=list)
    all_dependents: List[str] = field(default_factory=list)
    affected_models: List[str] = field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "module_name": self.module_name,
            "direct_dependents": self.direct_dependents,
            "all_dependents": self.all_dependents,
            "affected_models": self.affected_models,
            "risk_level": self.risk_level,
            "risk_factors": self.risk_factors,
            "recommendations": self.recommendations,
            "impact_score": len(self.all_dependents) + len(self.affected_models) * 2,
        }


class ModelAnalyzer:
    """模型分析器 - 解析Python文件中的Odoo模型定义"""
    
    # Odoo字段类型
    FIELD_TYPES = {
        'Char', 'Text', 'Html', 'Integer', 'Float', 'Monetary',
        'Boolean', 'Date', 'Datetime', 'Binary', 'Image',
        'Selection', 'Reference', 'Many2one', 'One2many', 'Many2many',
    }
    
    def __init__(self):
        self.models: Dict[str, OdooModel] = {}
        
    def analyze_module(self, module_path: str) -> Dict[str, OdooModel]:
        """分析模块中的所有模型"""
        module_path = Path(module_path)
        models_dir = module_path / 'models'
        
        if not models_dir.exists():
            # 尝试直接在模块根目录查找.py文件
            for py_file in module_path.glob('*.py'):
                if py_file.name != '__init__.py' and py_file.name != '__manifest__.py':
                    self._parse_python_file(py_file, module_path.name)
        else:
            for py_file in models_dir.rglob('*.py'):
                if py_file.name != '__init__.py':
                    self._parse_python_file(py_file, module_path.name)
                    
        return self.models
    
    def _parse_python_file(self, file_path: Path, module_name: str) -> None:
        """解析Python文件提取模型定义"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    model = self._parse_class(node, module_name, str(file_path))
                    if model:
                        # 使用_name或类名作为键
                        key = model.name if model.name else node.name
                        if key:
                            self.models[key] = model
                            
        except Exception as e:
            pass  # 静默处理解析错误
    
    def _parse_class(self, node: ast.ClassDef, module_name: str, file_path: str) -> Optional[OdooModel]:
        """解析类定义提取模型信息"""
        model = OdooModel(name="", module=module_name, file_path=file_path)
        is_odoo_model = False
        
        for item in node.body:
            # 解析 _name, _inherit, _inherits, _description
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        attr_name = target.id
                        
                        if attr_name == '_name':
                            model.name = self._get_string_value(item.value)
                            is_odoo_model = True
                        elif attr_name == '_inherit':
                            inherit_value = self._get_value(item.value)
                            if isinstance(inherit_value, str):
                                model.inherit = [inherit_value]
                                is_odoo_model = True
                            elif isinstance(inherit_value, list):
                                model.inherit = inherit_value
                                is_odoo_model = True
                        elif attr_name == '_inherits':
                            if isinstance(item.value, ast.Dict):
                                model.inherits = self._parse_dict(item.value)
                        elif attr_name == '_description':
                            model.description = self._get_string_value(item.value)
                        elif attr_name in self.FIELD_TYPES or self._is_field_definition(item.value):
                            field = self._parse_field(attr_name, item.value)
                            if field:
                                model.fields[attr_name] = field
                                
            # 解析字段定义 (field_name = fields.Char(...))
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        if self._is_field_definition(item.value):
                            field = self._parse_field(target.id, item.value)
                            if field:
                                model.fields[target.id] = field
                                is_odoo_model = True
                                
            # 解析方法
            elif isinstance(item, ast.FunctionDef):
                model.methods.append(item.name)
        
        # 如果没有_name但有_inherit，这是一个继承扩展
        if not model.name and model.inherit:
            model.name = model.inherit[0] if len(model.inherit) == 1 else None
            is_odoo_model = True
            
        return model if is_odoo_model else None
    
    def _is_field_definition(self, node: ast.expr) -> bool:
        """检查是否是Odoo字段定义"""
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id == 'fields':
                        return node.func.attr in self.FIELD_TYPES
        return False
    
    def _parse_field(self, name: str, node: ast.expr) -> Optional[ModelField]:
        """解析字段定义"""
        if not isinstance(node, ast.Call):
            return None
            
        if not isinstance(node.func, ast.Attribute):
            return None
            
        field_type = node.func.attr
        if field_type not in self.FIELD_TYPES:
            return None
            
        field = ModelField(name=name, field_type=field_type)
        
        # 解析字段参数
        for keyword in node.keywords:
            if keyword.arg == 'comodel_name':
                field.comodel_name = self._get_string_value(keyword.value)
            elif keyword.arg == 'related':
                field.related = self._get_string_value(keyword.value)
            elif keyword.arg == 'compute':
                field.compute = self._get_string_value(keyword.value)
            elif keyword.arg == 'store':
                field.store = self._get_bool_value(keyword.value)
            elif keyword.arg == 'required':
                field.required = self._get_bool_value(keyword.value)
            elif keyword.arg == 'readonly':
                field.readonly = self._get_bool_value(keyword.value)
            elif keyword.arg == 'string':
                field.string = self._get_string_value(keyword.value)
                
        # 对于关系字段，第一个位置参数通常是comodel_name
        if field_type in ('Many2one', 'One2many', 'Many2many') and node.args:
            if isinstance(node.args[0], ast.Constant):
                field.comodel_name = node.args[0].value
                
        return field
    
    def _get_string_value(self, node: ast.expr) -> str:
        """获取字符串值"""
        if isinstance(node, ast.Constant):
            return str(node.value) if node.value else ""
        elif isinstance(node, ast.Str):  # Python 3.7兼容
            return node.s
        return ""
    
    def _get_bool_value(self, node: ast.expr) -> bool:
        """获取布尔值"""
        if isinstance(node, ast.Constant):
            return bool(node.value)
        elif isinstance(node, ast.NameConstant):  # Python 3.7兼容
            return bool(node.value)
        return False
    
    def _get_value(self, node: ast.expr):
        """获取节点值"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Str):
            return node.s
        elif isinstance(node, ast.List):
            return [self._get_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Tuple):
            return [self._get_value(elt) for elt in node.elts]
        return None
    
    def _parse_dict(self, node: ast.Dict) -> dict:
        """解析字典"""
        result = {}
        for key, value in zip(node.keys, node.values):
            k = self._get_string_value(key) if key else None
            v = self._get_string_value(value)
            if k:
                result[k] = v
        return result


class UpgradeAnalyzer:
    """升级分析器 - 版本对比和影响评估"""
    
    def __init__(self):
        self.source_analyzer: Optional[OdooModuleAnalyzer] = None
        self.target_analyzer: Optional[OdooModuleAnalyzer] = None
        self.model_analyzer = ModelAnalyzer()
        self.models: Dict[str, OdooModel] = {}
        
    def load_source(self, paths: List[str]) -> None:
        """加载源版本（当前版本）"""
        self.source_analyzer = OdooModuleAnalyzer(paths)
        self.source_analyzer.scan_modules()
        self.source_analyzer.build_dependency_graph()
        
    def load_target(self, paths: List[str]) -> None:
        """加载目标版本（升级目标）"""
        self.target_analyzer = OdooModuleAnalyzer(paths)
        self.target_analyzer.scan_modules()
        self.target_analyzer.build_dependency_graph()
        
    def compare_versions(self) -> VersionDiff:
        """对比两个版本的差异"""
        if not self.source_analyzer or not self.target_analyzer:
            raise ValueError("请先加载源版本和目标版本")
            
        source_modules = set(self.source_analyzer.modules.keys())
        target_modules = set(self.target_analyzer.modules.keys())
        
        diff = VersionDiff()
        
        # 新增模块
        diff.added_modules = sorted(list(target_modules - source_modules))
        
        # 删除模块
        diff.removed_modules = sorted(list(source_modules - target_modules))
        
        # 修改的模块
        common_modules = source_modules & target_modules
        for name in sorted(common_modules):
            source_mod = self.source_analyzer.modules[name]
            target_mod = self.target_analyzer.modules[name]
            
            changes = self._compare_module(source_mod, target_mod)
            if changes:
                diff.modified_modules.append({
                    "name": name,
                    "changes": changes
                })
                
        # 依赖变更
        for name in sorted(common_modules):
            source_deps = set(self.source_analyzer.modules[name].depends)
            target_deps = set(self.target_analyzer.modules[name].depends)
            
            added_deps = target_deps - source_deps
            removed_deps = source_deps - target_deps
            
            if added_deps or removed_deps:
                diff.dependency_changes.append({
                    "module": name,
                    "added_dependencies": sorted(list(added_deps)),
                    "removed_dependencies": sorted(list(removed_deps)),
                })
                
        return diff
    
    def _compare_module(self, source: OdooModule, target: OdooModule) -> List[str]:
        """对比单个模块的变化"""
        changes = []
        
        if source.version != target.version:
            changes.append(f"版本变更: {source.version} → {target.version}")
            
        if source.category != target.category:
            changes.append(f"分类变更: {source.category} → {target.category}")
            
        if source.application != target.application:
            status = "是" if target.application else "否"
            changes.append(f"应用状态变更: {status}")
            
        if set(source.depends) != set(target.depends):
            changes.append("依赖关系已变更")
            
        return changes
    
    def analyze_models(self, analyzer: OdooModuleAnalyzer) -> Dict[str, OdooModel]:
        """分析所有模块的模型"""
        self.models.clear()
        model_analyzer = ModelAnalyzer()
        
        for name, module in analyzer.modules.items():
            module_models = model_analyzer.analyze_module(module.path)
            for model_name, model in module_models.items():
                if model_name:
                    self.models[model_name] = model
                    
        return self.models
    
    def get_model_relationships(self) -> Dict[str, List[dict]]:
        """获取模型间的关系"""
        relationships = defaultdict(list)
        
        for model_name, model in self.models.items():
            for field_name, field in model.fields.items():
                if field.comodel_name:
                    relationships[model_name].append({
                        "field": field_name,
                        "type": field.field_type,
                        "target": field.comodel_name,
                    })
                    
        return dict(relationships)
    
    def assess_upgrade_impact(
        self, 
        module_name: str, 
        analyzer: OdooModuleAnalyzer
    ) -> UpgradeImpact:
        """评估升级某个模块的影响"""
        impact = UpgradeImpact(module_name=module_name)
        
        if module_name not in analyzer.modules:
            impact.risk_factors.append(f"模块 {module_name} 不存在")
            impact.risk_level = "critical"
            return impact
            
        # 直接依赖者（哪些模块直接依赖这个模块）
        impact.direct_dependents = sorted(list(analyzer.get_reverse_dependencies(module_name)))
        
        # 所有依赖者（递归）
        all_dependents = set()
        for dep in impact.direct_dependents:
            all_dependents.add(dep)
            all_dependents.update(analyzer.get_reverse_dependencies(dep))
        impact.all_dependents = sorted(list(all_dependents))
        
        # 分析受影响的模型
        if module_name in analyzer.modules:
            module = analyzer.modules[module_name]
            model_analyzer = ModelAnalyzer()
            models = model_analyzer.analyze_module(module.path)
            impact.affected_models = sorted(list(models.keys()))
        
        # 评估风险等级
        dependent_count = len(impact.all_dependents)
        model_count = len(impact.affected_models)
        
        if dependent_count > 50 or module_name in analyzer.CORE_MODULES:
            impact.risk_level = "critical"
            impact.risk_factors.append(f"核心模块，{dependent_count} 个模块依赖此模块")
        elif dependent_count > 20:
            impact.risk_level = "high"
            impact.risk_factors.append(f"高影响模块，{dependent_count} 个模块依赖此模块")
        elif dependent_count > 5:
            impact.risk_level = "medium"
            impact.risk_factors.append(f"中等影响，{dependent_count} 个模块依赖此模块")
        else:
            impact.risk_level = "low"
            
        if model_count > 10:
            impact.risk_factors.append(f"定义了 {model_count} 个模型")
            if impact.risk_level == "low":
                impact.risk_level = "medium"
                
        # 生成建议
        if impact.risk_level == "critical":
            impact.recommendations.append("⚠️ 建议在测试环境充分测试后再升级")
            impact.recommendations.append("📋 制定详细的回滚计划")
            impact.recommendations.append("📊 升级前备份数据库")
        elif impact.risk_level == "high":
            impact.recommendations.append("🔍 仔细检查所有依赖模块的兼容性")
            impact.recommendations.append("📊 建议先在测试环境验证")
        elif impact.risk_level == "medium":
            impact.recommendations.append("✅ 检查直接依赖模块的兼容性")
        else:
            impact.recommendations.append("✅ 可以安全升级")
            
        return impact
    
    def get_upgrade_order(
        self, 
        modules: List[str], 
        analyzer: OdooModuleAnalyzer
    ) -> List[dict]:
        """获取模块升级顺序（考虑依赖关系）"""
        order = analyzer.get_install_order(modules)
        
        result = []
        for i, mod in enumerate(order):
            impact = self.assess_upgrade_impact(mod, analyzer)
            result.append({
                "order": i + 1,
                "module": mod,
                "risk_level": impact.risk_level,
                "dependents_count": len(impact.all_dependents),
            })
            
        return result
    
    def get_model_statistics(self) -> dict:
        """获取模型统计信息"""
        if not self.models:
            return {}
            
        total_fields = 0
        relation_fields = 0
        computed_fields = 0
        
        for model in self.models.values():
            total_fields += len(model.fields)
            for field in model.fields.values():
                if field.field_type in ('Many2one', 'One2many', 'Many2many'):
                    relation_fields += 1
                if field.compute:
                    computed_fields += 1
                    
        return {
            "total_models": len(self.models),
            "total_fields": total_fields,
            "relation_fields": relation_fields,
            "computed_fields": computed_fields,
            "avg_fields_per_model": round(total_fields / len(self.models), 1) if self.models else 0,
        }
