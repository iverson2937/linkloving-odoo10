# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class ProductTemplate11(models.Model):
    _inherit = 'product.template'
    sub_spec_id = fields.Many2one('product.spec', string=u'子类别')
    spec_id = fields.Many2one('product.spec', string=u'型号')
    partner_id = fields.Many2one('res.partner', domain=[('customer', '=', True), ('is_company', '=', True)],
                                 string=u'客户')
    is_updated = fields.Boolean()

    product_img_count = fields.Integer(compute='_compute_product_img_count', string=u'产品照片数量')

    product_img_ids = fields.One2many('ir.attachment', 'product_ir_img_id', u'产品照片')

    def _compute_product_img_count(self):
        for product in self:
            product.product_img_count = len(product.product_img_ids)

    @api.multi
    def action_view_product_img(self):
        action = self.env.ref('base.action_attachment').read()[0]
        action['domain'] = [('product_ir_img_id', 'in', self.ids)]
        # action['domain'] = [('res_id', 'in', self.ids)]
        return action

    @api.model
    def create(self, vals):
        if not self.env.user.has_group('linkloving_warehouse.group_document_control_user'):
            raise UserError('你没有权限修改物料，请联系文控管理员')
        if vals.get('default_code'):
            if not vals.get('default_code').replace(' ', ''):
                raise UserError(u"料号不能为空")
            vals['default_code'] = vals.get('default_code').replace(' ', '')
        return super(ProductTemplate11, self).create(vals)

    @api.multi
    def write(self, vals):
        if vals.get('default_code'):
            if not vals.get('default_code').replace(' ', ''):
                raise UserError(u"料号不能为空")
            vals['default_code'] = vals.get('default_code').replace(' ', '')
        if 'default_code' in vals and vals['default_code'] != self.default_code:
            vals.update({'is_updated': True})
        return super(ProductTemplate11, self).write(vals)

    @api.multi
    def create_new_product(self):

        form = self.env.ref('linkloving_product.new_product_form_wizard', False)

        return {
            'name': '新建',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'product.template',
            'views': [(form.id, 'form')],
            'view_id': form.id,
            'target': 'new',
        }

    @api.multi
    def product_list(self):
        return {
            'name': '产品',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'view_id': False,
            'type': 'ir.actions.act_window',
            # 'domain': [('payment_id', 'in', self.ids)],
        }

    @api.onchange('categ_id', 'sub_spec_id', 'spec_id', 'partner_id')
    def _get_default_code(self):
        if self.categ_id.code:
            categ_code = self.categ_id.code
            sub_spec_id = self.sub_spec_id.code if self.sub_spec_id else '0'
            spec_id = self.spec_id.code if self.spec_id else '000'
            full_specs = str(sub_spec_id) + str(spec_id)

            if self.partner_id:
                version1 = self.partner_id.customer_code
                if not version1:
                    raise UserError('请设置该客户编码')
                prefix = '.'.join([categ_code, full_specs, version1])
                products = self.env['product.template'].search([('default_code', 'ilike', prefix)])
                if not products:
                    final_version = 'A'
                else:
                    versions = []
                    for product in products:
                        if len(product.default_code.split('.')) > 3:
                            versions.append(product.default_code.split('.')[-1])
                    if not versions:
                        final_version = 'B'
                    else:
                        final_version = chr(ord(max(versions)) + 1)
                full_code = '.'.join([categ_code, full_specs, version1, final_version])
                self.default_code = full_code

            else:
                prefix = '.'.join([categ_code, full_specs])
                products = self.env['product.template'].search([('default_code', 'ilike', prefix)])
                if not products:
                    version1 = '000'
                else:
                    versions = []
                    for product in products:
                        if len(product.default_code.split('.')) == 3:
                            versions.append(product.default_code.split('.')[-1])
                    if versions:
                        version1 = '00' + str(int(max(versions)) + 1)
                    else:
                        version1 = '000'
                full_code = '.'.join([categ_code, full_specs, version1])
                self.default_code = full_code


class ProductIrAttachment(models.Model):
    _inherit = 'ir.attachment'

    product_ir_img_id = fields.Many2one('product.template', string=u'产品照片')

    name = fields.Char('Attachment Name', require=False)

    @api.model
    @api.returns('self', lambda value: value.id)
    def create(self, vals):
        if not (vals.get('res_model') or vals.get('res_id')):
            if self.env.context.get('active_model') == 'product.template':
                if not vals.get('datas'):
                    raise UserError(u"请完善信息")
                vals['product_ir_img_id'] = self.env.context.get('active_ids')[0] if self.env.context.get(
                    'active_ids')  else ''
                # vals['name'] = vals.get('datas_fname')

        return super(ProductIrAttachment, self).create(vals)

    @api.onchange('datas')
    def onchange_datas(self):
        for tar in self:
            tar.name = self.datas_fname.split('.')[0] if self.datas_fname else ' '


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.onchange('categ_id', 'sub_spec_id', 'spec_id', 'partner_id')
    def _get_default_code(self):
        if self.categ_id.code:
            categ_code = self.categ_id.code
            sub_spec_id = self.sub_spec_id.code if self.sub_spec_id else '0'
            spec_id = self.spec_id.code if self.spec_id else '000'
            full_specs = str(sub_spec_id) + str(spec_id)

            if self.partner_id:
                print self.partner_id.name
                version1 = self.partner_id.customer_code
                if not version1:
                    raise UserError('请设置该客户编码')
                prefix = '.'.join([categ_code, full_specs, version1])
                products = self.env['product.product'].search([('default_code', 'ilike', prefix)])
                if not products:
                    final_version = 'A'
                else:
                    versions = []
                    for product in products:
                        if len(product.default_code.split('.')) > 3:
                            versions.append(product.default_code.split('.')[-1])
                    if not versions:
                        final_version = 'B'
                    else:
                        final_version = chr(ord(max(versions)) + 1)
                full_code = '.'.join([categ_code, full_specs, version1, final_version])
                self.default_code = full_code

            else:
                prefix = '.'.join([categ_code, full_specs])
                products = self.env['product.product'].search([('default_code', 'ilike', prefix)])
                if not products:
                    version1 = '000'
                else:
                    versions = []
                    for product in products:
                        if len(product.default_code.split('.')) == 3:
                            versions.append(product.default_code.split('.')[-1])
                    if versions:
                        version1 = '00' + str(int(max(versions)) + 1)
                    else:
                        version1 = '000'
                full_code = '.'.join([categ_code, full_specs, version1])
                self.default_code = full_code
        print self.default_code

    @api.multi
    def create_new_product(self):

        form = self.env.ref('linkloving_product.new_product_form_wizard', False)

        return {
            'name': '新建',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'product.template',
            'views': [(form.id, 'form')],
            'view_id': form.id,
            'target': 'new',
        }

    @api.multi
    def product_list(self):
        return {
            'name': '产品',
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'product.template',
            'view_id': False,
            'type': 'ir.actions.act_window',
            # 'domain': [('payment_id', 'in', self.ids)],
        }
