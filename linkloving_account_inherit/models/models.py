# -*- coding: utf-8 -*-

from odoo import models, fields, api


class AccountAccountExternal(models.Model):
    _name = 'account.account.additional'

    name = fields.Char()
    line_ids = fields.One2many('account.account.additional.line', 'account_id')

    @api.multi
    def _get_total_amount(self):
        for r in self:
            r.total_amount = sum(line.sub_total for line in r.line_ids)

    total_amount = fields.Float(compute='_get_total_amount')


class AccountAccountExternalLine(models.Model):
    _name = 'account.account.additional.line'

    account_id = fields.Many2one('account.account.additional')
    name = fields.Char(string=u'名称')
    rate = fields.Float(string=u'汇率', default=1)
    amount = fields.Float(string=u'金额')

    sub_total = fields.Float(string=u'人民币小计', compute='_get_sub_total_amount')

    @api.multi
    def _get_sub_total_amount(self):
        for r in self:
            r.sub_total = r.amount * r.rate
