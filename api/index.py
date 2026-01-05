"""
Vercel Serverless Function 入口
"""
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from odoo_depends.web_app import app

# Vercel Flask handler
app = app
