# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ResPartnerExtension(models.Model):
    _inherit = 'res.partner'
    
    custom_field = fields.Char(string='自定义字段')
    custom_notes = fields.Text(string='自定义备注')
