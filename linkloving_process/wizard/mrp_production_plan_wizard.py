# -*- coding: utf-8 -*-
import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MrpProductionWizard(models.TransientModel):
    _name = 'mrp.production.plan.wizard'

    date_planned_start = fields.Datetime(
        u'交期', default=fields.Datetime.now)
    partner_id = fields.Many2one('res.partner', domain="[('is_in_charge','=',True)]", string='工序负责人')

    @api.multi
    def action_mo_plan(self):
        context = dict(self._context or {})
        active_ids = context.get('active_ids', []) or []
        for record in self.env['mrp.production'].browse(active_ids):
            record.date_planned_start = self.date_planned_start
            if self.partner_id:
                record.in_charge_id = self.partner_id