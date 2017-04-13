# -*- coding: utf-8 -*-

from odoo import models, fields, api


# class linkloving_product_input_extend(models.Model):
#     _name = 'linkloving_product_input_extend.linkloving_product_input_extend'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         self.value2 = float(self.value) / 100

class linklpving_product_product(models.Model):
    _inherit = 'product.product'

    product_ll_type = fields.Selection(related="product_tmpl_id.product_ll_type",
                                       string="类型",
                                       selection=[('raw material', '原料'),
                                                  ('semi-finished', '半成品'),
                                                  ('finished', '成品')])
    order_ll_type = fields.Selection(related="product_tmpl_id.order_ll_type",
                                     string="订单类型", selection=[('ordering', '订单制'),
                                                               ('stock', '备货制')],
                                     help="订单制:路线自动选中按订单生成项,备货制:需要填写最大最小存货数量")

    @api.multi
    def write(self, vals):
        return super(linklpving_product_product, self).write(vals)

class linkloving_product_input_extend(models.Model):
    _inherit = 'product.template'

    product_ll_type = fields.Selection(string="物料类型", selection=[('raw material', '原料'),
                                                                 ('semi-finished', '半成品'),
                                                                 ('finished', '成品')])

    order_ll_type = fields.Selection(string="订单类型",
                                     selection=[('ordering', '订单制'),
                                                ('stock', '备货制')], help="订单制:路线自动选中按订单生成项,备货制:需要填写最大最小存货数量")


    @api.onchange('product_ll_type')
    def _onchange_product_ll_type(self):
        self.product_ll_type = self.product_ll_type
        if self.product_ll_type == "raw material":  # 原料
            self.sale_ok = False
            self.purchase_ok = True
            self.route_ids = [(6, 0, (
            self.env.ref('stock.route_warehouse0_mto').id, self.env.ref('purchase.route_warehouse0_buy').id))]
        elif self.product_ll_type == "semi-finished":  # 半成品
            self.sale_ok = False
            self.purchase_ok = False
            self.route_ids = [(6, 0, (
            self.env.ref('stock.route_warehouse0_mto').id, self.env.ref('mrp.route_warehouse0_manufacture').id))]
        elif self.product_ll_type == "finished":  # 成品
            self.sale_ok = True
            self.purchase_ok = False
            self.route_ids = [(6, 0, [self.env.ref('mrp.route_warehouse0_manufacture').id, ])]
