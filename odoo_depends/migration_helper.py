"""
Odoo 升级迁移辅助工具
- 生成迁移脚本模板
- 检测废弃 API 并提供修改建议
- 生成升级检查清单
- 批量代码更新
"""
import os
import re
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


# Odoo 版本间的废弃 API 映射
DEPRECATED_APIS = {
    # Odoo 14 -> 15
    "14_to_15": {
        "odoo.tools.misc.topological_sort": {
            "replacement": "graphlib.TopologicalSorter",
            "description": "使用 Python 标准库的 TopologicalSorter",
        },
        "report_sxw": {
            "replacement": "report.report_qweb",
            "description": "RML 报表已废弃，使用 QWeb",
        },
    },
    # Odoo 15 -> 16
    "15_to_16": {
        "odoo.tools.pycompat": {
            "replacement": "直接使用 Python 3 语法",
            "description": "Python 2 兼容层已移除",
        },
        "@api.multi": {
            "replacement": "移除此装饰器",
            "description": "api.multi 在 Odoo 13+ 已废弃",
        },
        "@api.one": {
            "replacement": "使用 for record in self",
            "description": "api.one 已废弃，手动遍历记录集",
        },
    },
    # Odoo 16 -> 17
    "16_to_17": {
        "fields.Serialized": {
            "replacement": "fields.Json",
            "description": "Serialized 字段已更名为 Json",
        },
        "web.assets_backend": {
            "replacement": "web.assets_backend_lazy",
            "description": "资源包结构变更",
        },
        "_inherit_children": {
            "replacement": "_inherits_children",
            "description": "属性名称变更",
        },
    },
    # Odoo 17 -> 18
    "17_to_18": {
        "oldname": {
            "replacement": "使用 pre_init_hook 处理",
            "description": "字段的 oldname 参数已移除",
        },
    },
}

# 常见代码模式及其替换
CODE_PATTERNS = {
    # api.multi 和 api.one
    r"@api\.multi\s*\n": {
        "replacement": "",
        "description": "移除 @api.multi 装饰器",
        "since": "13.0",
    },
    r"@api\.one\s*\n": {
        "replacement": "",
        "description": "移除 @api.one 装饰器（需手动添加 for record in self）",
        "since": "13.0",
    },
    # 旧式 compute 方法
    r"compute='([^']+)',\s*multi='([^']+)'": {
        "replacement": r"compute='\1'",
        "description": "移除 multi 参数",
        "since": "13.0",
    },
    # 旧式 fields 导入
    r"from openerp import fields": {
        "replacement": "from odoo import fields",
        "description": "openerp 已重命名为 odoo",
        "since": "10.0",
    },
    r"from openerp\.osv import fields": {
        "replacement": "from odoo import fields",
        "description": "使用新式 ORM",
        "since": "10.0",
    },
    # 废弃的方法调用
    r"self\.pool\.get\(['\"]([^'\"]+)['\"]\)": {
        "replacement": r"self.env['\1']",
        "description": "使用 self.env 代替 self.pool.get",
        "since": "8.0",
    },
    r"\.browse\(cr,\s*uid,": {
        "replacement": ".browse(",
        "description": "新式 ORM 不需要 cr, uid 参数",
        "since": "8.0",
    },
    r"\.search\(cr,\s*uid,": {
        "replacement": ".search(",
        "description": "新式 ORM 不需要 cr, uid 参数",
        "since": "8.0",
    },
}


@dataclass
class CodeIssue:
    """代码问题"""
    file_path: str
    line_number: int
    line_content: str
    issue_type: str
    description: str
    suggestion: str
    auto_fixable: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MigrationScript:
    """迁移脚本"""
    module_name: str
    version: str
    pre_migrate: str
    post_migrate: str
    end_migrate: str
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class UpgradeChecklist:
    """升级检查清单"""
    items: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_item(self, category: str, title: str, description: str, 
                 priority: str = "medium", auto_check: bool = False,
                 status: str = "pending"):
        self.items.append({
            "category": category,
            "title": title,
            "description": description,
            "priority": priority,
            "auto_check": auto_check,
            "status": status,
        })
    
    def to_dict(self) -> Dict:
        return {"items": self.items}


class MigrationHelper:
    """迁移辅助工具"""
    
    def __init__(self, module_paths: List[str], 
                 source_version: str = "16.0",
                 target_version: str = "17.0"):
        self.module_paths = [Path(p) for p in module_paths]
        self.source_version = source_version
        self.target_version = target_version
        self.issues: List[CodeIssue] = []
        self.modules: Dict[str, Path] = {}
        
    def scan_modules(self):
        """扫描模块"""
        for path in self.module_paths:
            if not path.exists():
                continue
            for item in path.iterdir():
                if item.is_dir():
                    manifest = item / "__manifest__.py"
                    if manifest.exists():
                        self.modules[item.name] = item
    
    def analyze_code(self) -> List[CodeIssue]:
        """分析代码问题"""
        self.issues = []
        
        for module_name, module_path in self.modules.items():
            self._analyze_module(module_name, module_path)
        
        return self.issues
    
    def _analyze_module(self, module_name: str, module_path: Path):
        """分析单个模块"""
        # 扫描所有 Python 文件
        for py_file in module_path.rglob("*.py"):
            self._analyze_python_file(py_file)
        
        # 扫描所有 XML 文件
        for xml_file in module_path.rglob("*.xml"):
            self._analyze_xml_file(xml_file)
    
    def _analyze_python_file(self, file_path: Path):
        """分析 Python 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")
        except Exception:
            return
        
        # 检查代码模式
        for pattern, info in CODE_PATTERNS.items():
            for match in re.finditer(pattern, content):
                # 找到行号
                line_num = content[:match.start()].count("\n") + 1
                line_content = lines[line_num - 1] if line_num <= len(lines) else ""
                
                self.issues.append(CodeIssue(
                    file_path=str(file_path),
                    line_number=line_num,
                    line_content=line_content.strip(),
                    issue_type="deprecated_pattern",
                    description=info["description"],
                    suggestion=f"替换为: {info['replacement']}" if info['replacement'] else "移除此代码",
                    auto_fixable=True,
                ))
        
        # 检查废弃 API
        version_key = f"{self.source_version.split('.')[0]}_to_{self.target_version.split('.')[0]}"
        deprecated = DEPRECATED_APIS.get(version_key, {})
        
        for api, info in deprecated.items():
            if api in content:
                for i, line in enumerate(lines, 1):
                    if api in line:
                        self.issues.append(CodeIssue(
                            file_path=str(file_path),
                            line_number=i,
                            line_content=line.strip(),
                            issue_type="deprecated_api",
                            description=info["description"],
                            suggestion=f"使用: {info['replacement']}",
                            auto_fixable=False,
                        ))
    
    def _analyze_xml_file(self, file_path: Path):
        """分析 XML 文件"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                lines = content.split("\n")
        except Exception:
            return
        
        # 检查废弃的 XML 元素
        deprecated_xml = {
            '<report': "检查报表是否使用 QWeb 格式",
            'report_type="sxw"': "RML 报表已废弃，请转换为 QWeb",
            't-raw=': "t-raw 已废弃，使用 t-out 或 t-esc",
        }
        
        for pattern, description in deprecated_xml.items():
            for i, line in enumerate(lines, 1):
                if pattern in line:
                    self.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=i,
                        line_content=line.strip(),
                        issue_type="deprecated_xml",
                        description=description,
                        suggestion="请根据新版本文档更新",
                        auto_fixable=False,
                    ))
    
    def generate_migration_scripts(self, module_name: str) -> Optional[MigrationScript]:
        """生成迁移脚本模板"""
        if module_name not in self.modules:
            return None
        
        module_path = self.modules[module_name]
        
        # 读取当前版本
        manifest_path = module_path / "__manifest__.py"
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                content = f.read()
            manifest = ast.literal_eval(content)
            current_version = manifest.get("version", "1.0.0")
        except:
            current_version = "1.0.0"
        
        # 生成新版本号
        parts = current_version.split(".")
        if len(parts) >= 2:
            parts[0] = self.target_version.split(".")[0]
            new_version = ".".join(parts)
        else:
            new_version = f"{self.target_version}.1.0.0"
        
        # 生成迁移脚本内容
        pre_migrate = f'''# -*- coding: utf-8 -*-
# Pre-migration script for {module_name}
# Version: {current_version} -> {new_version}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

import logging
from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    在模块升级之前执行
    用于：
    - 备份即将被修改的数据
    - 重命名字段/表（使用 openupgrade）
    - 处理即将废弃的数据结构
    """
    if not version:
        return
    
    _logger.info("Pre-migration {module_name}: %s -> {new_version}", version)
    
    env = Environment(cr, SUPERUSER_ID, {{}})
    
    # TODO: 添加预迁移逻辑
    # 示例：重命名字段
    # if openupgrade.column_exists(cr, 'table_name', 'old_column'):
    #     openupgrade.rename_columns(cr, {{'table_name': [('old_column', 'new_column')]}})
    
    _logger.info("Pre-migration {module_name} completed")
'''
        
        post_migrate = f'''# -*- coding: utf-8 -*-
# Post-migration script for {module_name}
# Version: {current_version} -> {new_version}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

import logging
from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    在模块升级之后执行
    用于：
    - 数据转换和清理
    - 计算新字段的值
    - 更新配置
    """
    if not version:
        return
    
    _logger.info("Post-migration {module_name}: %s -> {new_version}", version)
    
    env = Environment(cr, SUPERUSER_ID, {{}})
    
    # TODO: 添加后迁移逻辑
    # 示例：更新计算字段
    # records = env['model.name'].search([])
    # for record in records:
    #     record._compute_field_name()
    
    # 示例：数据清理
    # env.cr.execute("UPDATE table SET field = 'new_value' WHERE condition")
    
    _logger.info("Post-migration {module_name} completed")
'''
        
        end_migrate = f'''# -*- coding: utf-8 -*-
# End-migration script for {module_name}
# Version: {current_version} -> {new_version}
# Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}

import logging
from odoo import SUPERUSER_ID
from odoo.api import Environment

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    在所有模块升级完成后执行
    用于：
    - 跨模块的数据同步
    - 最终验证
    - 清理临时数据
    """
    if not version:
        return
    
    _logger.info("End-migration {module_name}: %s -> {new_version}", version)
    
    env = Environment(cr, SUPERUSER_ID, {{}})
    
    # TODO: 添加结束迁移逻辑
    
    _logger.info("End-migration {module_name} completed")
'''
        
        return MigrationScript(
            module_name=module_name,
            version=new_version,
            pre_migrate=pre_migrate,
            post_migrate=post_migrate,
            end_migrate=end_migrate,
        )
    
    def save_migration_scripts(self, module_name: str, output_dir: str = None) -> Optional[str]:
        """保存迁移脚本到文件"""
        scripts = self.generate_migration_scripts(module_name)
        if not scripts:
            return None
        
        if output_dir:
            base_dir = Path(output_dir)
        else:
            base_dir = self.modules[module_name]
        
        # 创建 migrations 目录
        migration_dir = base_dir / "migrations" / scripts.version
        migration_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存脚本
        (migration_dir / "pre-migrate.py").write_text(scripts.pre_migrate, encoding="utf-8")
        (migration_dir / "post-migrate.py").write_text(scripts.post_migrate, encoding="utf-8")
        (migration_dir / "end-migrate.py").write_text(scripts.end_migrate, encoding="utf-8")
        
        return str(migration_dir)
    
    def generate_checklist(self) -> UpgradeChecklist:
        """生成升级检查清单"""
        checklist = UpgradeChecklist()
        
        # 备份检查
        checklist.add_item(
            category="backup",
            title="数据库完整备份",
            description="使用 pg_dump 创建数据库完整备份，包括文件存储",
            priority="critical",
        )
        checklist.add_item(
            category="backup",
            title="代码仓库备份",
            description="确保所有代码已提交并推送到远程仓库，创建版本标签",
            priority="critical",
        )
        checklist.add_item(
            category="backup",
            title="配置文件备份",
            description="备份 odoo.conf 和其他配置文件",
            priority="high",
        )
        
        # 环境准备
        checklist.add_item(
            category="environment",
            title="测试环境准备",
            description="在独立的测试环境中进行升级测试",
            priority="critical",
        )
        checklist.add_item(
            category="environment",
            title="Python 版本检查",
            description=f"确认目标版本 {self.target_version} 的 Python 要求",
            priority="high",
        )
        checklist.add_item(
            category="environment",
            title="依赖包更新",
            description="更新 requirements.txt 中的依赖版本",
            priority="high",
        )
        
        # 代码检查
        issues_count = len(self.issues)
        checklist.add_item(
            category="code",
            title=f"代码问题修复 ({issues_count} 个)",
            description="修复所有检测到的废弃 API 和代码模式问题",
            priority="high" if issues_count > 0 else "low",
            auto_check=True,
            status="done" if issues_count == 0 else "pending",
        )
        checklist.add_item(
            category="code",
            title="Manifest 版本更新",
            description=f"将所有模块的版本号从 {self.source_version} 更新为 {self.target_version}",
            priority="high",
        )
        checklist.add_item(
            category="code",
            title="迁移脚本准备",
            description="为需要数据迁移的模块创建 migration 脚本",
            priority="medium",
        )
        
        # 数据检查
        checklist.add_item(
            category="data",
            title="自定义字段检查",
            description="检查 ir.model.fields 中的自定义字段是否兼容",
            priority="medium",
        )
        checklist.add_item(
            category="data",
            title="视图验证",
            description="检查自定义视图是否使用了废弃的元素",
            priority="medium",
        )
        checklist.add_item(
            category="data",
            title="报表检查",
            description="确认所有报表使用 QWeb 格式",
            priority="medium",
        )
        
        # 测试
        checklist.add_item(
            category="testing",
            title="单元测试执行",
            description="运行所有模块的单元测试",
            priority="high",
        )
        checklist.add_item(
            category="testing",
            title="功能回归测试",
            description="执行核心业务流程的手动测试",
            priority="critical",
        )
        checklist.add_item(
            category="testing",
            title="性能测试",
            description="对比升级前后的性能指标",
            priority="medium",
        )
        
        # 部署
        checklist.add_item(
            category="deployment",
            title="停机通知",
            description="提前通知用户升级时间和预计停机时长",
            priority="high",
        )
        checklist.add_item(
            category="deployment",
            title="回滚计划",
            description="准备详细的回滚步骤，以防升级失败",
            priority="critical",
        )
        checklist.add_item(
            category="deployment",
            title="升级后验证",
            description="升级完成后执行验证检查清单",
            priority="high",
        )
        
        return checklist
    
    def apply_auto_fixes(self, dry_run: bool = True) -> Dict[str, List[Dict]]:
        """应用自动修复"""
        fixes_applied = {}
        
        for issue in self.issues:
            if not issue.auto_fixable:
                continue
            
            file_path = issue.file_path
            if file_path not in fixes_applied:
                fixes_applied[file_path] = []
            
            if not dry_run:
                # 实际应用修复
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 应用正则替换
                    for pattern, info in CODE_PATTERNS.items():
                        if re.search(pattern, content):
                            new_content = re.sub(pattern, info["replacement"], content)
                            if new_content != content:
                                content = new_content
                                fixes_applied[file_path].append({
                                    "line": issue.line_number,
                                    "description": issue.description,
                                    "applied": True,
                                })
                    
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                        
                except Exception as e:
                    fixes_applied[file_path].append({
                        "line": issue.line_number,
                        "description": issue.description,
                        "applied": False,
                        "error": str(e),
                    })
            else:
                # Dry run 只记录
                fixes_applied[file_path].append({
                    "line": issue.line_number,
                    "description": issue.description,
                    "would_apply": True,
                })
        
        return fixes_applied
    
    def generate_report(self) -> Dict[str, Any]:
        """生成完整报告"""
        self.scan_modules()
        issues = self.analyze_code()
        checklist = self.generate_checklist()
        
        # 按模块分组问题
        issues_by_module = {}
        for issue in issues:
            # 从路径中提取模块名
            for module_name, module_path in self.modules.items():
                if str(module_path) in issue.file_path:
                    if module_name not in issues_by_module:
                        issues_by_module[module_name] = []
                    issues_by_module[module_name].append(issue.to_dict())
                    break
        
        # 统计
        auto_fixable = sum(1 for i in issues if i.auto_fixable)
        manual_fix = len(issues) - auto_fixable
        
        return {
            "source_version": self.source_version,
            "target_version": self.target_version,
            "modules_count": len(self.modules),
            "modules": list(self.modules.keys()),
            "issues_count": len(issues),
            "auto_fixable_count": auto_fixable,
            "manual_fix_count": manual_fix,
            "issues_by_module": issues_by_module,
            "checklist": checklist.to_dict(),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
