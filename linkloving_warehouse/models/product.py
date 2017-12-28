# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright 2015 Eezee-It, MONK Software, Vauxoo
#    Copyright 2013 Camptocamp
#    Copyright 2009-2013 Akretion,
#    Author: Emmanuel Samyn, Raphaël Valyi, Sébastien Beau,
#            Benoît Guillot, Joel Grand-Guillaume, Leonardo Donelli
#            Osval Reyes, Yanina Aular
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import calendar
import datetime

from odoo import api
from odoo import fields, models, _
from odoo.exceptions import UserError


class ProductProduct(models.Model):
    _inherit = 'product.product'
    area_id = fields.Many2one('stock.location.area', string='Area', copy=False)
    location_x = fields.Char()
    location_y = fields.Char()
    orderpoint_ids = fields.One2many("stock.warehouse.orderpoint", "product_id")
    product_specs = fields.Text(string=u'Product Specification', related='product_tmpl_id.product_specs')
    _sql_constraints = [
        ('default_code_uniq', 'unique (default_code)', _('Default Code already exist!')),
        # ('name_uniq', 'unique (name)', u'产品名称已存在!')
    ]

    def count_amount(self, start, end):
        orders = self.env['sale.order.line'].search(
            [('product_id', '=', self.id), ('state', '=', 'sale'), ('order_id.date_order', '>=', start),
             ('order_id.date_order', '<=', end)])
        res = sum(order.product_uom_qty for order in orders)
        print res

        return res


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    has_bom_line_lines = fields.Boolean(compute='has_bom_line_ids', string='是否有在BOM中')

    @api.multi
    def has_bom_line_ids(self):
        for product in self:
            line = self.env['mrp.bom.line'].search([('product_id', '=', product.product_variant_ids[0].id)])
            if line:
                product.has_bom_line_lines = True
            else:
                product.has_bom_line_lines = False

    @api.model
    @api.depends("all_mo_ids", "all_mo_ids.state")
    def _compute_has_mo_procure(self):
        print("_compute_has_mo_procure")

        for product in self:
            zaichan_mos = product.all_mo_ids.filtered(lambda x: x.state not in ['done', 'cancel'])
            if zaichan_mos:  # 是否有在产
                product.has_mo_procure = True
            else:
                product.has_mo_procure = False

    @api.model
    @api.depends("all_mo_ids", "all_mo_ids.state")
    def _compute_has_mo_in_plan(self):
        print("_compute_has_mo_in_plan")
        for product in self:
            zaichan_mos = product.all_mo_ids.filtered(lambda x: x.state not in ['cancel', 'draft', 'confirmed', 'done'])
            if zaichan_mos:  # 是否有在产
                product.has_mo_in_plan = True
            else:
                product.has_mo_in_plan = False

    @api.model
    @api.depends("all_mo_ids", "all_mo_ids.state")
    def _compute_has_mo_unplan(self):
        print("_compute_has_mo_unplan")
        for product in self:
            zaichan_mos = product.all_mo_ids.filtered(lambda x: x.state in ['draft', 'confirmed'])
            if zaichan_mos:  # 已排产
                product.has_mo_unplan = True
            else:
                product.has_mo_unplan = False

    @api.depends('stock_move_ids', 'stock_move_ids.state')
    def _compute_is_available_lt_required(self):
        res = self._compute_quantities_dict()
        for product in self:
            product_data = res[product.id]
            print(product_data["qty_available"], product_data["outgoing_qty"])
            if product_data["qty_available"] < product_data["outgoing_qty"]:  # 库存小于需求
                product.is_available_lt_required = True
            else:
                product.is_available_lt_required = False

    @api.depends('stock_move_ids', 'stock_move_ids.state', 'product_variant_ids.orderpoint_ids.product_min_qty')
    def _compute_is_virtual_lt_reordering(self):
        res = self._compute_quantities_dict()
        ress = {k: {'nbr_reordering_rules': 0, 'reordering_min_qty': 0, 'reordering_max_qty': 0} for k in self.ids}
        product_data = self.env['stock.warehouse.orderpoint'].read_group(
            [('product_id.product_tmpl_id', 'in', self.ids)], ['product_id', 'product_min_qty', 'product_max_qty'],
            ['product_id'])
        for data in product_data:
            product = self.env['product.product'].browse([data['product_id'][0]])
            product_tmpl_id = product.product_tmpl_id.id
            ress[product_tmpl_id]['reordering_min_qty'] = data['product_min_qty']

        for product in self:
            product_data = res[product.id]
            if product_data["virtual_available"] < ress[product.id]['reordering_min_qty']:  # 库存小于最小存货规则
                product.is_virtual_lt_reordering = True
            else:
                product.is_virtual_lt_reordering = False

    @api.multi
    @api.depends("all_mo_ids", "all_mo_ids.state")
    def _compute_has_confirmed_mo(self):
        for product in self:
            unplan_mos = product.all_mo_ids.filtered(lambda x: x.state in ['confirmed'])
            if unplan_mos:
                product.has_confirmed_mo = True
            else:
                product.has_confirmed_mo = False

    @api.multi
    @api.depends("all_mo_ids", "all_mo_ids.state")
    def _compute_has_draft_mo(self):
        for product in self:
            unplan_mos = product.all_mo_ids.filtered(lambda x: x.state in ['draft'])
            if unplan_mos:
                product.has_draft_mo = True
            else:
                product.has_draft_mo = False

    stock_move_ids = fields.One2many(comodel_name="stock.move", inverse_name="product_tmpl_id")
    is_virtual_lt_reordering = fields.Boolean(compute="_compute_is_virtual_lt_reordering", store=True)
    is_available_lt_required = fields.Boolean(compute='_compute_is_available_lt_required', store=True)
    all_mo_ids = fields.One2many('mrp.production', 'product_tmpl_id')
    has_mo_in_plan = fields.Boolean(compute='_compute_has_mo_in_plan', store=True)
    has_mo_unplan = fields.Boolean(compute='_compute_has_mo_unplan', store=True)
    has_mo_procure = fields.Boolean(compute='_compute_has_mo_procure', store=True)
    has_confirmed_mo = fields.Boolean(compute='_compute_has_confirmed_mo', store=True)
    has_draft_mo = fields.Boolean(compute='_compute_has_draft_mo', store=True)

    reordering_min_qty = fields.Float(compute='_compute_nbr_reordering_rules', store=True,
                                      inverse='_set_nbr_reordering_rules')
    reordering_max_qty = fields.Float(compute='_compute_nbr_reordering_rules', store=True,
                                      inverse='_set_nbr_reordering_rules')

    order_point_active = fields.Boolean(compute='_compute_order_point_active', store=True,
                                        inverse='_set_nbr_reordering_rules')

    image = fields.Binary(
        "Image", attachment=True,
        copy=False,
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        copy=False,
        help="Medium-sized image of the product. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved, "
             "only when the image exceeds one of those sizes. Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        copy=False,
        help="Small-sized image of the product. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    last1_month_qty = fields.Float(string=u'1个月')
    last2_month_qty = fields.Float(string=u'3个月')
    last3_month_qty = fields.Float(string=u'6个月')
    status = fields.Selection([
        ('eol', '已停产'),
        ('normal', '正常')
    ], track_visibility='onchange')

    # pack_rate = fields.Float(string=u'装箱率')
    @api.multi
    def set_to_eol(self):
        OrderPoint = self.env['stock.warehouse.orderpoint']
        for r in self:
            r.status = 'eol'
            orderPoints = OrderPoint.search([('product_id.product_tmpl_id', 'in', r.ids)])
            if orderPoints:
                orderPoints.write({
                    'active': False
                })

    @api.multi
    def cancel_eol(self):
        for r in self:
            r.status = 'normal'
            r.active = True

    @api.multi
    def view_product_id(self):
        for product in self:
            return {
                'name': product.name,
                'type': 'ir.actions.client',
                'tag': 'product_detail',
                'product_id': product.id
            }
            # return {
            #     'type': 'ir.actions.act_window',
            #     'res_model': 'product.template',
            #     'view_mode': 'form',
            #     'view_type': 'form',
            #     'views': [[False, 'form']],
            #     'target': 'current',
            #     'res_id': product.id
            # }

    @api.multi
    def _set_order_point_active(self):
        OrderPoint = self.env['stock.warehouse.orderpoint']
        orderPoints = OrderPoint.search([('product_id.product_tmpl_id', 'in', self.ids),
                                         ('active', '!=', -1)])

        orderPoints.write({
            'active': True
        })

    @api.multi
    def _set_nbr_reordering_rules(self):
        OrderPoint = self.env['stock.warehouse.orderpoint']
        for product_tmplate in self:
            if product_tmplate.status == 'eol':
                raise UserError('已经停产,不能设置订货规则')
            if product_tmplate.reordering_max_qty < product_tmplate.reordering_min_qty:
                raise UserError(u'最小数量不能大于最大数量')
            if product_tmplate.product_variant_ids:
                product_id = product_tmplate.product_variant_ids[0].id

                orderpoint = OrderPoint.search([('product_id', '=', product_id), ('active', '!=', None)])
                if not orderpoint:
                    orderpoint.create({
                        'product_id': product_tmplate.product_variant_ids[0].id,
                        'product_max_qty': product_tmplate.reordering_max_qty if product_tmplate.reordering_max_qty else 0.0,
                        'product_min_qty': product_tmplate.reordering_min_qty if product_tmplate.reordering_min_qty else 0.0,
                    })
                elif len(orderpoint) > 1:
                    raise UserError(u'有多条存货规则,请确认')
                elif len(orderpoint) == 1:
                    orderpoint.product_max_qty = product_tmplate.reordering_max_qty
                    orderpoint.product_min_qty = product_tmplate.reordering_min_qty
                    orderpoint.active = product_tmplate.order_point_active

    @api.multi
    @api.depends("product_variant_ids.orderpoint_ids.active")
    def _compute_order_point_active(self):
        OrderPoint = self.env['stock.warehouse.orderpoint']
        for tmpl in self:
            if tmpl.product_variant_ids:
                product_id = tmpl.product_variant_ids[0].id
                orderpoint = OrderPoint.search([('product_id', '=', product_id), ('active', '!=', None)], limit=1)
                tmpl.order_point_active = orderpoint.active

    def _compute_nbr_reordering_rules(self):
        res = {k: {'nbr_reordering_rules': 0, 'reordering_min_qty': 0, 'reordering_max_qty': 0} for k in self.ids}
        product_data = self.env['stock.warehouse.orderpoint'].read_group(
            [
                ('product_id.product_tmpl_id', 'in', self.ids),
                ('active', '!=', None)
            ],
            ['product_id', 'product_min_qty', 'product_max_qty'],
            ['product_id'])
        for data in product_data:
            product = self.env['product.product'].browse([data['product_id'][0]])
            product_tmpl_id = product.product_tmpl_id.id
            res[product_tmpl_id]['nbr_reordering_rules'] += int(data['product_id_count'])
            res[product_tmpl_id]['reordering_min_qty'] = data['product_min_qty']
            res[product_tmpl_id]['reordering_max_qty'] = data['product_max_qty']
        for template in self:
            template.nbr_reordering_rules = res[template.id]['nbr_reordering_rules']
            template.reordering_min_qty = res[template.id]['reordering_min_qty']
            template.reordering_max_qty = res[template.id]['reordering_max_qty']

    @api.multi
    def write(self, vals):
        # 销售单或者采购单页面保存也走这个方法
        if 'product_specs' in vals and self.product_specs == vals['product_specs']:
            vals.pop('product_specs')
        if ('name' in vals or 'product_specs' in vals or 'default_code' in vals) and not self.env.user.has_group(
                'linkloving_warehouse.group_document_control_user'):
            raise UserError('你没有权限修改物料，请联系文控管理员')

        # 单位修改,批量修改BOM line 里面的单位
        if 'uom_id' in vals:
            new_uom = self.env['product.uom'].browse(vals['uom_id'])
            updated = self.filtered(lambda template: template.uom_id != new_uom)
            bom_line_ids = self.env['mrp.bom.line'].search(
                [('product_id', 'in', updated.mapped('product_variant_ids').ids)])
            for line in bom_line_ids:
                line.product_uom_id = vals['uom_id']

            print 1111111111
        return super(ProductTemplate, self).write(vals)

    def _get_default_uom_id(self):
        return self.env["product.uom"].search([], limit=1, order='id').id

    uom_id = fields.Many2one(
        'product.uom', 'Unit of Measure',
        default=_get_default_uom_id, required=True,
        help="Default Unit of Measure used for all stock operation.", track_visibility='onchange')

    product_specs = fields.Text(string=u'Product Specification')
    default_code = fields.Char(related='product_variant_ids.default_code')
    area_id = fields.Many2one(related='product_variant_ids.area_id', string='Area')
    location_x = fields.Char(related='product_variant_ids.location_x')
    location_y = fields.Char(related='product_variant_ids.location_y')
    name = fields.Char('Name', index=True, required=True, translate=False)

    @api.depends('stock_move_ids.state')
    def get_stock(self):
        res = self._compute_quantities_dict()
        for product in self:
            product_data = res[product.id]
            product.stock = product_data['qty_available']

    stock = fields.Float(string=u'库存', store=True, compute=get_stock)
    _sql_constraints = [
        ('default_code_uniq1', 'unique (default_code)', _('Default Code already exist!')),
        # ('name_uniq', 'unique (name)', u'产品名称已存在!')
    ]

    # @api.multi
    # def write(self, vals):
    #     if 'uom_id' in vals:
    #         new_uom = self.env['product.uom'].browse(vals['uom_id'])
    #         updated = self.filtered(lambda template: template.uom_id != new_uom)
    #         done_moves = self.env['stock.move'].search(
    #             [('product_id', 'in', updated.mapped('product_variant_ids').ids)], limit=1)
    #
    #     return super(models.Model, self).write(vals)

    @api.multi
    def toggle_active(self):
        """ Inverse the value of the field ``active`` on the records in ``self``. """
        for record in self:

            record.active = not record.active
            active = not record.active
            products = self.env['product.product'].search(
                [('product_tmpl_id', '=', record.id), ('active', '=', active)])
            for product in products:
                product.active = not product.active

    @api.multi
    def action_view_stock_moves(self):
        action = super(ProductTemplate, self).action_view_stock_moves()
        action['context'] = dict({'search_default_done': 1}, **action['context'])
        return action
