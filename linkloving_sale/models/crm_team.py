# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in module root
# directory
##############################################################################
from odoo import fields, api, models


class CrmTeam(models.Model):
    _inherit = "crm.team"
    code = fields.Char(string=u'Simple code')
    #for inner_code
    is_domestic=fields.Boolean(string=u'Is Domestic team')
