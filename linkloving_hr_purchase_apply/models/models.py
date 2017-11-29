# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons import decimal_precision as dp
import jpush

try:
    from linklovingaddons.linkloving_app_api.models.models import JPushExtend
except Exception:
    pass



class PurchaseApply(models.Model):
    _name = 'hr.purchase.apply'
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    name = fields.Char()
    apply_date = fields.Date(string=u'申请日期', default=fields.Date.context_today)
    employee_id = fields.Many2one('hr.employee',
                                  default=lambda self: self.env['hr.employee'].search([('user_id', '=', self.env.uid)],
                                                                                      limit=1))
    approve_ids = fields.Many2many('res.users')
    department_id = fields.Many2one('hr.department')
    to_approve_id = fields.Many2one('res.users')
    line_ids = fields.One2many('hr.purchase.apply.line', 'apply_id')
    untaxed_amount = fields.Float(string='Subtotal', store=True, compute='_compute_amount',
                                  digits=dp.get_precision('Account'))
    total_amount = fields.Float(string='Total', store=True, compute='_compute_amount',
                                digits=dp.get_precision('Account'))
    reject_reason = fields.Char(string=u'拒绝原因')

    @api.depends('line_ids.sub_total')
    def _compute_amount(self):
        for record in self:
            record.total_amount = sum(line.sub_total for line in record.line_ids)

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        self.address_id = self.employee_id.address_home_id
        self.department_id = self.employee_id.department_id

    @api.multi
    def refuse_application(self, reason):
        self.write({'state': 'cancel'})
        for record in self:
            body = (_(
                "Your Expense %s has been refused.<br/><ul class=o_timeline_tracking_value_list><li>Reason<span> : </span><span class=o_timeline_tracking_value>%s</span></li></ul>") % (
                        record.name, reason))
            record.message_post(body=body)
            record.to_approve_id = False

    state = fields.Selection([
        ('draft', u'草稿'),
        ('submit', u'提交'),
        ('manager1_approve', u'一级审核'),
        ('manager2_approve', u'二级审核'),
        ('cancel', u'取消'),
        ('approve', u'批准'),
        ('done', u'完成')
    ], default='draft', track_visibility='onchange')
    company_id = fields.Many2one('res.company')

    def _get_is_show(self):
        is_show = False
        if self.env.user.id == self.to_approve_id.id:
            is_show = True
        self.is_show = is_show

    is_show = fields.Boolean(compute=_get_is_show)
    description = fields.Text()

    @api.multi
    def refuse_payment(self, reason):
        self.write({'state': 'cancel', 'approve_ids': [(4, self.env.user.id)]})
        for sheet in self:
            body = (_(
                "申购单 %s 已经取消.<br/><ul class=o_timeline_tracking_value_list><li>原因<span> : </span><span class=o_timeline_tracking_value>%s</span></li></ul>") % (
                        sheet.name, reason))
            sheet.message_post(body=body)
            sheet.to_approve_id = False
            sheet.reject_reason = reason

        #推送
        JPushExtend.send_notification_push(audience=jpush.audience(
            jpush.alias(sheet.create_uid.id)
        ), notification=_("申购单：%s被拒绝") % (sheet.name),
            body=_("原因：%s") % (reason))

    @api.multi
    def create_message_post(self,body_str):
        for sheet in self:
            body = body_str
            sheet.message_post(body=body)

    @api.multi
    def unlink(self):
        for r in self:
            if r.state not in ['draft', 'cancel']:
                raise UserError('只可以删除草稿状态的采购申请.')
        return super(PurchaseApply, self).unlink()

    @api.model
    def create(self, vals):
        return super(PurchaseApply, self).create(vals)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.purchase.apply') or '/'

        res = super(PurchaseApply, self).create(vals)
        return res

    @api.multi
    def hr_purchase_apply_post(self):
        for exp in self:
            if not exp.line_ids:
                raise UserError(u'请填写报销明细')

            department = exp.department_id
            state, to_approve_id = department.get_to_approve_id(exp.employee_id, exp.total_amount)
            print to_approve_id
            if not state:
                state = 'submit'
            exp.write({
                'state': state,
                'to_approve_id': to_approve_id
            })

        JPushExtend.send_notification_push(audience=jpush.audience(
            jpush.alias(exp.to_approve_id.id)
        ), notification=exp.name,
            body=_("申购单：%s 等待审核！") % (exp.name))

    def reset_hr_purchase_apply(self):
        self.hr_purchase_apply_post()

    @api.multi
    def manager1_approve(self):
        if not self.env.user.employee_ids.ids:
            raise UserError(u'该用户没有设置员工')
        department = self.env.user.employee_ids.department_id
        if not department:
            UserError(u'请设置该员工部门')
        state, to_approve_id = department.get_to_approve_id(self.env.user.employee_ids[0], self.total_amount)
        if not state:
            state = 'manager1_approve'
        print 'd', to_approve_id
        self.write({
            'state': state,
            'to_approve_id': to_approve_id,
            'approve_ids': [(4, self.env.user.id)]
        })

    @api.multi
    def manager2_approve(self):
        if not self.env.user.employee_ids.ids:
            raise UserError(u'该用户没有设置员工')
        department = self.env.user.employee_ids.department_id
        if not department:
            UserError(u'请设置该员工部门')
        state, to_approve_id = department.get_to_approve_id(self.env.user.employee_ids[0], self.total_amount)
        if not state:
            state = 'manager2_approve'
        self.write({
            'state': state,
            'to_approve_id': to_approve_id,
            'approve_ids': [(4, self.env.user.id)]
        })

    @api.multi
    def manager3_approve(self):
        if not self.env.user.employee_ids.ids:
            raise UserError(u'该用户没有设置员工')
        department = self.env.user.employee_ids.department_id
        if not department:
            UserError(u'请设置该员工部门')
        state, to_approve_id = department.get_to_approve_id(self.env.user.employee_ids[0], self.total_amount)
        if not state:
            state = 'manager3_approve'
        self.write({
            'state': state,
            'to_approve_id': to_approve_id,
            'approve_ids': [(4, self.env.user.id)]
        })

    @api.model
    def _needaction_domain_get(self):
        """ Returns the domain to filter records that require an action
            :return: domain or False is no action
        """
        if self._context.get('to_approve_id'):
            return [('to_approve_id', '=', self.env.user.id)]
        if self._context.get('state') == 'draft':
            return [('state', '=', 'draft'), ('employee_id.user_id', '=', self.env.user.id)]
        if self._context.get('state') == 'cancel':
            return [('state', '=', 'cancel'), ('employee_id.user_id', '=', self.env.user.id)]


class PurchaseApplyLine(models.Model):
    _name = 'hr.purchase.apply.line'

    apply_id = fields.Many2one('hr.purchase.apply')
    name = fields.Char(related='apply_id.name')
    employee_id = fields.Many2one('hr.employee', related='apply_id.employee_id')
    sheet_id = fields.Many2one('hr.expense.sheet')
    product_id = fields.Many2one('product.product', string='产品',
                                 domain=[('can_be_expensed', '=', True)], required=True)
    product_qty = fields.Float(string=u'申购数量', default=1.00)
    price_unit = fields.Float(string=u'预计金额')
    description = fields.Char(string=u'说明')
    sub_total = fields.Float(compute='_compute_amount', string='小计')
    tax_id = fields.Many2one('account.tax', string=u'税率')
    state = fields.Selection([
        ('draft', u'草稿'),
        ('submit', u'提交'),
        ('manager1_approve', u'一级审核'),
        ('manager2_approve', u'二级审核'),
        ('cancel', u'取消'),
        ('approve', u'批准'),
        ('done', u'完成')
    ], related='apply_id.state')

    @api.depends('price_unit', 'product_qty')
    def _compute_amount(self):
        for line in self:
            line.sub_total = line.price_unit * line.product_qty

    @api.one
    @api.constrains('amount')
    def _check_amount(self):
        if not self.amount > 0.0:
            raise ValidationError('金额必须大于0.')

    @api.multi
    def name_get(self):
        return [(order.name, '%s %s' % (order.name, '#%s' % order.product_id.name)) for order in self]
