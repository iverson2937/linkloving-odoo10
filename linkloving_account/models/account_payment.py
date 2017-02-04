# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
}
from odoo import models, fields, api, _


class AccountPaymentRegisterBalance(models.Model):
    _name = 'account.payment.register.balance'
    state = fields.Selection([
        (0, u'未付'),
        (1, u'已付'),
    ], default=0)
    amount = fields.Float()
    payment_id = fields.Many2one('account.payment.register', ondelete='cascade')
    invoice_id = fields.Many2one('account.invoice')


class AccountPaymentRegister(models.Model):
    _name = 'account.payment.register'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    name = fields.Char()
    balance_ids = fields.One2many('account.payment.register.balance', 'payment_id')
    amount = fields.Float(string=u'金额', compute='get_amount', store=True)

    @api.multi
    def register_payment(self):
        amount = self.amount

        context = {'default_payment_type': 'outbound', 'default_amount': amount,
                   'default_partner_id': self.partner_id.id}

        return {
            'name': _('Payment'),
            'view_type': 'form',
            'view_mode': 'form',
            # 'view_id': False,
            'res_model': 'account.supplier.payment.wizard',
            'domain': [],
            'context': dict(context, active_ids=self.ids),
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.depends('invoice_ids')
    def get_amount(self):
        amount = 0
        for invoice in self.invoice_ids:
            amount += invoice.remain_apply_balance
        self.amount = amount

    bank_id = fields.Many2one('res.partner.bank', string=u'账号', domain="[('partner_id', '=', partner_id)]")
    invoice_ids = fields.Many2many('account.invoice')
    receive_date = fields.Date(string=u'收款日期', default=fields.date.today())
    remark = fields.Text(string=u'备注')
    partner_id = fields.Many2one('res.partner', string=u'合作伙伴')
    is_customer = fields.Boolean(related='partner_id.customer', store=True)
    receive_id = fields.Many2one('res.users')
    account_id = fields.Many2one('account.account')
    payment_type = fields.Selection([
        (1, u'付款'),
        (2, u'收款')
    ])

    @api.onchange('partner_id')
    def change_partner_id(self):
        self.invoice_ids = None

    state = fields.Selection([
        ('draft', u'草稿'),
        ('posted', u'提交'),
        ('confirm', u'确认'),
        ('register', u'登记收款'),
        ('done', u'完成'),
        ('cancel', u'取消')
    ], 'State', readonly=True, default='draft')

    _sql_constraints = {
        ('name_uniq', 'unique(name)',
         'Name must be unique!')
    }

    @api.multi
    def reject(self):

        for balance_id in self.balance_ids:
            balance_id.unlink()
        self.state = 'draft'

    @api.multi
    def unlink(self):
        if self.state not in ['draft', 'posted']:
            raise UserError('只能删除草稿和提交状态的付款申请')

        return super(AccountPaymentRegister, self).unlink()

    @api.multi
    def post(self):

        self.state = 'posted'

    @api.multi
    def confirm(self):
        balance = self.amount
        if self.payment_type == 2 and balance > sum(self.mapped('invoice_ids.amount_total')):
            raise UserError('对账单金额必须大于收到货款价格')
        for invoice in self.invoice_ids:
            balance_id = self.env['account.payment.register.balance'].create({
                'payment_id': self.id,
                'invoice_id': invoice.id,
                'amount': invoice.remain_apply_balance if balance >= invoice.remain_apply_balance else balance
            })
            balance -= balance_id.amount
        self.state = 'confirm'

    @api.multi
    def done(self):
        for balance in self.balance_ids:
            if not balance.state:
                raise UserError('有款型登记没有完成，不可以关闭次记录')

        self.state = 'done'

    @api.model
    def create(self, vals):
        payment_type = self._context.get('default_payment_type')

        if 'name' not in vals or vals['name'] == _('New'):
            if payment_type == 2:
                vals['name'] = self.env['ir.sequence'].next_by_code('account.receive') or _('New')
            else:
                vals['name'] = self.env['ir.sequence'].next_by_code('account.pay') or _('New')
        return super(AccountPaymentRegister, self).create(vals)

    @api.model
    def _needaction_domain_get(self):
        """ Returns the domain to filter records that require an action
            :return: domain or False is no action
        """

        if self._context.get('wait_pay'):
            return [('state', '=', 'confirm')]
        if self._context.get('posted'):
            return [('state', '=', 'posted')]


class AccountPayment(models.Model):
    _inherit = 'account.payment'
    team_id = fields.Many2one('crm.team', related='partner_id.team_id')
    customer = fields.Boolean(related='partner_id.customer')

    @api.model
    def default_get(self, fields):
        rec = super(AccountPayment, self).default_get(fields)
        invoice_defaults = self.resolve_2many_commands('invoice_ids', rec.get('invoice_ids'))
        if invoice_defaults and len(invoice_defaults) == 1:
            invoice = invoice_defaults[0]
            amount = 0.0
            for balance_id in invoice['balance_ids']:
                balance_obj = self.env['account.payment.register.balance']
                balance = balance_obj.browse(balance_id)
                if not balance.state:
                    amount += balance.amount
            rec['communication'] = invoice['reference'] or invoice['name'] or invoice['number']
            rec['currency_id'] = invoice['currency_id'][0]
            rec['payment_type'] = invoice['type'] in ('out_invoice', 'in_refund') and 'inbound' or 'outbound'
            rec['partner_type'] = MAP_INVOICE_TYPE_PARTNER_TYPE[invoice['type']]
            rec['partner_id'] = invoice['partner_id'][0]
            rec['amount'] = amount
            print rec['amount']
        return rec

    @api.multi
    def post(self):
        """ Create the journal items for the payment and update the payment's state to 'posted'.
            A journal entry is created containing an item in the source liquidity account (selected journal's default_debit or default_credit)
            and another in the destination reconciliable account (see _compute_destination_account_id).
            If invoice_ids is not empty, there will be one reconciliable move line per invoice to reconcile with.
            If the payment is a transfer, a second journal entry is created in the destination journal to receive money from the transfer account.
        """
        for rec in self:

            if rec.state not in ['draft', 'approve']:
                raise UserError(
                    _("Only a draft payment can be posted. Trying to post a payment in state %s.") % rec.state)

            if any(inv.state != 'open' for inv in rec.invoice_ids):
                raise ValidationError(_("The payment cannot be processed because the invoice is not open!"))

            # Use the right sequence to set the name
            if rec.payment_type == 'transfer':
                sequence_code = 'account.payment.transfer'
            else:
                if rec.partner_type == 'customer':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.customer.invoice'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.customer.refund'
                if rec.partner_type == 'supplier':
                    if rec.payment_type == 'inbound':
                        sequence_code = 'account.payment.supplier.refund'
                    if rec.payment_type == 'outbound':
                        sequence_code = 'account.payment.supplier.invoice'
                else:
                    sequence_code = 'account.payment.employee'
            rec.name = self.env['ir.sequence'].with_context(ir_sequence_date=rec.payment_date).next_by_code(
                sequence_code)

            # Create the journal entry
            amount = rec.amount * (rec.payment_type in ('outbound', 'transfer') and 1 or -1)
            move = rec._create_payment_entry(amount)

            # In case of a transfer, the first journal entry created debited the source liquidity account and credited
            # the transfer account. Now we debit the transfer account and credit the destination liquidity account.
            if rec.payment_type == 'transfer':
                transfer_credit_aml = move.line_ids.filtered(
                    lambda r: r.account_id == rec.company_id.transfer_account_id)
                transfer_debit_aml = rec._create_transfer_entry(amount)
                (transfer_credit_aml + transfer_debit_aml).reconcile()
            # add by allen
            for balance in rec.invoice_ids.balance_ids:
                balance.state = 1

            rec.write({'state': 'posted', 'move_name': move.name})
