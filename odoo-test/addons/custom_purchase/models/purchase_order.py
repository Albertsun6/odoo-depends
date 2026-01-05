# -*- coding: utf-8 -*-
from odoo import models, fields


class PurchaseOrderExtension(models.Model):
    _inherit = 'purchase.order'
    
    internal_notes = fields.Text(string='内部备注')
