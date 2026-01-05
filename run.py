#!/usr/bin/env python3
"""
快速启动脚本 - 运行 Odoo 模块依赖分析器 Web 服务
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from odoo_depends.web_app import app, run_server

# Vercel serverless function 入口
application = app

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Odoo 模块依赖分析器')
    parser.add_argument('-p', '--port', type=int, default=5000, help='端口号 (默认: 5000)')
    parser.add_argument('-d', '--debug', action='store_true', help='调试模式')
    
    args = parser.parse_args()
    
    run_server(port=args.port, debug=args.debug)
