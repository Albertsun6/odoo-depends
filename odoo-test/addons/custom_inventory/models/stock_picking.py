# -*- coding: utf-8 -*-
from odoo import models, fields


class StockPickingExtension(models.Model):
    _inherit = 'stock.picking'
    
    custom_tracking = fields.Char(string='自定义追踪号')
    warehouse_notes = fields.Text(string='仓库备注')
