# -*- coding: utf-8 -*-
import json

from odoo import models, fields, api
from models import MO_STATE
import uuid

from odoo.exceptions import UserError

SALE_ORDER_STATE = {
    'sale': u'销售订单',
    'sent': u'已发送报价单',
    'cancel': u'取消',
    'draft': u'草稿',
    'done': u'完成',
}


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.multi
    def show_product_form(self):
        return {
            'name': u'产品明细',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'product.template',
            'target': 'current',
            'res_id': self.product_id.product_tmpl_id.id
        }

    @api.multi
    def show_product_detail(self):
        return {
            'name': self.name,
            'type': 'ir.actions.client',
            'tag': 'product_detail',
            'product_id': self.product_id.product_tmpl_id.id
        }

    @api.multi
    def get_mo_list(self):

        for line in self:
            origin = line.order_id.origin
            sources = []
            res = []
            if origin:
                mos = origin.split(',')

                for mo in mos:
                    mo_ids = mo.split(':')
                    for mo_id in mo_ids:
                        sources.append(mo_id.strip())
            for s in set(sources):
                if s.startswith('MO'):
                    mo_id = self.env['mrp.production'].sudo().search([('name', '=', s)])
                    for move_line in mo_id.sim_stock_move_lines:

                        if line.product_id.id == move_line.product_id.id:
                            res.append({
                                'name': mo_id.name,
                                'product_qty': move_line.product_uom_qty,
                                'product_id': mo_id.product_tmpl_id.product_variant_ids[0].id,
                                'date': mo_id.date_planned_start,
                                'state': MO_STATE[mo_id.state],
                                'id': mo_id.id,
                                'model': "mrp.production",
                                'origin': mo_id.origin,
                                'status_light': mo_id.status_light,
                                'material_light': mo_id.material_light,
                            })
                else:
                    so_id = self.env['sale.order'].sudo().search([('name', '=', s)])
                    for order_line_id in so_id.order_line:
                        if line.product_id == order_line_id.product_id:
                            res.append({
                                'partner_name': so_id.partner_id.name,
                                'name': so_id.name,
                                'id': so_id.id,
                                'model': 'sale.order',
                                'origin': False,
                                'product_qty': order_line_id.product_qty,
                                'date': so_id.validity_date,
                                'status_light': so_id.status_light,
                                'material_light': so_id.material_light,
                            })
            return res

    @api.model
    def get_source_list(self, origin, product_id):
        sources = []
        res = []
        if origin:
            mos = origin.split(',')

            for mo in mos:
                mo_ids = mo.split(':')
                for mo_id in mo_ids:
                    sources.append(mo_id.strip())
            for s in set(sources):
                if s.startswith('MO'):
                    mo_id = self.env['mrp.production'].search([('name', '=', s)])
                    for move_line in mo_id.sim_stock_move_lines:
                        print move_line.product_id.id
                        print product_id
                        if product_id == move_line.product_id.id:
                            res.append({
                                'name': mo_id.name,
                                'product_qty': move_line.product_uom_qty,
                                'product_id': mo_id.product_tmpl_id.product_variant_ids[0].id,
                                'date': mo_id.date_planned_start,
                                'state': MO_STATE[mo_id.state],
                                'uuid': str(uuid.uuid1()),
                                'id': mo_id.id,
                                'model': "mrp.production",
                                'origin': mo_id.origin,
                                'status_light': mo_id.status_light,
                                'material_light': mo_id.material_light,
                            })
                elif s.startswith('SO'):
                    so_id = self.env['sale.order'].search([('name', '=', s)])
                    for order_line_id in so_id.order_line:
                        if product_id == order_line_id.product_id.id:
                            res.append({
                                'partner_name': so_id.partner_id.name,
                                'name': so_id.name,
                                'id': so_id.id,
                                'model': 'sale.order',
                                'origin': False,
                                'state': SALE_ORDER_STATE[so_id.state],
                                'product_qty': order_line_id.product_qty,
                                'date': so_id.validity_date,
                                'status_light': so_id.status_light,
                                'material_light': so_id.material_light,
                            })

            return res


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    @api.multi
    def get_mail_message(self):
        for mo in self:
            return [
                {'name': 'allen', 'time': '2017-10-19', 'description': 'abc'}
            ]
