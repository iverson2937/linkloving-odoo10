# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, api, models


class ProductTemplate(models.Model):
    _inherit = "product.template"
    inner_code = fields.Char(string='国内简称')
    inner_spec = fields.Char(string='国内型号')
