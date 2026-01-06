"""
Flask Web应用 - 提供Odoo依赖分析的完整可视化界面
"""

import os
import json
import tempfile
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify, send_file

from .analyzer import OdooModuleAnalyzer
from .visualizer import DependencyVisualizer
from .upgrade_analyzer import UpgradeAnalyzer, ModelAnalyzer
from .migration_helper import MigrationHelper
from .cloud_storage import get_storage, LocalStorage, AnalysisRecord, generate_record_id
from datetime import datetime


app = Flask(__name__)
app.config['SECRET_KEY'] = 'odoo-depends-analyzer-secret-key'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

# 全局分析器实例
analyzer = None
visualizer = None
upgrade_analyzer = UpgradeAnalyzer()
storage = get_storage()  # 云存储/本地存储实例


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Odoo 模块依赖分析器</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/vis-network.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.2/dist/dist/vis-network.min.css" />
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-tertiary: #16213e;
            --bg-card: rgba(26, 26, 46, 0.9);
            --accent-red: #e74c3c;
            --accent-blue: #3498db;
            --accent-green: #2ecc71;
            --accent-orange: #f39c12;
            --accent-purple: #9b59b6;
            --accent-cyan: #00d4ff;
            --text-primary: #ffffff;
            --text-secondary: rgba(255, 255, 255, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Noto Sans SC', 'JetBrains Mono', sans-serif;
            background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 50%, var(--bg-tertiary) 100%);
            min-height: 100vh;
            color: var(--text-primary);
        }
        
        body::before {
            content: '';
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: 
                radial-gradient(circle at 20% 80%, rgba(231, 76, 60, 0.08) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(52, 152, 219, 0.08) 0%, transparent 50%);
            pointer-events: none;
            z-index: -1;
        }

        /* 侧边栏 */
        .sidebar {
            position: fixed;
            left: 0; top: 0;
            width: 280px;
            height: 100vh;
            background: var(--bg-card);
            border-right: 1px solid var(--border-color);
            padding: 20px;
            overflow-y: auto;
            z-index: 100;
            backdrop-filter: blur(10px);
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--accent-red), var(--accent-cyan));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 30px;
            text-align: center;
        }
        
        .nav-section {
            margin-bottom: 25px;
        }
        
        .nav-section-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            color: var(--text-secondary);
            margin-bottom: 10px;
            letter-spacing: 1px;
        }
        
        .nav-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px 15px;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-bottom: 5px;
            font-size: 0.95rem;
        }
        
        .nav-item:hover {
            background: rgba(255,255,255,0.05);
        }
        
        .nav-item.active {
            background: linear-gradient(135deg, var(--accent-red), var(--accent-purple));
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
        }
        
        .nav-item .icon { font-size: 1.2rem; }

        /* 主内容区 */
        .main-content {
            margin-left: 280px;
            padding: 30px;
            min-height: 100vh;
        }
        
        .page { display: none; }
        .page.active { display: block; animation: fadeIn 0.3s ease; }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(100px); }
            to { opacity: 1; transform: translateX(0); }
        }
        
        @keyframes slideOut {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(100px); }
        }

        /* 卡片 */
        .card {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow);
            backdrop-filter: blur(10px);
        }
        
        .card-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 1.2rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .card-title::before {
            content: '';
            width: 4px;
            height: 20px;
            background: linear-gradient(180deg, var(--accent-red), var(--accent-blue));
            border-radius: 2px;
        }

        /* 表单元素 */
        .form-group { margin-bottom: 20px; }
        
        label {
            display: block;
            font-size: 0.9rem;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 12px 16px;
            font-size: 0.95rem;
            font-family: 'JetBrains Mono', monospace;
            background: var(--bg-primary);
            border: 1px solid var(--border-color);
            border-radius: 10px;
            color: var(--text-primary);
            transition: all 0.3s ease;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: var(--accent-blue);
            box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
        }
        
        textarea { min-height: 100px; resize: vertical; }

        /* 按钮 */
        .btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            font-size: 0.95rem;
            font-weight: 600;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-red), var(--accent-purple));
            color: white;
            box-shadow: 0 4px 15px rgba(231, 76, 60, 0.3);
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(231, 76, 60, 0.4);
        }
        
        .btn-secondary {
            background: var(--bg-tertiary);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        
        .btn-secondary:hover {
            background: var(--bg-secondary);
            border-color: var(--accent-blue);
        }
        
        .btn-group { display: flex; gap: 10px; flex-wrap: wrap; }

        /* 统计网格 */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        
        .stat-card {
            background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-primary));
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid var(--border-color);
        }
        
        .stat-value {
            font-size: 2rem;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .stat-value.red { color: var(--accent-red); }
        .stat-value.blue { color: var(--accent-blue); }
        .stat-value.green { color: var(--accent-green); }
        .stat-value.orange { color: var(--accent-orange); }
        .stat-value.purple { color: var(--accent-purple); }
        
        .stat-label { font-size: 0.85rem; color: var(--text-secondary); margin-top: 5px; }

        /* 依赖图容器 */
        #graph-container {
            width: 100%;
            height: 600px;
            background: var(--bg-primary);
            border-radius: 12px;
            border: 1px solid var(--border-color);
        }

        /* 模块列表 */
        .module-list {
            max-height: 500px;
            overflow-y: auto;
        }
        
        .module-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 15px;
            background: var(--bg-primary);
            border-radius: 10px;
            margin-bottom: 8px;
            border: 1px solid var(--border-color);
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .module-item:hover {
            border-color: var(--accent-blue);
            transform: translateX(5px);
        }
        
        .module-name {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            color: var(--accent-green);
        }
        
        .module-info {
            display: flex;
            gap: 15px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 20px;
            font-size: 0.7rem;
            font-weight: 600;
        }
        
        .badge-app { background: rgba(231, 76, 60, 0.2); color: var(--accent-red); }
        .badge-core { background: rgba(52, 152, 219, 0.2); color: var(--accent-blue); }

        /* 依赖树 */
        .tree-container {
            background: var(--bg-primary);
            border-radius: 10px;
            padding: 20px;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            white-space: pre;
            overflow-x: auto;
            max-height: 500px;
            overflow-y: auto;
            line-height: 1.6;
        }

        /* 问题列表 */
        .issue-item {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 10px;
        }
        
        .issue-item.warning {
            background: rgba(243, 156, 18, 0.1);
            border: 1px solid var(--accent-orange);
        }
        
        .issue-item.error {
            background: rgba(231, 76, 60, 0.1);
            border: 1px solid var(--accent-red);
        }
        
        .issue-item.success {
            background: rgba(46, 204, 113, 0.1);
            border: 1px solid var(--accent-green);
        }
        
        .issue-title {
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        /* 安装顺序 */
        .order-list {
            counter-reset: order;
        }
        
        .order-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 12px 15px;
            background: var(--bg-primary);
            border-radius: 8px;
            margin-bottom: 5px;
            border: 1px solid var(--border-color);
        }
        
        .order-item::before {
            counter-increment: order;
            content: counter(order);
            display: flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            background: var(--accent-blue);
            border-radius: 50%;
            font-weight: 600;
            font-size: 0.85rem;
        }
        
        .order-item.core::before { background: var(--accent-purple); }

        /* 图例 */
        .legend {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            margin-bottom: 15px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 0.85rem;
        }
        
        .legend-color {
            width: 14px;
            height: 14px;
            border-radius: 50%;
        }

        /* 加载状态 */
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .loading.active { display: block; }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--border-color);
            border-top-color: var(--accent-blue);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin { to { transform: rotate(360deg); } }

        /* 搜索框 */
        .search-box {
            position: relative;
            margin-bottom: 15px;
        }
        
        .search-box input { padding-left: 40px; }
        
        .search-box::before {
            content: '🔍';
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
        }

        /* 空状态 */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
        }
        
        .empty-state .icon { font-size: 4rem; margin-bottom: 20px; opacity: 0.5; }
        
        /* 滚动条 */
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-primary); border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: var(--bg-tertiary); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: var(--accent-blue); }

        /* 响应式 */
        @media (max-width: 768px) {
            .sidebar { width: 100%; height: auto; position: relative; }
            .main-content { margin-left: 0; }
        }
    </style>
</head>
<body>
    <!-- 侧边栏 -->
    <div class="sidebar">
        <div class="logo">🔗 Odoo Depends</div>
        
        <div class="nav-section">
            <div class="nav-section-title">配置</div>
            <div class="nav-item active" onclick="showPage('scan')">
                <span class="icon">📂</span> 扫描模块
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">分析</div>
            <div class="nav-item" onclick="showPage('graph')">
                <span class="icon">📊</span> 依赖图
            </div>
            <div class="nav-item" onclick="showPage('modules')">
                <span class="icon">📦</span> 模块列表
            </div>
            <div class="nav-item" onclick="showPage('tree')">
                <span class="icon">🌳</span> 依赖树
            </div>
            <div class="nav-item" onclick="showPage('order')">
                <span class="icon">📋</span> 安装顺序
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">诊断</div>
            <div class="nav-item" onclick="showPage('issues')">
                <span class="icon">🔍</span> 问题检查
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">升级分析</div>
            <div class="nav-item" onclick="showPage('models')">
                <span class="icon">🗄️</span> 模型分析
            </div>
            <div class="nav-item" onclick="showPage('impact')">
                <span class="icon">⚡</span> 影响评估
            </div>
            <div class="nav-item" onclick="showPage('compare')">
                <span class="icon">🔄</span> 版本对比
            </div>
            <div class="nav-item" onclick="showPage('migration')">
                <span class="icon">🛠️</span> 升级工具
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">存储</div>
            <div class="nav-item" onclick="window.location.href='/history'">
                <span class="icon">📚</span> 分析历史
            </div>
        </div>
        
        <div class="nav-section">
            <div class="nav-section-title">导出</div>
            <div class="nav-item" onclick="exportData('json')">
                <span class="icon">📄</span> 导出 JSON
            </div>
            <div class="nav-item" onclick="exportData('html')">
                <span class="icon">🌐</span> 导出 HTML
            </div>
        </div>
    </div>

    <!-- 主内容 -->
    <div class="main-content">
        <!-- 扫描页面 -->
        <div class="page active" id="page-scan">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">扫描 Odoo 模块</h2>
                </div>
                
                <!-- 历史路径选择 -->
                <div class="form-group" id="history-group" style="display: none;">
                    <label>📂 历史路径</label>
                    <select id="path-history" onchange="loadHistoryPath()" style="width: 100%; padding: 12px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-primary); margin-bottom: 10px;">
                        <option value="">-- 选择历史路径 --</option>
                    </select>
                </div>
                
                <!-- 已上传分析历史 -->
                <div class="form-group" id="uploaded-history-group" style="display: none;">
                    <label>📦 已上传的分析</label>
                    <select id="uploaded-history" onchange="loadUploadedHistory()" style="width: 100%; padding: 12px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-primary); margin-bottom: 10px;">
                        <option value="">-- 选择已上传的分析 --</option>
                    </select>
                </div>
                
                <!-- 快捷路径按钮 -->
                <div class="form-group">
                    <label>⚡ 快速操作</label>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px;">
                        <button class="btn btn-primary" style="font-size: 0.85rem; padding: 8px 16px;" onclick="document.getElementById('zip-upload').click()">📤 上传 ZIP</button>
                        <button class="btn btn-secondary" style="font-size: 0.85rem; padding: 8px 12px;" onclick="openFolderBrowser()">📂 浏览文件夹</button>
                        <button class="btn btn-secondary" style="font-size: 0.85rem; padding: 8px 12px;" onclick="loadDemoModules()">🎯 加载示例</button>
                        <button class="btn btn-secondary" style="font-size: 0.85rem; padding: 8px 12px;" onclick="clearPaths()">🗑️ 清空</button>
                    </div>
                    <input type="file" id="zip-upload" accept=".zip" style="display:none;" onchange="uploadZip(this)">
                    <p style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 8px;">
                        💡 在线版请使用「上传 ZIP」功能，本地版可使用「浏览文件夹」
                    </p>
                </div>
                
                <div class="form-group" id="local-path-group">
                    <label>模块路径（每行一个）- 仅本地版可用</label>
                    <textarea id="paths" placeholder="点击上方快速选择按钮，或手动输入路径"></textarea>
                </div>
                <div class="btn-group">
                    <button class="btn btn-primary" onclick="scanModules()">🔍 开始扫描</button>
                </div>
            </div>
            
            <div class="loading" id="scan-loading">
                <div class="spinner"></div>
                <p>正在扫描模块...</p>
            </div>
            
            <div id="scan-results" style="display: none;">
                <div class="card">
                    <div class="card-header">
                        <h2 class="card-title">统计概览</h2>
                        <button class="btn btn-primary" onclick="saveToHistory()">💾 保存到历史</button>
                    </div>
                    <div class="stats-grid" id="stats-grid"></div>
                </div>
            </div>
        </div>

        <!-- 依赖图页面 -->
        <div class="page" id="page-graph">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">模块依赖关系图</h2>
                    <div class="btn-group">
                        <button class="btn btn-secondary" onclick="renderGraph(false)">📊 完整图</button>
                        <button class="btn btn-secondary" onclick="renderGraph(true)">🎯 仅自定义</button>
                    </div>
                </div>
                <div class="legend">
                    <div class="legend-item"><div class="legend-color" style="background:#e74c3c"></div> 应用模块</div>
                    <div class="legend-item"><div class="legend-color" style="background:#3498db"></div> 核心模块</div>
                    <div class="legend-item"><div class="legend-color" style="background:#2ecc71"></div> 普通模块</div>
                    <div class="legend-item"><div class="legend-color" style="background:#95a5a6"></div> 外部依赖</div>
                </div>
                <div id="graph-container"></div>
            </div>
        </div>

        <!-- 模块列表页面 -->
        <div class="page" id="page-modules">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">模块列表</h2>
                </div>
                <div class="search-box">
                    <input type="text" id="module-search" placeholder="搜索模块..." oninput="filterModules()">
                </div>
                <div class="module-list" id="module-list"></div>
            </div>
        </div>

        <!-- 依赖树页面 -->
        <div class="page" id="page-tree">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">模块依赖树</h2>
                </div>
                <div class="form-group">
                    <label>选择模块</label>
                    <select id="tree-module" onchange="showTree()">
                        <option value="">-- 请先扫描模块 --</option>
                    </select>
                </div>
                <div class="tree-container" id="tree-output"></div>
            </div>
        </div>

        <!-- 安装顺序页面 -->
        <div class="page" id="page-order">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">安装顺序</h2>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px;">
                    按照依赖关系计算的正确安装顺序（拓扑排序）
                </p>
                <div class="order-list" id="order-list"></div>
            </div>
        </div>

        <!-- 问题检查页面 -->
        <div class="page" id="page-issues">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">问题检查</h2>
                    <button class="btn btn-secondary" onclick="checkIssues()">🔄 重新检查</button>
                </div>
                <div id="issues-list"></div>
            </div>
        </div>

        <!-- 模型分析页面 -->
        <div class="page" id="page-models">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">数据模型分析</h2>
                    <button class="btn btn-primary" onclick="analyzeModels()">🔍 分析模型</button>
                </div>
                <div class="form-group">
                    <label>选择要分析的模块</label>
                    <select id="model-module-select" onchange="filterModelsByModule()">
                        <option value="">-- 全部模块 --</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>搜索模型</label>
                    <input type="text" id="model-search" placeholder="输入模型名称搜索..." oninput="filterModelsTable()">
                </div>
                <div id="model-stats" style="margin-bottom: 20px;"></div>
                <div class="module-list" id="models-list" style="max-height: 600px;"></div>
            </div>
        </div>

        <!-- 升级影响评估页面 -->
        <div class="page" id="page-impact">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">升级影响评估</h2>
                </div>
                <div class="form-group">
                    <label>选择要评估的模块</label>
                    <select id="impact-module" onchange="assessImpact()">
                        <option value="">-- 请选择模块 --</option>
                    </select>
                </div>
                <div id="impact-result"></div>
            </div>
        </div>

        <!-- 版本对比页面 -->
        <div class="page" id="page-compare">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">版本对比分析</h2>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div class="form-group">
                        <label>源版本路径（当前版本）</label>
                        <textarea id="source-paths" rows="3" placeholder="/path/to/odoo14/addons"></textarea>
                    </div>
                    <div class="form-group">
                        <label>目标版本路径（升级目标）</label>
                        <textarea id="target-paths" rows="3" placeholder="/path/to/odoo17/addons"></textarea>
                    </div>
                </div>
                <button class="btn btn-primary" onclick="compareVersions()">🔄 对比版本</button>
                <div id="compare-result" style="margin-top: 20px;"></div>
            </div>
        </div>
        
        <!-- 升级工具页面 -->
        <div class="page" id="page-migration">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">🛠️ 升级辅助工具</h2>
                </div>
                <p style="color: var(--text-secondary); margin-bottom: 20px;">
                    分析代码问题、生成迁移脚本、创建升级检查清单
                </p>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div class="form-group">
                        <label>源版本</label>
                        <select id="migration-source" style="width:100%;padding:10px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:8px;color:var(--text-primary);">
                            <option value="14.0">Odoo 14.0</option>
                            <option value="15.0">Odoo 15.0</option>
                            <option value="16.0" selected>Odoo 16.0</option>
                            <option value="17.0">Odoo 17.0</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>目标版本</label>
                        <select id="migration-target" style="width:100%;padding:10px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:8px;color:var(--text-primary);">
                            <option value="15.0">Odoo 15.0</option>
                            <option value="16.0">Odoo 16.0</option>
                            <option value="17.0" selected>Odoo 17.0</option>
                            <option value="18.0">Odoo 18.0</option>
                        </select>
                    </div>
                </div>
                
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="btn btn-primary" onclick="analyzeMigration()">🔍 分析代码问题</button>
                    <button class="btn btn-secondary" onclick="generateChecklist()">📋 生成检查清单</button>
                    <button class="btn btn-secondary" onclick="showScriptGenerator()">📝 生成迁移脚本</button>
                    <button class="btn" style="background: linear-gradient(135deg, #f39c12, #e67e22); color: white;" onclick="previewAutoFix()">🔧 预览自动修复</button>
                </div>
            </div>
            
            <div id="migration-result" style="margin-top: 20px;"></div>
        </div>
    </div>

    <script>
        let moduleData = null;
        let network = null;
        
        // 显示通知
        function showNotification(message, type = 'info') {
            const notification = document.createElement('div');
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 25px;
                border-radius: 10px;
                color: white;
                font-weight: 500;
                z-index: 10000;
                animation: slideIn 0.3s ease;
                background: ${type === 'success' ? 'linear-gradient(135deg, #2ecc71, #27ae60)' : 
                             type === 'error' ? 'linear-gradient(135deg, #e74c3c, #c0392b)' :
                             'linear-gradient(135deg, #3498db, #2980b9)'};
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            `;
            notification.textContent = message;
            document.body.appendChild(notification);
            
            setTimeout(() => {
                notification.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => notification.remove(), 300);
            }, 3000);
        }
        
        function showPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            document.getElementById('page-' + pageId).classList.add('active');
            event.currentTarget.classList.add('active');
            
            // 页面切换时的特殊处理
            if (pageId === 'graph' && moduleData) {
                setTimeout(() => renderGraph(false), 100);
            }
            if (pageId === 'issues' && moduleData) {
                checkIssues();
            }
            if (pageId === 'order' && moduleData) {
                showOrder();
            }
        }
        
        // ========== 升级工具 ==========
        let migrationReport = null;
        
        async function analyzeMigration() {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            const sourceVersion = document.getElementById('migration-source').value;
            const targetVersion = document.getElementById('migration-target').value;
            
            try {
                const response = await fetch('/api/migration/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_version: sourceVersion, target_version: targetVersion })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('分析失败: ' + data.error);
                    return;
                }
                
                migrationReport = data;
                renderMigrationReport(data);
                showNotification('✅ 代码分析完成', 'success');
            } catch (error) {
                alert('分析失败: ' + error.message);
            }
        }
        
        function renderMigrationReport(data) {
            const resultEl = document.getElementById('migration-result');
            
            // 统计卡片
            let html = `
                <div class="stats-grid" style="margin-bottom: 20px;">
                    <div class="stat-card"><div class="stat-value blue">${data.modules_count}</div><div class="stat-label">扫描模块</div></div>
                    <div class="stat-card"><div class="stat-value ${data.issues_count > 0 ? 'red' : 'green'}">${data.issues_count}</div><div class="stat-label">代码问题</div></div>
                    <div class="stat-card"><div class="stat-value orange">${data.auto_fixable_count}</div><div class="stat-label">可自动修复</div></div>
                    <div class="stat-card"><div class="stat-value purple">${data.manual_fix_count}</div><div class="stat-label">需手动修复</div></div>
                </div>
            `;
            
            // 问题列表
            if (data.issues_count > 0) {
                html += '<div class="card"><h3 style="color: var(--accent-red); margin-bottom: 15px;">⚠️ 代码问题</h3>';
                
                for (const [moduleName, issues] of Object.entries(data.issues_by_module)) {
                    html += `<div style="margin-bottom: 15px;">
                        <h4 style="color: var(--accent-cyan); margin-bottom: 10px;">📦 ${moduleName} (${issues.length} 个问题)</h4>
                        <div style="background: var(--bg-primary); border-radius: 8px; padding: 10px; max-height: 300px; overflow-y: auto;">
                    `;
                    
                    for (const issue of issues.slice(0, 20)) {
                        const autoTag = issue.auto_fixable ? 
                            '<span style="background: var(--accent-green); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem; margin-left: 5px;">可自动修复</span>' : '';
                        html += `
                            <div style="padding: 8px; border-bottom: 1px solid var(--border-color);">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="color: var(--text-secondary); font-family: var(--font-mono); font-size: 0.8rem;">行 ${issue.line_number}</span>
                                    ${autoTag}
                                </div>
                                <div style="color: var(--accent-orange); margin: 5px 0;">${issue.description}</div>
                                <div style="color: var(--text-secondary); font-size: 0.85rem;">💡 ${issue.suggestion}</div>
                                <code style="display: block; background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; margin-top: 5px; font-size: 0.8rem; overflow-x: auto;">${issue.line_content}</code>
                            </div>
                        `;
                    }
                    
                    if (issues.length > 20) {
                        html += `<div style="padding: 10px; color: var(--text-secondary);">... 还有 ${issues.length - 20} 个问题</div>`;
                    }
                    
                    html += '</div></div>';
                }
                
                html += '</div>';
            } else {
                html += '<div class="card" style="text-align: center; padding: 40px;"><span style="font-size: 3rem;">🎉</span><h3 style="margin-top: 15px; color: var(--accent-green);">代码检查通过！</h3><p style="color: var(--text-secondary);">没有检测到需要修改的问题</p></div>';
            }
            
            resultEl.innerHTML = html;
        }
        
        function generateChecklist() {
            if (!migrationReport) {
                alert('请先分析代码问题');
                return;
            }
            
            const checklist = migrationReport.checklist;
            const resultEl = document.getElementById('migration-result');
            
            // 按分类分组
            const categories = {
                backup: { icon: '💾', title: '备份', items: [] },
                environment: { icon: '🖥️', title: '环境准备', items: [] },
                code: { icon: '📝', title: '代码检查', items: [] },
                data: { icon: '🗄️', title: '数据检查', items: [] },
                testing: { icon: '🧪', title: '测试', items: [] },
                deployment: { icon: '🚀', title: '部署', items: [] },
            };
            
            for (const item of checklist.items) {
                if (categories[item.category]) {
                    categories[item.category].items.push(item);
                }
            }
            
            let html = '<div class="card"><h3 style="margin-bottom: 20px;">📋 升级检查清单</h3>';
            
            for (const [key, cat] of Object.entries(categories)) {
                if (cat.items.length === 0) continue;
                
                html += `<div style="margin-bottom: 20px;">
                    <h4 style="color: var(--accent-cyan); margin-bottom: 10px;">${cat.icon} ${cat.title}</h4>
                    <div style="background: var(--bg-primary); border-radius: 8px; padding: 10px;">
                `;
                
                for (const item of cat.items) {
                    const priorityColors = { critical: '#e74c3c', high: '#f39c12', medium: '#3498db', low: '#95a5a6' };
                    const priorityLabels = { critical: '紧急', high: '高', medium: '中', low: '低' };
                    const statusIcon = item.status === 'done' ? '✅' : '⬜';
                    
                    html += `
                        <div style="padding: 10px; border-bottom: 1px solid var(--border-color); display: flex; align-items: flex-start; gap: 10px;">
                            <span style="font-size: 1.2rem; cursor: pointer;" onclick="this.textContent = this.textContent === '⬜' ? '✅' : '⬜'">${statusIcon}</span>
                            <div style="flex: 1;">
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <strong>${item.title}</strong>
                                    <span style="background: ${priorityColors[item.priority]}; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7rem;">${priorityLabels[item.priority]}</span>
                                </div>
                                <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 5px;">${item.description}</div>
                            </div>
                        </div>
                    `;
                }
                
                html += '</div></div>';
            }
            
            html += '<button class="btn btn-primary" onclick="printChecklist()" style="margin-top: 15px;">🖨️ 打印清单</button></div>';
            
            resultEl.innerHTML = html;
            showNotification('📋 检查清单已生成', 'success');
        }
        
        function printChecklist() {
            window.print();
        }
        
        function showScriptGenerator() {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            const modules = Object.keys(moduleData.modules);
            const resultEl = document.getElementById('migration-result');
            
            let html = '<div class="card"><h3 style="margin-bottom: 20px;">📝 生成迁移脚本</h3>';
            html += '<p style="color: var(--text-secondary); margin-bottom: 15px;">选择模块生成迁移脚本模板（pre-migrate.py, post-migrate.py, end-migrate.py）</p>';
            
            html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px;">';
            
            for (const mod of modules) {
                html += `
                    <div style="background: var(--bg-primary); padding: 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <span>📦 ${mod}</span>
                        <button class="btn btn-sm" style="background: var(--accent-cyan); color: white; padding: 5px 10px; font-size: 0.8rem;" onclick="generateScript('${mod}')">生成</button>
                    </div>
                `;
            }
            
            html += '</div></div>';
            resultEl.innerHTML = html;
        }
        
        async function generateScript(moduleName) {
            const sourceVersion = document.getElementById('migration-source').value;
            const targetVersion = document.getElementById('migration-target').value;
            
            try {
                const response = await fetch('/api/migration/scripts/' + moduleName + '/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_version: sourceVersion, target_version: targetVersion })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('生成失败: ' + data.error);
                    return;
                }
                
                showNotification('✅ 脚本已保存到: ' + data.output_dir, 'success');
            } catch (error) {
                alert('生成失败: ' + error.message);
            }
        }
        
        async function previewAutoFix() {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            const sourceVersion = document.getElementById('migration-source').value;
            const targetVersion = document.getElementById('migration-target').value;
            
            try {
                const response = await fetch('/api/migration/auto-fix', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        source_version: sourceVersion, 
                        target_version: targetVersion,
                        dry_run: true
                    })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('预览失败: ' + data.error);
                    return;
                }
                
                renderAutoFixPreview(data);
            } catch (error) {
                alert('预览失败: ' + error.message);
            }
        }
        
        function renderAutoFixPreview(data) {
            const resultEl = document.getElementById('migration-result');
            const fixCount = Object.values(data.fixes).reduce((sum, arr) => sum + arr.length, 0);
            
            let html = '<div class="card">';
            html += '<h3 style="margin-bottom: 20px;">🔧 自动修复预览</h3>';
            html += `<p style="color: var(--text-secondary); margin-bottom: 15px;">共有 <strong style="color: var(--accent-orange);">${fixCount}</strong> 处可自动修复的代码</p>`;
            
            if (fixCount > 0) {
                for (const [filePath, fixes] of Object.entries(data.fixes)) {
                    const fileName = filePath.split('/').pop();
                    html += `
                        <div style="margin-bottom: 15px;">
                            <div style="color: var(--accent-cyan); font-family: var(--font-mono); margin-bottom: 5px;">${fileName}</div>
                            <div style="background: var(--bg-primary); border-radius: 8px; padding: 10px;">
                    `;
                    
                    for (const fix of fixes) {
                        html += `
                            <div style="padding: 5px 0; border-bottom: 1px solid var(--border-color);">
                                <span style="color: var(--text-secondary);">行 ${fix.line}:</span> ${fix.description}
                            </div>
                        `;
                    }
                    
                    html += '</div></div>';
                }
                
                html += `
                    <div style="margin-top: 20px; padding: 15px; background: rgba(243, 156, 18, 0.1); border-radius: 8px; border: 1px solid var(--accent-orange);">
                        <p style="color: var(--accent-orange); margin-bottom: 10px;">⚠️ 警告：自动修复会直接修改源代码文件</p>
                        <p style="color: var(--text-secondary); margin-bottom: 15px;">请确保已备份代码后再执行</p>
                        <button class="btn" style="background: linear-gradient(135deg, #e74c3c, #c0392b); color: white;" onclick="applyAutoFix()">⚡ 确认应用修复</button>
                    </div>
                `;
            } else {
                html += '<div style="text-align: center; padding: 40px;"><span style="font-size: 3rem;">🎉</span><p style="margin-top: 15px; color: var(--accent-green);">没有需要自动修复的代码</p></div>';
            }
            
            html += '</div>';
            resultEl.innerHTML = html;
        }
        
        async function applyAutoFix() {
            if (!confirm('确定要应用自动修复吗？\\n\\n此操作会直接修改源代码文件！\\n请确保已备份代码。')) {
                return;
            }
            
            const sourceVersion = document.getElementById('migration-source').value;
            const targetVersion = document.getElementById('migration-target').value;
            
            try {
                const response = await fetch('/api/migration/auto-fix', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        source_version: sourceVersion, 
                        target_version: targetVersion,
                        dry_run: false
                    })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('修复失败: ' + data.error);
                    return;
                }
                
                showNotification('✅ 自动修复已应用', 'success');
                
                // 重新分析
                analyzeMigration();
            } catch (error) {
                alert('修复失败: ' + error.message);
            }
        }
        
        // ========== 路径管理 ==========
        const STORAGE_KEY = 'odoo_depends_path_history';
        
        function loadPathHistory() {
            try {
                const history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
                const select = document.getElementById('path-history');
                const group = document.getElementById('history-group');
                
                if (history.length > 0) {
                    group.style.display = 'block';
                    select.innerHTML = '<option value="">-- 选择历史路径 --</option>';
                    history.forEach((paths, idx) => {
                        const label = paths.length > 50 ? paths.substring(0, 47) + '...' : paths;
                        const opt = document.createElement('option');
                        opt.value = paths;
                        opt.textContent = '📁 ' + label;
                        select.appendChild(opt);
                    });
                }
            } catch(e) {}
        }
        
        // 加载已上传的分析历史
        async function loadUploadedHistoryList() {
            try {
                const response = await fetch('/api/storage/records');
                const records = await response.json();
                const select = document.getElementById('uploaded-history');
                const group = document.getElementById('uploaded-history-group');
                
                if (records.length > 0) {
                    group.style.display = 'block';
                    select.innerHTML = '<option value="">-- 选择已上传的分析 --</option>';
                    records.forEach(record => {
                        const opt = document.createElement('option');
                        opt.value = record.id;
                        opt.textContent = '📦 ' + record.filename + ' (' + record.modules_count + '个模块)';
                        select.appendChild(opt);
                    });
                }
            } catch(e) {
                console.error('加载上传历史失败:', e);
            }
        }
        
        // 选择已上传的分析
        async function loadUploadedHistory() {
            const select = document.getElementById('uploaded-history');
            const recordId = select.value;
            if (!recordId) return;
            
            document.getElementById('scan-loading').classList.add('active');
            document.getElementById('scan-results').style.display = 'none';
            
            try {
                const response = await fetch('/api/storage/record/' + recordId + '/load', {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.error) {
                    alert('加载失败: ' + data.error);
                    return;
                }
                
                moduleData = {
                    modules: data.modules,
                    statistics: data.statistics
                };
                displayResults(moduleData);
                document.getElementById('scan-results').scrollIntoView({ behavior: 'smooth' });
                showNotification('✅ 已加载历史分析', 'success');
            } catch (error) {
                alert('加载失败: ' + error.message);
            } finally {
                document.getElementById('scan-loading').classList.remove('active');
                select.value = '';  // 重置选择
            }
        }
        
        function savePathHistory(paths) {
            try {
                let history = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
                // 去重
                history = history.filter(h => h !== paths);
                // 添加到开头
                history.unshift(paths);
                // 最多保存10条
                history = history.slice(0, 10);
                localStorage.setItem(STORAGE_KEY, JSON.stringify(history));
                loadPathHistory();
            } catch(e) {}
        }
        
        function loadHistoryPath() {
            const select = document.getElementById('path-history');
            if (select.value) {
                document.getElementById('paths').value = select.value;
            }
        }
        
        function addQuickPath(path) {
            const textarea = document.getElementById('paths');
            const current = textarea.value.trim();
            const paths = current ? current.split('\\n').filter(p => p.trim()) : [];
            
            // 避免重复
            if (!paths.includes(path)) {
                paths.push(path);
            }
            textarea.value = paths.join('\\n');
        }
        
        function clearPaths() {
            document.getElementById('paths').value = '';
        }
        
        // 上传 ZIP 文件
        async function uploadZip(input) {
            if (!input.files || !input.files[0]) return;
            
            const file = input.files[0];
            if (!file.name.endsWith('.zip')) {
                alert('请上传 .zip 格式的文件');
                return;
            }
            
            document.getElementById('scan-loading').classList.add('active');
            document.getElementById('scan-results').style.display = 'none';
            
            try {
                const formData = new FormData();
                formData.append('file', file);
                
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('上传失败: ' + data.error);
                    return;
                }
                
                moduleData = data;
                displayResults(data);
                // 滚动到结果区域
                document.getElementById('scan-results').scrollIntoView({ behavior: 'smooth' });
                // 显示成功提示
                const count = Object.keys(data.modules || {}).length;
                showNotification('✅ 上传成功！扫描到 ' + count + ' 个模块', 'success');
            } catch (error) {
                alert('上传失败: ' + error.message);
            } finally {
                document.getElementById('scan-loading').classList.remove('active');
                input.value = '';  // 清空文件选择
            }
        }
        
        // 加载示例模块数据
        async function loadDemoModules() {
            document.getElementById('scan-loading').classList.add('active');
            document.getElementById('scan-results').style.display = 'none';
            
            // 示例数据 - 模拟 Odoo 模块结构
            const demoData = {
                modules: {
                    'base': {name: 'base', version: '17.0.1.0.0', category: 'Hidden', depends: [], application: false, author: 'Odoo S.A.', summary: 'Odoo Base Module', path: '/demo/base', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'mail': {name: 'mail', version: '17.0.1.0.0', category: 'Communication', depends: ['base'], application: false, author: 'Odoo S.A.', summary: 'Email & Messaging', path: '/demo/mail', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'sale': {name: 'sale', version: '17.0.1.0.0', category: 'Sales', depends: ['base', 'mail', 'product'], application: true, author: 'Odoo S.A.', summary: 'Sales Management', path: '/demo/sale', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'purchase': {name: 'purchase', version: '17.0.1.0.0', category: 'Inventory/Purchase', depends: ['base', 'mail', 'product'], application: true, author: 'Odoo S.A.', summary: 'Purchase Management', path: '/demo/purchase', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'product': {name: 'product', version: '17.0.1.0.0', category: 'Sales/Products', depends: ['base', 'mail'], application: false, author: 'Odoo S.A.', summary: 'Product Catalog', path: '/demo/product', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'stock': {name: 'stock', version: '17.0.1.0.0', category: 'Inventory', depends: ['base', 'mail', 'product'], application: true, author: 'Odoo S.A.', summary: 'Inventory Management', path: '/demo/stock', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'account': {name: 'account', version: '17.0.1.0.0', category: 'Accounting', depends: ['base', 'mail', 'product'], application: true, author: 'Odoo S.A.', summary: 'Invoicing & Accounting', path: '/demo/account', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'crm': {name: 'crm', version: '17.0.1.0.0', category: 'Sales/CRM', depends: ['base', 'mail', 'sale'], application: true, author: 'Odoo S.A.', summary: 'Customer Relationship Management', path: '/demo/crm', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'website': {name: 'website', version: '17.0.1.0.0', category: 'Website', depends: ['base', 'mail'], application: true, author: 'Odoo S.A.', summary: 'Website Builder', path: '/demo/website', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                    'hr': {name: 'hr', version: '17.0.1.0.0', category: 'Human Resources', depends: ['base', 'mail'], application: true, author: 'Odoo S.A.', summary: 'Employees Management', path: '/demo/hr', installable: true, auto_install: false, license: 'LGPL-3', data: [], description: ''},
                },
                statistics: {
                    total_modules: 10,
                    total_dependencies: 22,
                    unique_dependencies: 4,
                    applications: ['sale', 'purchase', 'stock', 'account', 'crm', 'website', 'hr'],
                    categories: ['Hidden', 'Communication', 'Sales', 'Inventory/Purchase', 'Sales/Products', 'Inventory', 'Accounting', 'Sales/CRM', 'Website', 'Human Resources'],
                    circular_dependencies: [],
                    missing_dependencies: {},
                    external_dependencies: [],
                    core_dependencies: ['base', 'mail', 'product'],
                    most_depended_modules: [['base', 9], ['mail', 8], ['product', 4], ['sale', 1]]
                }
            };
            
            moduleData = demoData;
            displayResults(demoData);
            document.getElementById('scan-loading').classList.remove('active');
        }
        
        // 页面加载时加载历史记录
        document.addEventListener('DOMContentLoaded', loadPathHistory);
        
        async function scanModules() {
            const paths = document.getElementById('paths').value.split('\\n').filter(p => p.trim());
            if (paths.length === 0) {
                alert('请输入至少一个模块路径');
                return;
            }
            
            document.getElementById('scan-loading').classList.add('active');
            document.getElementById('scan-results').style.display = 'none';
            
            try {
                const response = await fetch('/api/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ paths })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('扫描失败: ' + data.error);
                    return;
                }
                
                moduleData = data;
                // 保存成功扫描的路径到历史记录
                savePathHistory(document.getElementById('paths').value.trim());
                displayResults(data);
                // 滚动到结果区域并显示通知
                document.getElementById('scan-results').scrollIntoView({ behavior: 'smooth' });
                const count = Object.keys(data.modules || {}).length;
                showNotification('✅ 扫描完成！发现 ' + count + ' 个模块', 'success');
            } catch (error) {
                alert('请求失败: ' + error.message);
            } finally {
                document.getElementById('scan-loading').classList.remove('active');
            }
        }
        
        function displayResults(data) {
            const stats = data.statistics;
            
            // 统计信息
            document.getElementById('stats-grid').innerHTML = `
                <div class="stat-card"><div class="stat-value blue">${stats.total_modules}</div><div class="stat-label">模块总数</div></div>
                <div class="stat-card"><div class="stat-value green">${stats.total_dependencies}</div><div class="stat-label">依赖关系</div></div>
                <div class="stat-card"><div class="stat-value purple">${stats.applications.length}</div><div class="stat-label">应用模块</div></div>
                <div class="stat-card"><div class="stat-value orange">${stats.circular_dependencies.length}</div><div class="stat-label">循环依赖</div></div>
                <div class="stat-card"><div class="stat-value red">${Object.keys(stats.missing_dependencies).length}</div><div class="stat-label">缺失依赖</div></div>
                <div class="stat-card"><div class="stat-value blue">${stats.categories.length}</div><div class="stat-label">分类数量</div></div>
            `;
            
            document.getElementById('scan-results').style.display = 'block';
            
            // 模块列表
            updateModuleList(data.modules);
            
            // 模块选择器
            updateModuleSelector(data.modules);
        }
        
        function updateModuleList(modules) {
            const list = Object.values(modules).sort((a, b) => a.name.localeCompare(b.name));
            let html = '';
            
            for (const mod of list) {
                const badges = mod.application ? '<span class="badge badge-app">应用</span>' : '';
                html += `
                    <div class="module-item" data-name="${mod.name.toLowerCase()}" onclick="showModuleDetail('${mod.name}')">
                        <div>
                            <span class="module-name">${mod.name}</span> ${badges}
                        </div>
                        <div class="module-info">
                            <span>v${mod.version}</span>
                            <span>${mod.depends.length} 依赖</span>
                        </div>
                    </div>
                `;
            }
            document.getElementById('module-list').innerHTML = html;
        }
        
        function updateModuleSelector(modules) {
            const list = Object.values(modules).sort((a, b) => a.name.localeCompare(b.name));
            let html = '<option value="">-- 选择模块 --</option>';
            for (const mod of list) {
                html += `<option value="${mod.name}">${mod.name}</option>`;
            }
            document.getElementById('tree-module').innerHTML = html;
        }
        
        function filterModules() {
            const search = document.getElementById('module-search').value.toLowerCase();
            document.querySelectorAll('.module-item').forEach(item => {
                item.style.display = item.dataset.name.includes(search) ? 'flex' : 'none';
            });
        }
        
        async function renderGraph(excludeExternal) {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            try {
                const response = await fetch(`/api/graph-data?exclude_external=${excludeExternal}`);
                const data = await response.json();
                
                const container = document.getElementById('graph-container');
                const nodes = new vis.DataSet(data.nodes);
                const edges = new vis.DataSet(data.edges);
                
                const options = {
                    nodes: {
                        shape: 'dot',
                        font: { color: '#ffffff', size: 12 },
                        borderWidth: 2,
                        shadow: true
                    },
                    edges: {
                        arrows: { to: { enabled: true, scaleFactor: 0.5 } },
                        color: { color: '#4a4a6a', highlight: '#e74c3c' },
                        smooth: { type: 'curvedCW', roundness: 0.2 }
                    },
                    physics: {
                        barnesHut: {
                            gravitationalConstant: -30000,
                            centralGravity: 0.3,
                            springLength: 150
                        },
                        stabilization: { iterations: 100 }
                    },
                    interaction: { hover: true, tooltipDelay: 200 }
                };
                
                if (network) network.destroy();
                network = new vis.Network(container, { nodes, edges }, options);
                
            } catch (error) {
                alert('生成图表失败: ' + error.message);
            }
        }
        
        async function showTree() {
            const moduleName = document.getElementById('tree-module').value;
            if (!moduleName) return;
            
            try {
                const response = await fetch(`/api/tree/${moduleName}`);
                const data = await response.json();
                document.getElementById('tree-output').textContent = data.tree;
            } catch (error) {
                alert('获取依赖树失败');
            }
        }
        
        async function showOrder() {
            if (!moduleData) return;
            
            try {
                const response = await fetch('/api/order');
                const data = await response.json();
                
                let html = '';
                for (const mod of data.order) {
                    const isCore = data.core_modules.includes(mod);
                    html += `<div class="order-item ${isCore ? 'core' : ''}">
                        <span class="module-name">${mod}</span>
                    </div>`;
                }
                document.getElementById('order-list').innerHTML = html;
            } catch (error) {
                alert('获取安装顺序失败');
            }
        }
        
        function checkIssues() {
            if (!moduleData) {
                document.getElementById('issues-list').innerHTML = `
                    <div class="empty-state">
                        <div class="icon">📂</div>
                        <p>请先扫描模块</p>
                    </div>
                `;
                return;
            }
            
            const stats = moduleData.statistics;
            let html = '';
            
            // 循环依赖
            if (stats.circular_dependencies.length > 0) {
                html += `<div class="issue-item error">
                    <div class="issue-title">🔄 循环依赖 (${stats.circular_dependencies.length})</div>
                    ${stats.circular_dependencies.map(c => `<div style="margin-left:20px;font-family:monospace;">${c.join(' → ')} → ${c[0]}</div>`).join('')}
                </div>`;
            } else {
                html += `<div class="issue-item success">
                    <div class="issue-title">✅ 无循环依赖</div>
                </div>`;
            }
            
            // 缺失依赖
            const missing = stats.missing_dependencies;
            if (Object.keys(missing).length > 0) {
                html += `<div class="issue-item warning">
                    <div class="issue-title">❓ 缺失依赖 (${Object.keys(missing).length} 个模块)</div>
                    ${Object.entries(missing).map(([m, deps]) => 
                        `<div style="margin-left:20px;margin-top:8px;"><strong>${m}:</strong> ${deps.join(', ')}</div>`
                    ).join('')}
                </div>`;
            } else {
                html += `<div class="issue-item success">
                    <div class="issue-title">✅ 无缺失依赖</div>
                </div>`;
            }
            
            document.getElementById('issues-list').innerHTML = html;
        }
        
        function showModuleDetail(name) {
            document.getElementById('tree-module').value = name;
            showPage('tree');
            document.querySelector('[onclick="showPage(\\'tree\\')"]').classList.add('active');
            showTree();
        }
        
        function exportData(format) {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            window.open(`/api/export/${format}`, '_blank');
        }
        
        // ========== 保存到历史 ==========
        async function saveToHistory() {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            const name = prompt('请输入保存名称（可选）:', '分析结果 ' + new Date().toLocaleString());
            if (name === null) return;
            
            try {
                const response = await fetch('/api/storage/save-current', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: name || '未命名分析' })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('保存失败: ' + data.error);
                } else {
                    alert('已保存到历史！ID: ' + data.record_id);
                }
            } catch (error) {
                alert('保存失败: ' + error.message);
            }
        }
        
        // ========== 模型分析 ==========
        async function analyzeModels() {
            if (!moduleData) {
                alert('请先扫描模块');
                return;
            }
            
            try {
                const response = await fetch('/api/models');
                const data = await response.json();
                
                // 显示统计信息
                document.getElementById('model-stats').innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-card"><div class="stat-value blue">${data.statistics.total_models}</div><div class="stat-label">模型总数</div></div>
                        <div class="stat-card"><div class="stat-value green">${data.statistics.total_fields}</div><div class="stat-label">字段总数</div></div>
                        <div class="stat-card"><div class="stat-value purple">${data.statistics.relation_fields}</div><div class="stat-label">关系字段</div></div>
                        <div class="stat-card"><div class="stat-value orange">${data.statistics.computed_fields}</div><div class="stat-label">计算字段</div></div>
                    </div>
                `;
                
                // 填充模块选择框
                const moduleSelect = document.getElementById('model-module-select');
                const modules = [...new Set(Object.values(data.models).map(m => m.module))].sort();
                moduleSelect.innerHTML = '<option value="">全部模块</option>' + 
                    modules.map(m => `<option value="${m}">${m}</option>`).join('');
                
                // 显示模型列表
                renderModelsList(data.models);
                
                // 保存数据供后续使用
                window.modelsData = data.models;
                showNotification('✅ 模型分析完成', 'success');
            } catch (error) {
                alert('分析模型失败: ' + error.message);
            }
        }
        
        function renderModelsList(models, moduleFilter = '', searchFilter = '') {
            let html = '';
            const modelEntries = Object.entries(models).sort((a, b) => a[0].localeCompare(b[0]));
            
            for (const [name, model] of modelEntries) {
                // 应用过滤
                if (moduleFilter && model.module !== moduleFilter) continue;
                if (searchFilter && !name.toLowerCase().includes(searchFilter)) continue;
                
                const fieldCount = Object.keys(model.fields || {}).length;
                html += `
                    <div class="module-item" data-name="${name.toLowerCase()}" data-module="${model.module}" onclick="showModelDetail('${name}')">
                        <div>
                            <span class="module-name">${name}</span>
                            <span style="color: var(--text-secondary); margin-left: 10px;">📦 ${model.module}</span>
                        </div>
                        <div class="module-info">
                            <span>${fieldCount} 字段</span>
                            <span>${model.methods?.length || 0} 方法</span>
                        </div>
                    </div>
                `;
            }
            document.getElementById('models-list').innerHTML = html || '<div style="text-align:center;padding:40px;color:var(--text-secondary);">📭 未找到匹配的模型</div>';
        }
        
        function filterModelsByModule() {
            if (!window.modelsData) return;
            const moduleFilter = document.getElementById('model-module-select').value;
            const searchFilter = document.getElementById('model-search').value.toLowerCase();
            renderModelsList(window.modelsData, moduleFilter, searchFilter);
        }
        
        function filterModelsTable() {
            if (!window.modelsData) return;
            const moduleFilter = document.getElementById('model-module-select').value;
            const search = document.getElementById('model-search').value.toLowerCase();
            renderModelsList(window.modelsData, moduleFilter, search);
        }
        
        function showModelDetail(modelName) {
            if (!window.modelsData || !window.modelsData[modelName]) return;
            const model = window.modelsData[modelName];
            
            let fieldsHtml = '';
            for (const [fname, field] of Object.entries(model.fields || {})) {
                const typeColor = field.field_type.includes('2') ? 'var(--accent-purple)' : 'var(--accent-blue)';
                fieldsHtml += `<div style="padding:8px;background:var(--bg-primary);border-radius:6px;margin:4px 0;">
                    <span style="color:var(--accent-green);font-weight:600;">${fname}</span>
                    <span style="color:${typeColor};margin-left:10px;">${field.field_type}</span>
                    ${field.comodel_name ? `<span style="color:var(--text-secondary);"> → ${field.comodel_name}</span>` : ''}
                </div>`;
            }
            
            alert('模型: ' + modelName + '\\n模块: ' + model.module + '\\n字段数: ' + Object.keys(model.fields || {}).length + '\\n方法数: ' + (model.methods?.length || 0));
        }
        
        // ========== 升级影响评估 ==========
        async function assessImpact() {
            const moduleName = document.getElementById('impact-module').value;
            if (!moduleName) {
                document.getElementById('impact-result').innerHTML = '';
                return;
            }
            
            try {
                const response = await fetch(`/api/impact/${moduleName}`);
                const data = await response.json();
                
                const riskColors = {
                    'low': 'var(--accent-green)',
                    'medium': 'var(--accent-orange)',
                    'high': 'var(--accent-red)',
                    'critical': '#ff0000'
                };
                const riskLabels = {
                    'low': '低风险',
                    'medium': '中等风险',
                    'high': '高风险',
                    'critical': '极高风险'
                };
                
                document.getElementById('impact-result').innerHTML = `
                    <div class="card" style="margin-top: 20px;">
                        <h3 style="color: ${riskColors[data.risk_level]}; font-size: 1.5rem; margin-bottom: 20px;">
                            ⚡ ${riskLabels[data.risk_level]}
                        </h3>
                        
                        <div class="stats-grid" style="margin-bottom: 20px;">
                            <div class="stat-card"><div class="stat-value blue">${data.direct_dependents.length}</div><div class="stat-label">直接依赖</div></div>
                            <div class="stat-card"><div class="stat-value purple">${data.all_dependents.length}</div><div class="stat-label">全部依赖</div></div>
                            <div class="stat-card"><div class="stat-value green">${data.affected_models.length}</div><div class="stat-label">受影响模型</div></div>
                            <div class="stat-card"><div class="stat-value orange">${data.impact_score}</div><div class="stat-label">影响分数</div></div>
                        </div>
                        
                        ${data.risk_factors.length ? `
                        <div style="margin-bottom: 15px;">
                            <strong>风险因素:</strong>
                            <ul style="margin-top: 8px; padding-left: 20px;">
                                ${data.risk_factors.map(f => `<li style="margin: 5px 0;">${f}</li>`).join('')}
                            </ul>
                        </div>
                        ` : ''}
                        
                        <div style="margin-bottom: 15px;">
                            <strong>建议:</strong>
                            <ul style="margin-top: 8px; padding-left: 20px;">
                                ${data.recommendations.map(r => `<li style="margin: 5px 0;">${r}</li>`).join('')}
                            </ul>
                        </div>
                        
                        ${data.direct_dependents.length ? `
                        <div style="margin-bottom: 15px;">
                            <strong>直接依赖此模块的模块:</strong>
                            <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px;">
                                ${data.direct_dependents.map(d => `<span class="badge badge-core">${d}</span>`).join('')}
                            </div>
                        </div>
                        ` : ''}
                        
                        ${data.affected_models.length ? `
                        <div>
                            <strong>涉及的模型:</strong>
                            <div style="margin-top: 8px; display: flex; flex-wrap: wrap; gap: 8px;">
                                ${data.affected_models.slice(0, 20).map(m => `<span class="badge badge-app">${m}</span>`).join('')}
                                ${data.affected_models.length > 20 ? `<span class="badge">+${data.affected_models.length - 20} 更多</span>` : ''}
                            </div>
                        </div>
                        ` : ''}
                    </div>
                `;
            } catch (error) {
                alert('评估失败: ' + error.message);
            }
        }
        
        // ========== 版本对比 ==========
        async function compareVersions() {
            const sourcePaths = document.getElementById('source-paths').value.split('\\n').filter(p => p.trim());
            const targetPaths = document.getElementById('target-paths').value.split('\\n').filter(p => p.trim());
            
            if (!sourcePaths.length || !targetPaths.length) {
                alert('请输入源版本和目标版本的路径');
                return;
            }
            
            try {
                const response = await fetch('/api/compare', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ source_paths: sourcePaths, target_paths: targetPaths })
                });
                
                const data = await response.json();
                if (data.error) {
                    alert('对比失败: ' + data.error);
                    return;
                }
                
                document.getElementById('compare-result').innerHTML = `
                    <div class="stats-grid" style="margin-bottom: 20px;">
                        <div class="stat-card"><div class="stat-value green">${data.summary.added}</div><div class="stat-label">新增模块</div></div>
                        <div class="stat-card"><div class="stat-value red">${data.summary.removed}</div><div class="stat-label">删除模块</div></div>
                        <div class="stat-card"><div class="stat-value orange">${data.summary.modified}</div><div class="stat-label">修改模块</div></div>
                        <div class="stat-card"><div class="stat-value blue">${data.dependency_changes.length}</div><div class="stat-label">依赖变更</div></div>
                    </div>
                    
                    ${data.added_modules.length ? `
                    <div class="card">
                        <h3 style="color: var(--accent-green);">✅ 新增模块 (${data.added_modules.length})</h3>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
                            ${data.added_modules.slice(0, 50).map(m => `<span class="badge" style="background:rgba(46,204,113,0.2);color:var(--accent-green);">${m}</span>`).join('')}
                            ${data.added_modules.length > 50 ? `<span class="badge">+${data.added_modules.length - 50} 更多</span>` : ''}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${data.removed_modules.length ? `
                    <div class="card">
                        <h3 style="color: var(--accent-red);">❌ 删除模块 (${data.removed_modules.length})</h3>
                        <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
                            ${data.removed_modules.slice(0, 50).map(m => `<span class="badge" style="background:rgba(231,76,60,0.2);color:var(--accent-red);">${m}</span>`).join('')}
                            ${data.removed_modules.length > 50 ? `<span class="badge">+${data.removed_modules.length - 50} 更多</span>` : ''}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${data.modified_modules.length ? `
                    <div class="card">
                        <h3 style="color: var(--accent-orange);">🔄 修改模块 (${data.modified_modules.length})</h3>
                        <div style="margin-top: 10px;">
                            ${data.modified_modules.slice(0, 20).map(m => `
                                <div style="padding: 10px; background: var(--bg-primary); border-radius: 8px; margin: 5px 0;">
                                    <strong style="color: var(--accent-green);">${m.name}</strong>
                                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 5px;">
                                        ${m.changes.join(' | ')}
                                    </div>
                                </div>
                            `).join('')}
                            ${data.modified_modules.length > 20 ? `<p style="color: var(--text-secondary);">...还有 ${data.modified_modules.length - 20} 个模块</p>` : ''}
                        </div>
                    </div>
                    ` : ''}
                    
                    ${data.dependency_changes.length ? `
                    <div class="card">
                        <h3 style="color: var(--accent-blue);">🔗 依赖变更 (${data.dependency_changes.length})</h3>
                        <div style="margin-top: 10px;">
                            ${data.dependency_changes.slice(0, 15).map(c => `
                                <div style="padding: 10px; background: var(--bg-primary); border-radius: 8px; margin: 5px 0;">
                                    <strong style="color: var(--accent-green);">${c.module}</strong>
                                    ${c.added_dependencies.length ? `<div style="color: var(--accent-green); font-size: 0.85rem;">+ ${c.added_dependencies.join(', ')}</div>` : ''}
                                    ${c.removed_dependencies.length ? `<div style="color: var(--accent-red); font-size: 0.85rem;">- ${c.removed_dependencies.join(', ')}</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    ` : ''}
                `;
            } catch (error) {
                alert('请求失败: ' + error.message);
            }
        }
        
        // 更新显示逻辑
        const originalShowPage = showPage;
        showPage = function(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            
            document.getElementById('page-' + pageId).classList.add('active');
            if (event && event.currentTarget) {
                event.currentTarget.classList.add('active');
            }
            
            if (pageId === 'graph' && moduleData) {
                setTimeout(() => renderGraph(false), 100);
            }
            if (pageId === 'issues' && moduleData) {
                checkIssues();
            }
            if (pageId === 'order' && moduleData) {
                showOrder();
            }
            if (pageId === 'impact' && moduleData) {
                // 更新模块选择器
                const select = document.getElementById('impact-module');
                if (select.options.length <= 1) {
                    const modules = Object.keys(moduleData.modules).sort();
                    for (const mod of modules) {
                        const opt = document.createElement('option');
                        opt.value = mod;
                        opt.textContent = mod;
                        select.appendChild(opt);
                    }
                }
            }
        }
        
        // ========== 文件夹浏览器 ==========
        let currentBrowsePath = '';
        
        async function openFolderBrowser() {
            // 先检测是否是本地环境
            try {
                const response = await fetch('/api/browse?path=~');
                const data = await response.json();
                
                if (data.error) {
                    // 可能是 Vercel 环境，无法访问本地文件
                    alert('⚠️ 云端部署版本无法浏览本地文件夹\\n\\n请使用以下方式：\\n1. 点击「上传 ZIP」上传模块压缩包\\n2. 或使用本地部署版本（python run.py）');
                    return;
                }
                
                document.getElementById('folder-modal').style.display = 'flex';
                document.getElementById('current-path').textContent = data.path;
                document.getElementById('current-path-input').value = data.path;
                currentBrowsePath = data.path;
                await renderFolderList(data);
            } catch (error) {
                alert('无法连接服务器：' + error.message);
            }
        }
        
        function closeFolderBrowser() {
            document.getElementById('folder-modal').style.display = 'none';
        }
        
        async function browseTo(path) {
            const listEl = document.getElementById('folder-list');
            listEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-secondary);">加载中...</div>';
            
            try {
                const response = await fetch('/api/browse?path=' + encodeURIComponent(path));
                const data = await response.json();
                
                if (data.error) {
                    listEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--accent-red);">❌ ' + data.error + '</div>';
                    return;
                }
                
                currentBrowsePath = data.path;
                document.getElementById('current-path').textContent = data.path;
                document.getElementById('current-path-input').value = data.path;
                await renderFolderList(data);
            } catch (error) {
                listEl.innerHTML = '<div style="text-align:center;padding:40px;color:var(--accent-red);">❌ 请求失败: ' + error.message + '</div>';
            }
        }
        
        function renderFolderList(data) {
            const listEl = document.getElementById('folder-list');
            let html = '';
            
            // 返回上级目录
            if (data.parent) {
                html += '<div class="folder-item" onclick="browseTo(\\'' + data.parent.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'") + '\\')"><span class="folder-icon">⬆️</span><span class="folder-name">..</span><span class="folder-type">返回上级</span></div>';
            }
            
            // 目录和模块
            for (const item of data.items || []) {
                if (item.is_dir) {
                    const escapedPath = item.path.replace(/\\\\/g, '\\\\\\\\').replace(/'/g, "\\\\'");
                    const icon = item.is_odoo_module ? '📦' : '📁';
                    const typeLabel = item.is_odoo_module ? '<span style="color:var(--accent-green);">Odoo模块</span>' : '文件夹';
                    html += '<div class="folder-item' + (item.is_odoo_module ? ' odoo-module' : '') + '" onclick="browseTo(\\'' + escapedPath + '\\')" ondblclick="selectAndClose(\\'' + escapedPath + '\\')"><span class="folder-icon">' + icon + '</span><span class="folder-name">' + item.name + '</span><span class="folder-type">' + typeLabel + '</span>' + (item.is_odoo_module ? '<button class="btn btn-sm" onclick="event.stopPropagation();selectFolder(\\'' + escapedPath + '\\')">选择</button>' : '') + '</div>';
                }
            }
            
            if (!html) {
                html = '<div style="text-align:center;padding:40px;color:var(--text-secondary);">📭 此目录为空</div>';
            }
            
            listEl.innerHTML = html;
        }
        
        function selectFolder(path) {
            addQuickPath(path);
            closeFolderBrowser();
        }
        
        function selectAndClose(path) {
            selectFolder(path);
        }
        
        function selectCurrentFolder() {
            if (currentBrowsePath) {
                addQuickPath(currentBrowsePath);
                closeFolderBrowser();
            }
        }
        
        function goToPath() {
            const path = document.getElementById('current-path-input').value;
            if (path) {
                browseTo(path);
            }
        }
        
        // 点击模态框背景关闭
        document.addEventListener('click', function(e) {
            if (e.target.id === 'folder-modal') {
                closeFolderBrowser();
            }
        });
        
        // 页面加载时初始化
        document.addEventListener('DOMContentLoaded', function() {
            loadPathHistory();
            loadUploadedHistoryList();
        });
    </script>
    
    <!-- 文件夹浏览器模态框 -->
    <div id="folder-modal" style="display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.8);z-index:1000;align-items:center;justify-content:center;">
        <div style="background:var(--bg-secondary);border-radius:16px;width:90%;max-width:800px;max-height:80vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,0.5);">
            <div style="padding:20px;border-bottom:1px solid var(--border-color);display:flex;align-items:center;justify-content:space-between;">
                <h2 style="margin:0;font-size:1.2rem;">📂 选择文件夹</h2>
                <button onclick="closeFolderBrowser()" style="background:none;border:none;color:var(--text-secondary);font-size:1.5rem;cursor:pointer;">&times;</button>
            </div>
            <div style="padding:15px;border-bottom:1px solid var(--border-color);display:flex;gap:10px;">
                <input type="text" id="current-path-input" style="flex:1;padding:10px 15px;background:var(--bg-primary);border:1px solid var(--border-color);border-radius:8px;color:var(--text-primary);font-family:var(--font-mono);" placeholder="输入路径...">
                <button class="btn btn-secondary" onclick="goToPath()">前往</button>
            </div>
            <div style="padding:10px 15px;background:var(--bg-primary);border-bottom:1px solid var(--border-color);">
                <span style="color:var(--text-secondary);font-size:0.85rem;">当前位置: </span>
                <span id="current-path" style="color:var(--accent-cyan);font-family:var(--font-mono);font-size:0.85rem;"></span>
            </div>
            <div id="folder-list" style="flex:1;overflow-y:auto;padding:10px;">
                <!-- 文件夹列表 -->
            </div>
            <div style="padding:15px;border-top:1px solid var(--border-color);display:flex;justify-content:space-between;align-items:center;">
                <span style="color:var(--text-secondary);font-size:0.85rem;">💡 双击 Odoo 模块可快速选择</span>
                <div style="display:flex;gap:10px;">
                    <button class="btn btn-secondary" onclick="closeFolderBrowser()">取消</button>
                    <button class="btn btn-primary" onclick="selectCurrentFolder()">选择当前目录</button>
                </div>
            </div>
        </div>
    </div>
    
    <style>
        .folder-item {
            display: flex;
            align-items: center;
            padding: 12px 15px;
            margin: 4px 0;
            background: var(--bg-primary);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .folder-item:hover {
            background: var(--bg-tertiary);
            transform: translateX(5px);
        }
        .folder-item.odoo-module {
            border-left: 3px solid var(--accent-green);
        }
        .folder-icon {
            font-size: 1.3rem;
            margin-right: 12px;
        }
        .folder-name {
            flex: 1;
            font-weight: 500;
        }
        .folder-type {
            color: var(--text-secondary);
            font-size: 0.85rem;
            margin-right: 10px;
        }
        .btn-sm {
            padding: 5px 12px !important;
            font-size: 0.8rem !important;
        }
    </style>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/scan', methods=['POST'])
def scan():
    global analyzer, visualizer
    
    data = request.get_json()
    paths = data.get('paths', [])
    
    if not paths:
        return jsonify({'error': '请提供至少一个路径'})
    
    try:
        analyzer = OdooModuleAnalyzer(paths)
        analyzer.scan_modules()
        analyzer.build_dependency_graph()
        visualizer = DependencyVisualizer(analyzer)
        
        return jsonify({
            'modules': {name: mod.to_dict() for name, mod in analyzer.modules.items()},
            'statistics': analyzer.get_statistics()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/upload', methods=['POST'])
def upload_modules():
    """上传并分析 Odoo 模块 zip 文件"""
    global analyzer, visualizer
    import zipfile
    import shutil
    
    if 'file' not in request.files:
        return jsonify({'error': '请上传文件'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未选择文件'})
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': '请上传 zip 格式文件'})
    
    try:
        # 创建临时目录
        upload_dir = tempfile.mkdtemp(prefix='odoo_upload_')
        zip_path = os.path.join(upload_dir, 'modules.zip')
        extract_dir = os.path.join(upload_dir, 'modules')
        
        # 保存并解压
        file.save(zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 分析模块
        analyzer = OdooModuleAnalyzer([extract_dir])
        analyzer.scan_modules()
        analyzer.build_dependency_graph()
        visualizer = DependencyVisualizer(analyzer)
        
        result = {
            'modules': {name: mod.to_dict() for name, mod in analyzer.modules.items()},
            'statistics': analyzer.get_statistics()
        }
        
        # 清理临时文件
        shutil.rmtree(upload_dir, ignore_errors=True)
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/graph-data')
def graph_data():
    global analyzer
    
    if not analyzer:
        return jsonify({'error': '请先扫描模块'})
    
    exclude_external = request.args.get('exclude_external', 'false').lower() == 'true'
    
    nodes = []
    edges = []
    
    COLORS = {
        'application': '#e74c3c',
        'core': '#3498db',
        'external': '#95a5a6',
        'normal': '#2ecc71',
    }
    
    for node in analyzer.graph.nodes():
        attrs = dict(analyzer.graph.nodes[node])
        
        if exclude_external and attrs.get('is_external'):
            continue
        
        # 确定颜色
        if attrs.get('is_external'):
            color = COLORS['external']
        elif attrs.get('is_core'):
            color = COLORS['core']
        elif attrs.get('application'):
            color = COLORS['application']
        else:
            color = COLORS['normal']
        
        # 节点大小
        in_degree = analyzer.graph.in_degree(node)
        size = max(15, min(50, 15 + in_degree * 3))
        
        nodes.append({
            'id': node,
            'label': node,
            'color': color,
            'size': size,
            'title': f"{node}\\n依赖数: {len(list(analyzer.graph.successors(node)))}\\n被依赖: {in_degree}"
        })
    
    node_ids = {n['id'] for n in nodes}
    
    for source, target in analyzer.graph.edges():
        if source in node_ids and target in node_ids:
            edges.append({'from': source, 'to': target})
    
    return jsonify({'nodes': nodes, 'edges': edges})


@app.route('/api/tree/<module_name>')
def tree(module_name):
    global visualizer
    
    if not visualizer:
        return jsonify({'error': '请先扫描模块'})
    
    tree_text = visualizer.generate_module_tree(module_name)
    return jsonify({'tree': tree_text})


@app.route('/api/order')
def order():
    global analyzer
    
    if not analyzer:
        return jsonify({'error': '请先扫描模块'})
    
    install_order = analyzer.get_install_order()
    core_modules = list(analyzer.CORE_MODULES)
    
    return jsonify({'order': install_order, 'core_modules': core_modules})


@app.route('/api/export/<format>')
def export(format):
    global analyzer, visualizer
    
    if not analyzer:
        return "请先扫描模块", 400
    
    if format == 'json':
        output = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        analyzer.export_to_json(output.name)
        return send_file(output.name, as_attachment=True, download_name='odoo_modules.json')
    
    elif format == 'html':
        output = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
        visualizer.generate_interactive_html(output.name)
        return send_file(output.name, as_attachment=True, download_name='odoo_dependency_graph.html')
    
    return "不支持的格式", 400


@app.route('/api/models')
def models():
    """获取模型分析结果"""
    global analyzer, upgrade_analyzer
    
    if not analyzer:
        return jsonify({'error': '请先扫描模块'})
    
    try:
        models = upgrade_analyzer.analyze_models(analyzer)
        stats = upgrade_analyzer.get_model_statistics()
        
        return jsonify({
            'models': {name: model.to_dict() for name, model in models.items()},
            'statistics': stats,
            'relationships': upgrade_analyzer.get_model_relationships()
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/impact/<module_name>')
def impact(module_name):
    """获取模块升级影响评估"""
    global analyzer, upgrade_analyzer
    
    if not analyzer:
        return jsonify({'error': '请先扫描模块'})
    
    try:
        impact = upgrade_analyzer.assess_upgrade_impact(module_name, analyzer)
        return jsonify(impact.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/compare', methods=['POST'])
def compare():
    """对比两个版本"""
    global upgrade_analyzer
    
    data = request.get_json()
    source_paths = data.get('source_paths', [])
    target_paths = data.get('target_paths', [])
    
    if not source_paths or not target_paths:
        return jsonify({'error': '请提供源版本和目标版本路径'})
    
    try:
        upgrade_analyzer.load_source(source_paths)
        upgrade_analyzer.load_target(target_paths)
        diff = upgrade_analyzer.compare_versions()
        
        return jsonify(diff.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)})


# ==================== 迁移辅助 API ====================

@app.route('/api/migration/analyze', methods=['POST'])
def migration_analyze():
    """分析代码并生成升级报告"""
    global analyzer
    
    data = request.get_json() or {}
    source_version = data.get('source_version', '16.0')
    target_version = data.get('target_version', '17.0')
    
    if not analyzer or not analyzer.modules:
        return jsonify({'error': '请先扫描模块'})
    
    try:
        # 获取模块路径
        module_paths = list(set(
            str(Path(mod.path).parent) 
            for mod in analyzer.modules.values()
        ))
        
        helper = MigrationHelper(module_paths, source_version, target_version)
        report = helper.generate_report()
        
        return jsonify(report)
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/migration/scripts/<module_name>')
def migration_scripts(module_name):
    """生成迁移脚本模板"""
    global analyzer
    
    source_version = request.args.get('source_version', '16.0')
    target_version = request.args.get('target_version', '17.0')
    
    if not analyzer or not analyzer.modules:
        return jsonify({'error': '请先扫描模块'})
    
    if module_name not in analyzer.modules:
        return jsonify({'error': f'模块 {module_name} 不存在'})
    
    try:
        module_path = Path(analyzer.modules[module_name].path).parent
        helper = MigrationHelper([str(module_path)], source_version, target_version)
        helper.scan_modules()
        
        scripts = helper.generate_migration_scripts(module_name)
        if scripts:
            return jsonify(scripts.to_dict())
        return jsonify({'error': '生成脚本失败'})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/migration/scripts/<module_name>/save', methods=['POST'])
def migration_scripts_save(module_name):
    """保存迁移脚本到模块目录"""
    global analyzer
    
    data = request.get_json() or {}
    source_version = data.get('source_version', '16.0')
    target_version = data.get('target_version', '17.0')
    
    if not analyzer or not analyzer.modules:
        return jsonify({'error': '请先扫描模块'})
    
    if module_name not in analyzer.modules:
        return jsonify({'error': f'模块 {module_name} 不存在'})
    
    try:
        module_path = Path(analyzer.modules[module_name].path).parent
        helper = MigrationHelper([str(module_path)], source_version, target_version)
        helper.scan_modules()
        
        output_dir = helper.save_migration_scripts(module_name)
        if output_dir:
            return jsonify({
                'success': True,
                'output_dir': output_dir,
                'message': f'迁移脚本已保存到 {output_dir}'
            })
        return jsonify({'error': '保存失败'})
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/migration/auto-fix', methods=['POST'])
def migration_auto_fix():
    """应用自动修复"""
    global analyzer
    
    data = request.get_json() or {}
    source_version = data.get('source_version', '16.0')
    target_version = data.get('target_version', '17.0')
    dry_run = data.get('dry_run', True)
    
    if not analyzer or not analyzer.modules:
        return jsonify({'error': '请先扫描模块'})
    
    try:
        module_paths = list(set(
            str(Path(mod.path).parent) 
            for mod in analyzer.modules.values()
        ))
        
        helper = MigrationHelper(module_paths, source_version, target_version)
        helper.scan_modules()
        helper.analyze_code()
        
        fixes = helper.apply_auto_fixes(dry_run=dry_run)
        
        return jsonify({
            'dry_run': dry_run,
            'fixes': fixes,
            'message': '模拟运行完成' if dry_run else '自动修复已应用'
        })
    except Exception as e:
        return jsonify({'error': str(e)})


@app.route('/api/browse')
def browse_directory():
    """浏览本地目录"""
    import os
    
    path = request.args.get('path', os.path.expanduser('~'))
    
    try:
        # 规范化路径
        path = os.path.abspath(os.path.expanduser(path))
        
        if not os.path.exists(path):
            return jsonify({'error': '路径不存在', 'path': path})
        
        if not os.path.isdir(path):
            return jsonify({'error': '不是目录', 'path': path})
        
        # 获取目录内容
        items = []
        try:
            for name in sorted(os.listdir(path)):
                if name.startswith('.'):
                    continue  # 跳过隐藏文件
                full_path = os.path.join(path, name)
                try:
                    is_dir = os.path.isdir(full_path)
                    # 检查是否是 Odoo 模块
                    is_odoo_module = is_dir and (
                        os.path.exists(os.path.join(full_path, '__manifest__.py')) or
                        os.path.exists(os.path.join(full_path, '__openerp__.py'))
                    )
                    items.append({
                        'name': name,
                        'path': full_path,
                        'is_dir': is_dir,
                        'is_odoo_module': is_odoo_module,
                    })
                except PermissionError:
                    continue
        except PermissionError:
            return jsonify({'error': '无权限访问此目录', 'path': path})
        
        # 获取父目录
        parent = os.path.dirname(path)
        
        return jsonify({
            'path': path,
            'parent': parent if parent != path else None,
            'items': items,
        })
    except Exception as e:
        return jsonify({'error': str(e), 'path': path})


@app.route('/api/quick-paths')
def get_quick_paths():
    """获取常用快捷路径"""
    import os
    
    home = os.path.expanduser('~')
    paths = [
        {'name': '🏠 主目录', 'path': home},
        {'name': '💻 桌面', 'path': os.path.join(home, 'Desktop')},
        {'name': '📁 文档', 'path': os.path.join(home, 'Documents')},
        {'name': '🐳 Docker Odoo', 'path': '/opt/odoo'},
        {'name': '📦 项目测试模块', 'path': os.path.join(os.getcwd(), 'odoo-test', 'addons')},
    ]
    
    # 只返回存在的路径
    return jsonify([p for p in paths if os.path.exists(p['path'])])


# ==================== 云存储 API ====================

@app.route('/api/storage/upload', methods=['POST'])
def storage_upload():
    """上传 ZIP 文件并保存到云存储，同时进行分析"""
    global analyzer, visualizer
    import zipfile
    import shutil
    
    if 'file' not in request.files:
        return jsonify({'error': '请上传文件'})
    
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': '请选择文件'})
    
    if not file.filename.endswith('.zip'):
        return jsonify({'error': '请上传 ZIP 文件'})
    
    try:
        # 读取文件内容
        file_data = file.read()
        file_size = len(file_data)
        
        # 上传到云存储
        record_id = generate_record_id()
        file_url = storage.upload_file(f"modules/{record_id}_{file.filename}", file_data)
        
        # 解压并分析
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, 'modules.zip')
        
        with open(zip_path, 'wb') as f:
            f.write(file_data)
        
        extract_dir = os.path.join(temp_dir, 'extracted')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # 分析模块
        analyzer = OdooModuleAnalyzer([extract_dir])
        analyzer.scan_modules()
        analyzer.build_dependency_graph()
        visualizer = DependencyVisualizer(analyzer)
        
        # 创建分析结果
        analysis_result = {
            'modules': {name: mod.to_dict() for name, mod in analyzer.modules.items()},
            'statistics': analyzer.get_statistics()
        }
        
        # 保存记录
        record = AnalysisRecord(
            id=record_id,
            filename=file.filename,
            upload_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            file_url=file_url,
            file_size=file_size,
            modules_count=len(analyzer.modules),
            analysis_result=analysis_result
        )
        storage.save_record(record)
        
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        return jsonify({
            'success': True,
            'record_id': record_id,
            'modules': analysis_result['modules'],
            'statistics': analysis_result['statistics'],
            'message': f'已保存到云端，ID: {record_id}'
        })
        
    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'})


@app.route('/api/storage/records')
def storage_records():
    """获取所有分析记录"""
    records = storage.get_records()
    return jsonify([r.to_dict() for r in records])


@app.route('/api/storage/record/<record_id>')
def storage_record(record_id):
    """获取单个分析记录"""
    record = storage.get_record(record_id)
    if record:
        return jsonify(record.to_dict())
    return jsonify({'error': '记录不存在'}), 404


@app.route('/api/storage/record/<record_id>/load', methods=['POST'])
def storage_load_record(record_id):
    """加载历史分析记录到当前分析器"""
    global analyzer, visualizer
    
    record = storage.get_record(record_id)
    if not record:
        return jsonify({'error': '记录不存在'}), 404
    
    # 如果需要重新分析（有 ZIP 文件）
    if record.file_url and request.args.get('reanalyze'):
        try:
            import zipfile
            import shutil
            
            # 下载 ZIP 文件
            file_data = storage.download_file(record.file_url)
            
            # 解压并分析
            temp_dir = tempfile.mkdtemp()
            zip_path = os.path.join(temp_dir, 'modules.zip')
            
            with open(zip_path, 'wb') as f:
                f.write(file_data)
            
            extract_dir = os.path.join(temp_dir, 'extracted')
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # 重新分析
            analyzer = OdooModuleAnalyzer([extract_dir])
            analyzer.scan_modules()
            analyzer.build_dependency_graph()
            visualizer = DependencyVisualizer(analyzer)
            
            # 更新记录
            record.analysis_result = {
                'modules': {name: mod.to_dict() for name, mod in analyzer.modules.items()},
                'statistics': analyzer.get_statistics()
            }
            record.modules_count = len(analyzer.modules)
            storage.save_record(record)
            
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return jsonify({
                'success': True,
                'modules': record.analysis_result['modules'],
                'statistics': record.analysis_result['statistics']
            })
            
        except Exception as e:
            return jsonify({'error': f'重新分析失败: {str(e)}'})
    
    # 直接使用保存的分析结果
    return jsonify({
        'success': True,
        'modules': record.analysis_result.get('modules', {}),
        'statistics': record.analysis_result.get('statistics', {})
    })


@app.route('/api/storage/record/<record_id>', methods=['DELETE'])
def storage_delete_record(record_id):
    """删除分析记录"""
    if storage.delete_record(record_id):
        return jsonify({'success': True})
    return jsonify({'error': '删除失败'}), 400


@app.route('/api/storage/info')
def storage_info():
    """获取存储信息"""
    if isinstance(storage, LocalStorage):
        info = storage.get_storage_info()
        info['type'] = 'local'
    else:
        info = {
            'type': 'vercel_blob',
            'available': storage.is_available
        }
    return jsonify(info)


@app.route('/api/storage/save-current', methods=['POST'])
def storage_save_current():
    """保存当前分析结果到历史"""
    global analyzer
    
    if not analyzer or not analyzer.modules:
        return jsonify({'error': '没有可保存的分析结果，请先扫描模块'})
    
    data = request.get_json() or {}
    name = data.get('name', '未命名分析')
    
    try:
        record_id = generate_record_id()
        
        # 创建分析结果
        analysis_result = {
            'modules': {name: mod.to_dict() for name, mod in analyzer.modules.items()},
            'statistics': analyzer.get_statistics()
        }
        
        # 保存记录（不保存 ZIP，只保存分析结果）
        record = AnalysisRecord(
            id=record_id,
            filename=name,
            upload_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            file_url=None,  # 没有 ZIP 文件
            file_size=0,
            modules_count=len(analyzer.modules),
            analysis_result=analysis_result
        )
        storage.save_record(record)
        
        return jsonify({
            'success': True,
            'record_id': record_id,
            'message': f'已保存，ID: {record_id}'
        })
        
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'})


@app.route('/api/storage/clear', methods=['POST'])
def storage_clear():
    """清空存储（仅本地存储支持）"""
    if isinstance(storage, LocalStorage):
        if storage.clear_storage():
            return jsonify({'success': True})
    return jsonify({'error': '清空失败'}), 400


@app.route('/history')
def history_page():
    """分析历史页面"""
    return render_template_string(HISTORY_TEMPLATE)


HISTORY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>分析历史 - Odoo 模块依赖分析器</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0f0f1a;
            --bg-secondary: #1a1a2e;
            --bg-card: rgba(26, 26, 46, 0.9);
            --accent-cyan: #00d4ff;
            --accent-green: #2ecc71;
            --accent-red: #e74c3c;
            --accent-orange: #f39c12;
            --text-primary: #ffffff;
            --text-secondary: rgba(255, 255, 255, 0.7);
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Noto Sans SC', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
        }
        
        h1 {
            font-size: 1.8rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-green));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .btn {
            padding: 0.6rem 1.2rem;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-cyan), #0099cc);
            color: white;
        }
        
        .btn-primary:hover { transform: translateY(-2px); }
        
        .btn-danger {
            background: var(--accent-red);
            color: white;
        }
        
        .btn-secondary {
            background: var(--bg-secondary);
            color: var(--text-primary);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .storage-info {
            background: var(--bg-card);
            padding: 1rem 1.5rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .storage-info span {
            color: var(--text-secondary);
        }
        
        .storage-info strong {
            color: var(--accent-cyan);
        }
        
        .records-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }
        
        .record-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255,255,255,0.05);
            transition: all 0.3s;
        }
        
        .record-card:hover {
            transform: translateY(-3px);
            border-color: var(--accent-cyan);
        }
        
        .record-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        
        .record-title {
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--accent-cyan);
            word-break: break-all;
        }
        
        .record-id {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            background: rgba(255,255,255,0.1);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }
        
        .record-meta {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0.5rem;
            margin-bottom: 1rem;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }
        
        .record-meta span {
            display: flex;
            align-items: center;
            gap: 0.3rem;
        }
        
        .record-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .record-actions .btn {
            flex: 1;
            padding: 0.5rem;
            font-size: 0.85rem;
        }
        
        .empty-state {
            text-align: center;
            padding: 4rem 2rem;
            color: var(--text-secondary);
        }
        
        .empty-state h2 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
        }
        
        .upload-zone {
            border: 2px dashed rgba(255,255,255,0.2);
            border-radius: 12px;
            padding: 3rem;
            text-align: center;
            margin-bottom: 2rem;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .upload-zone:hover, .upload-zone.dragover {
            border-color: var(--accent-cyan);
            background: rgba(0, 212, 255, 0.05);
        }
        
        .upload-zone input {
            display: none;
        }
        
        .upload-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 2rem;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(255,255,255,0.1);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 1rem;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📚 分析历史</h1>
            <div>
                <a href="/" class="btn btn-secondary">← 返回主页</a>
            </div>
        </header>
        
        <div class="upload-zone" id="uploadZone">
            <input type="file" id="fileInput" accept=".zip">
            <div class="upload-icon">📦</div>
            <p>拖拽 ZIP 文件到这里，或点击上传</p>
            <p style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.5rem;">
                上传后自动分析并保存到云端
            </p>
        </div>
        
        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>正在上传并分析...</p>
        </div>
        
        <div class="storage-info" id="storageInfo">
            <span>存储信息加载中...</span>
        </div>
        
        <div class="records-grid" id="recordsGrid">
            <div class="empty-state">
                <h2>暂无分析记录</h2>
                <p>上传 ZIP 文件开始分析</p>
            </div>
        </div>
    </div>
    
    <script>
        const uploadZone = document.getElementById('uploadZone');
        const fileInput = document.getElementById('fileInput');
        const loading = document.getElementById('loading');
        const recordsGrid = document.getElementById('recordsGrid');
        
        // 上传区域事件
        uploadZone.addEventListener('click', () => fileInput.click());
        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });
        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });
        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) uploadFile(files[0]);
        });
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) uploadFile(fileInput.files[0]);
        });
        
        // 上传文件
        async function uploadFile(file) {
            if (!file.name.endsWith('.zip')) {
                alert('请上传 ZIP 文件');
                return;
            }
            
            loading.style.display = 'block';
            uploadZone.style.display = 'none';
            
            const formData = new FormData();
            formData.append('file', file);
            
            try {
                const resp = await fetch('/api/storage/upload', {
                    method: 'POST',
                    body: formData
                });
                const data = await resp.json();
                
                if (data.error) {
                    alert('上传失败: ' + data.error);
                } else {
                    alert('上传成功！已保存到云端，ID: ' + data.record_id);
                    loadRecords();
                }
            } catch (e) {
                alert('上传失败: ' + e.message);
            } finally {
                loading.style.display = 'none';
                uploadZone.style.display = 'block';
            }
        }
        
        // 加载记录列表
        async function loadRecords() {
            try {
                const resp = await fetch('/api/storage/records');
                const records = await resp.json();
                
                if (records.length === 0) {
                    recordsGrid.innerHTML = `
                        <div class="empty-state">
                            <h2>暂无分析记录</h2>
                            <p>上传 ZIP 文件开始分析</p>
                        </div>
                    `;
                    return;
                }
                
                recordsGrid.innerHTML = records.map(r => `
                    <div class="record-card">
                        <div class="record-header">
                            <div class="record-title">${r.filename}</div>
                            <span class="record-id">#${r.id}</span>
                        </div>
                        <div class="record-meta">
                            <span>📅 ${r.upload_time}</span>
                            <span>📦 ${r.modules_count} 个模块</span>
                            <span>💾 ${(r.file_size / 1024).toFixed(1)} KB</span>
                        </div>
                        <div class="record-actions">
                            <button class="btn btn-primary" onclick="loadRecord('${r.id}')">
                                📊 查看分析
                            </button>
                            <button class="btn btn-secondary" onclick="reanalyze('${r.id}')">
                                🔄 重新分析
                            </button>
                            <button class="btn btn-danger" onclick="deleteRecord('${r.id}')">
                                🗑️
                            </button>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('加载记录失败:', e);
            }
        }
        
        // 加载存储信息
        async function loadStorageInfo() {
            try {
                const resp = await fetch('/api/storage/info');
                const info = await resp.json();
                
                const storageInfo = document.getElementById('storageInfo');
                if (info.type === 'local') {
                    storageInfo.innerHTML = `
                        <span>本地存储: <strong>${info.total_size_mb} MB</strong> 使用</span>
                        <span>${info.file_count} 个文件 | ${info.record_count} 条记录</span>
                        <button class="btn btn-danger" onclick="clearStorage()">清空存储</button>
                    `;
                } else {
                    storageInfo.innerHTML = `
                        <span>云存储: <strong>Vercel Blob</strong></span>
                        <span>状态: ${info.available ? '✅ 已连接' : '❌ 未配置'}</span>
                    `;
                }
            } catch (e) {
                console.error('加载存储信息失败:', e);
            }
        }
        
        // 加载分析记录
        async function loadRecord(id) {
            try {
                const resp = await fetch(`/api/storage/record/${id}/load`, { method: 'POST' });
                const data = await resp.json();
                
                if (data.error) {
                    alert('加载失败: ' + data.error);
                } else {
                    // 跳转到主页查看分析结果
                    window.location.href = '/?loaded=' + id;
                }
            } catch (e) {
                alert('加载失败: ' + e.message);
            }
        }
        
        // 重新分析
        async function reanalyze(id) {
            if (!confirm('确定要重新分析吗？')) return;
            
            try {
                const resp = await fetch(`/api/storage/record/${id}/load?reanalyze=1`, { method: 'POST' });
                const data = await resp.json();
                
                if (data.error) {
                    alert('分析失败: ' + data.error);
                } else {
                    alert('重新分析完成！');
                    window.location.href = '/?loaded=' + id;
                }
            } catch (e) {
                alert('分析失败: ' + e.message);
            }
        }
        
        // 删除记录
        async function deleteRecord(id) {
            if (!confirm('确定要删除此记录吗？')) return;
            
            try {
                const resp = await fetch(`/api/storage/record/${id}`, { method: 'DELETE' });
                const data = await resp.json();
                
                if (data.error) {
                    alert('删除失败: ' + data.error);
                } else {
                    loadRecords();
                }
            } catch (e) {
                alert('删除失败: ' + e.message);
            }
        }
        
        // 清空存储
        async function clearStorage() {
            if (!confirm('确定要清空所有存储吗？此操作不可恢复！')) return;
            
            try {
                const resp = await fetch('/api/storage/clear', { method: 'POST' });
                const data = await resp.json();
                
                if (data.error) {
                    alert('清空失败: ' + data.error);
                } else {
                    alert('存储已清空');
                    loadRecords();
                    loadStorageInfo();
                }
            } catch (e) {
                alert('清空失败: ' + e.message);
            }
        }
        
        // 初始化
        loadStorageInfo();
        loadRecords();
    </script>
</body>
</html>
'''


def run_server(host='0.0.0.0', port=5000, debug=False):
    print(f"\n🚀 Odoo模块依赖分析器已启动!")
    print(f"📍 访问地址: http://localhost:{port}")
    print(f"📍 网络地址: http://{host}:{port}\n")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_server(debug=True)
