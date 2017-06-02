# -*- coding: utf-8 -*-
import json
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MrpProductionExtend(models.Model):
    _inherit = 'mrp.production'

    is_bom_update = fields.Boolean()


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.multi
    def bom_update(self):
        if not self.bom_ids:
            raise UserError(u'该产品没有BOM')
        return {
            'type': 'ir.actions.client',
            'tag': 'bom_update',
            'bom_id': self.bom_ids[0].id
        }

    @api.multi
    def apply_bom_update(self):
        bom_id = self.bom_ids[0]
        mos = self.env["mrp.production"].search([('bom_id', '=', bom_id.id), ('state', 'not in', ['cancel', 'done'])])
        for mo in mos:
            if mo.state in ['draft', 'confirmed', 'waiting_material']:
                mo.action_cancel()
                if mo.procurement_ids.move_dest_id.procurement_id:  # 订单制
                    mo.procurement_ids.cancel()
                    mo.procurement_ids.move_dest_id.procurement_id.reset_to_confirmed()
                    mo.procurement_ids.move_dest_id.procurement_id.run()
                elif mo.procurement_ids:
                    mo.procurement_ids.run()
                else:
                    new_mo = mo.copy()
                    new_mo.state = "draft"
            elif mo.state in ['prepare_material_ing', 'finish_prepare_material', 'already_picking', 'progress',
                              'waiting_inspection_finish', 'waiting_rework', 'waiting_inventory_material',
                              'waiting_warehouse_inspection', 'waiting_post_inventory']:
                mo.is_bom_update = True


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.multi
    def bom_update(self):
        if not self.self.product_tmpl_id.bom_ids:
            raise UserError(u'该产品没有BOM')
        return {
            'type': 'ir.actions.client',
            'tag': 'bom_update',
            'bom_id': self.product_tmpl_id.bom_ids[0].id
        }

    @api.multi
    def apply_bom_update(self):
        bom_id = self.product_tmpl_id.bom_ids[0]
        mos = self.env["mrp.production"].search([('bom_id', '=', bom_id.id), ('state', 'not in', ['cancel', 'done'])])
        for mo in mos:
            if mo.state in ['draft', 'confirmed', 'waiting_material']:
                mo.action_cancel()
                if mo.procurement_ids.move_dest_id.procurement_id:  # 订单制
                    mo.procurement_ids.cancel()
                    mo.procurement_ids.move_dest_id.procurement_id.reset_to_confirmed()
                    mo.procurement_ids.move_dest_id.procurement_id.run()
                elif mo.procurement_ids:
                    mo.procurement_ids.run()
                else:
                    new_mo = mo.copy()
                    new_mo.state = "draft"
            elif mo.state in ['prepare_material_ing', 'finish_prepare_material', 'already_picking', 'progress',
                              'waiting_inspection_finish', 'waiting_rework', 'waiting_inventory_material',
                              'waiting_warehouse_inspection', 'waiting_post_inventory']:
                mo.is_bom_update = True
