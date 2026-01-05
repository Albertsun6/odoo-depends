"""
依赖关系可视化模块
"""

import json
from pathlib import Path
from typing import Optional, Dict, List
from pyvis.network import Network
import networkx as nx

from .analyzer import OdooModuleAnalyzer


class DependencyVisualizer:
    """依赖关系可视化器"""
    
    # 颜色配置
    COLORS = {
        'application': '#e74c3c',      # 红色 - 应用模块
        'core': '#3498db',             # 蓝色 - 核心模块  
        'external': '#95a5a6',         # 灰色 - 外部未扫描模块
        'normal': '#2ecc71',           # 绿色 - 普通模块
        'not_installable': '#f39c12',  # 橙色 - 不可安装
    }
    
    def __init__(self, analyzer: OdooModuleAnalyzer):
        """
        初始化可视化器
        
        Args:
            analyzer: OdooModuleAnalyzer实例
        """
        self.analyzer = analyzer
        
    def _get_node_color(self, node: str, attrs: dict) -> str:
        """获取节点颜色"""
        if attrs.get('is_external'):
            return self.COLORS['external']
        if attrs.get('is_core'):
            return self.COLORS['core']
        if not attrs.get('installable', True):
            return self.COLORS['not_installable']
        if attrs.get('application'):
            return self.COLORS['application']
        return self.COLORS['normal']
    
    def _get_node_size(self, node: str, attrs: dict) -> int:
        """获取节点大小（基于被依赖次数）"""
        if self.analyzer.graph is None:
            return 20
        in_degree = self.analyzer.graph.in_degree(node)
        return max(15, min(50, 15 + in_degree * 3))
    
    def generate_interactive_html(
        self,
        output_path: str = "dependency_graph.html",
        height: str = "800px",
        width: str = "100%",
        show_physics_buttons: bool = True,
        filter_modules: Optional[List[str]] = None,
        include_external: bool = True,
    ) -> str:
        """
        生成交互式HTML依赖图
        
        Args:
            output_path: 输出文件路径
            height: 图表高度
            width: 图表宽度
            show_physics_buttons: 是否显示物理引擎控制按钮
            filter_modules: 只显示指定模块及其依赖
            include_external: 是否包含外部依赖
            
        Returns:
            输出文件路径
        """
        if not self.analyzer.modules:
            self.analyzer.scan_modules()
        if self.analyzer.graph is None:
            self.analyzer.build_dependency_graph()
            
        # 创建pyvis网络
        net = Network(
            height=height,
            width=width,
            directed=True,
            notebook=False,
            bgcolor="#1a1a2e",
            font_color="#ffffff",
            cdn_resources='remote',  # 使用CDN加载资源，避免本地lib依赖
        )
        
        # 设置物理引擎参数（不使用show_buttons避免configure错误）
        net.set_options('''
        {
            "configure": {
                "enabled": false
            },
            "physics": {
                "barnesHut": {
                    "gravitationalConstant": -30000,
                    "centralGravity": 0.3,
                    "springLength": 150,
                    "springConstant": 0.05,
                    "damping": 0.09
                },
                "maxVelocity": 50,
                "minVelocity": 0.1,
                "stabilization": {
                    "iterations": 100
                }
            },
            "edges": {
                "arrows": {
                    "to": {
                        "enabled": true,
                        "scaleFactor": 0.5
                    }
                },
                "color": {
                    "color": "#4a4a6a",
                    "highlight": "#e74c3c",
                    "hover": "#3498db"
                },
                "smooth": {
                    "type": "curvedCW",
                    "roundness": 0.2
                }
            },
            "nodes": {
                "borderWidth": 2,
                "borderWidthSelected": 4,
                "font": {
                    "size": 14,
                    "face": "Fira Code, Monaco, monospace"
                },
                "shadow": true
            },
            "interaction": {
                "hover": true,
                "tooltipDelay": 200,
                "hideEdgesOnDrag": true,
                "multiselect": true
            }
        }
        ''')
        
        # 确定要显示的节点
        nodes_to_show = set()
        if filter_modules:
            for module in filter_modules:
                nodes_to_show.add(module)
                nodes_to_show.update(self.analyzer.get_all_dependencies(module))
        else:
            nodes_to_show = set(self.analyzer.graph.nodes())
            
        # 添加节点
        for node in nodes_to_show:
            attrs = dict(self.analyzer.graph.nodes[node])
            
            if not include_external and attrs.get('is_external'):
                continue
                
            color = self._get_node_color(node, attrs)
            size = self._get_node_size(node, attrs)
            
            # 构建tooltip
            tooltip_parts = [f"<b>{node}</b>"]
            if 'version' in attrs:
                tooltip_parts.append(f"版本: {attrs['version']}")
            if 'category' in attrs:
                tooltip_parts.append(f"分类: {attrs['category']}")
            if attrs.get('application'):
                tooltip_parts.append("类型: 应用")
            if attrs.get('is_core'):
                tooltip_parts.append("类型: 核心模块")
            if attrs.get('is_external'):
                tooltip_parts.append("类型: 外部依赖")
            if 'path' in attrs:
                tooltip_parts.append(f"路径: {attrs['path']}")
                
            tooltip = "<br>".join(tooltip_parts)
            
            net.add_node(
                node,
                label=node,
                color=color,
                size=size,
                title=tooltip,
                shape='dot',
            )
            
        # 添加边
        for source, target in self.analyzer.graph.edges():
            if source in nodes_to_show and target in nodes_to_show:
                source_attrs = self.analyzer.graph.nodes[source]
                target_attrs = self.analyzer.graph.nodes[target]
                
                if not include_external and (
                    source_attrs.get('is_external') or target_attrs.get('is_external')
                ):
                    continue
                    
                net.add_edge(source, target)
                
        # 保存HTML
        net.save_graph(output_path)
        
        # 增强HTML添加图例和统计信息
        self._enhance_html(output_path)
        
        return output_path
    
    def _enhance_html(self, html_path: str) -> None:
        """增强HTML添加图例和统计信息"""
        stats = self.analyzer.get_statistics()
        
        # 读取生成的HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 添加自定义样式和图例
        legend_html = f'''
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }}
            .legend {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: rgba(26, 26, 46, 0.95);
                padding: 20px;
                border-radius: 12px;
                color: white;
                z-index: 1000;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.1);
                max-width: 280px;
            }}
            .legend h3 {{
                margin: 0 0 15px 0;
                font-size: 16px;
                color: #e74c3c;
                border-bottom: 1px solid rgba(255,255,255,0.2);
                padding-bottom: 10px;
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                margin: 8px 0;
                font-size: 13px;
            }}
            .legend-color {{
                width: 16px;
                height: 16px;
                border-radius: 50%;
                margin-right: 10px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            }}
            .stats {{
                margin-top: 15px;
                padding-top: 15px;
                border-top: 1px solid rgba(255,255,255,0.2);
            }}
            .stats h4 {{
                margin: 0 0 10px 0;
                font-size: 14px;
                color: #3498db;
            }}
            .stats p {{
                margin: 5px 0;
                font-size: 12px;
                color: rgba(255,255,255,0.8);
            }}
            .title-bar {{
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                padding: 15px 30px;
                color: white;
                z-index: 999;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .title-bar h1 {{
                margin: 0;
                font-size: 22px;
                background: linear-gradient(135deg, #e74c3c, #3498db);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                background-clip: text;
            }}
            .title-bar .info {{
                font-size: 13px;
                color: rgba(255,255,255,0.7);
            }}
            #mynetwork {{
                margin-top: 60px !important;
            }}
        </style>
        
        <div class="title-bar">
            <h1>🔗 Odoo 模块依赖关系图</h1>
            <div class="info">共 {stats['total_modules']} 个模块 | {stats['total_dependencies']} 个依赖关系</div>
        </div>
        
        <div class="legend">
            <h3>📊 图例</h3>
            <div class="legend-item">
                <div class="legend-color" style="background: {self.COLORS['application']}"></div>
                <span>应用模块 (Application)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: {self.COLORS['core']}"></div>
                <span>核心模块 (Core)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: {self.COLORS['normal']}"></div>
                <span>普通模块 (Normal)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: {self.COLORS['external']}"></div>
                <span>外部依赖 (External)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: {self.COLORS['not_installable']}"></div>
                <span>不可安装 (Not Installable)</span>
            </div>
            
            <div class="stats">
                <h4>📈 统计信息</h4>
                <p>📦 扫描模块数: {stats['total_modules']}</p>
                <p>🔗 依赖关系数: {stats['total_dependencies']}</p>
                <p>📱 应用数量: {len(stats['applications'])}</p>
                <p>⚠️ 循环依赖: {len(stats['circular_dependencies'])}</p>
                <p>❓ 缺失依赖: {len(stats['missing_dependencies'])}</p>
            </div>
        </div>
        '''
        
        # 在</head>前插入样式和HTML
        content = content.replace('</head>', f'{legend_html}</head>')
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
    def generate_module_tree(self, module_name: str, max_depth: int = 5) -> str:
        """
        生成模块的依赖树（文本格式）
        
        Args:
            module_name: 模块名
            max_depth: 最大深度
            
        Returns:
            树形结构字符串
        """
        if self.analyzer.graph is None:
            self.analyzer.build_dependency_graph()
            
        lines = [f"📦 {module_name}"]
        self._add_tree_nodes(module_name, lines, "", max_depth, set())
        return "\n".join(lines)
    
    def _add_tree_nodes(
        self,
        node: str,
        lines: List[str],
        prefix: str,
        max_depth: int,
        visited: set,
    ) -> None:
        """递归添加树节点"""
        if max_depth <= 0 or node in visited:
            return
            
        visited.add(node)
        
        if node not in self.analyzer.graph:
            return
            
        successors = list(self.analyzer.graph.successors(node))
        for i, child in enumerate(successors):
            is_last = i == len(successors) - 1
            connector = "└── " if is_last else "├── "
            
            # 添加标记
            markers = []
            attrs = self.analyzer.graph.nodes.get(child, {})
            if attrs.get('is_core'):
                markers.append("🔵")
            elif attrs.get('is_external'):
                markers.append("⚪")
            elif attrs.get('application'):
                markers.append("🔴")
            else:
                markers.append("🟢")
                
            marker = "".join(markers)
            lines.append(f"{prefix}{connector}{marker} {child}")
            
            # 递归
            new_prefix = prefix + ("    " if is_last else "│   ")
            self._add_tree_nodes(child, lines, new_prefix, max_depth - 1, visited.copy())
