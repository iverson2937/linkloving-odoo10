# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    has_budget = fields.Boolean()
