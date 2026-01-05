# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderExtension(models.Model):
    _inherit = 'sale.order'
    
    custom_reference = fields.Char(string='自定义参考号')
    priority_level = fields.Selection([
        ('low', '低'),
        ('normal', '普通'),
        ('high', '高'),
        ('urgent', '紧急'),
    ], string='优先级', default='normal')
