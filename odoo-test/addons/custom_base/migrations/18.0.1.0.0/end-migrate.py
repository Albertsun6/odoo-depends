# -*- coding: utf-8 -*-
# End-migration script for custom_base
# Version: 17.0.1.0.0 -> 18.0.1.0.0
# Generated: 2026-01-07 00:31

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
    
    _logger.info("End-migration custom_base: %s -> 18.0.1.0.0", version)
    
    env = Environment(cr, SUPERUSER_ID, {})
    
    # TODO: 添加结束迁移逻辑
    
    _logger.info("End-migration custom_base completed")
