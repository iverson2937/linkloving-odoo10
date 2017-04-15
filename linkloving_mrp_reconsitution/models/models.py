# -*- coding: utf-8 -*-
# from dateutil.relativedelta import relativedelta
from collections import defaultdict

from psycopg2._psycopg import OperationalError

from odoo import models, fields, api, _, registry
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import float_compare, float_round, DEFAULT_SERVER_DATETIME_FORMAT

class linkloving_product_extend(models.Model):
    _inherit = "product.product"

    qty_require = fields.Float(u"需求数量")
    is_trigger_by_so = fields.Boolean(default=False)

class linkloving_product_product_extend(models.Model):
    _inherit = "product.template"

    qty_require = fields.Float(related="product_variant_id.qty_require")
    is_trigger_by_so = fields.Boolean(default=False, related="product_variant_id.is_trigger_by_so")

class linkloving_production_extend1(models.Model):
    _inherit = "mrp.production"

    origin_sale_id = fields.Many2one("sale.order", string=u"源销售单据名称")
    origin_mo_id = fields.Many2one("mrp.production", string=u"源生产单据名称")

class linkloving_purchase_order_extend(models.Model):
    _inherit = "purchase.order"

    origin_sale_id = fields.Many2one("sale.order", string=u"源销售单据名称")
    origin_mo_id = fields.Many2one("mrp.production", string=u"源生产单据名称")

class linkloving_procurement_order_extend(models.Model):
    _inherit = "procurement.order"

    def _search_suitable_rule_new(self, product_id, domain):
        """ First find a rule among the ones defined on the procurement order
        group; then try on the routes defined for the product; finally fallback
        on the default behavior """
        if self.get_warehouse():
            domain = expression.AND(
                    [['|', ('warehouse_id', '=', self.get_warehouse().id), ('warehouse_id', '=', False)], domain])
        Pull = self.env['procurement.rule']
        res = self.env['procurement.rule']
        if product_id.route_ids:
            res = Pull.search(expression.AND([[('route_id', 'in', product_id.route_ids.ids)], domain]),
                              order='route_sequence, sequence', limit=1)
        if not res:
            product_routes = product_id.route_ids | product_id.categ_id.total_route_ids
            if product_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', product_routes.ids)], domain]),
                                  order='route_sequence, sequence', limit=1)
        if not res:
            warehouse_routes = self.get_warehouse().route_ids
            if warehouse_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', warehouse_routes.ids)], domain]),
                                  order='route_sequence, sequence', limit=1)
        if not res:
            res = Pull.search(expression.AND([[('route_id', '=', False)], domain]), order='sequence', limit=1)
        return res

    def get_warehouse(self):
        warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1)
        return warehouse_ids

    def _find_parent_locations_new(self):
        parent_locations = self.env['stock.location']
        location = self.get_warehouse().lot_stock_id
        while location:
            parent_locations |= location
            location = location.location_id
        return parent_locations

    def get_suitable_rule(self, product_id):
        all_parent_location_ids = self._find_parent_locations_new()
        rule = self._search_suitable_rule_new(product_id, [('location_id', 'in', all_parent_location_ids.ids)])
        return rule

    def get_actual_require_qty_with_param(self, product_id, require_qty_this_time):
        actual_need_qty = 0

        rule = self.get_suitable_rule(product_id)

        if rule.action == "manufacture":
            if rule.procure_method == "make_to_order":
                ori_require_qty = product_id.qty_require  # 初始需求数量
                real_require_qty = product_id.qty_require + require_qty_this_time  # 加上本次销售的需求数量
                stock_qty = product_id.qty_available  # 库存数量

                if ori_require_qty > stock_qty and real_require_qty > stock_qty:  # 初始需求 > 库存  并且 现有需求 > 库存
                    actual_need_qty = require_qty_this_time
                elif ori_require_qty <= stock_qty and real_require_qty > stock_qty:
                    actual_need_qty = real_require_qty - stock_qty
            else:
                product_id.is_trigger_by_so = True
                xuqiul = product_id.qty_require + require_qty_this_time
                OrderPoint = self.env['stock.warehouse.orderpoint'].search([("product_id", "=", product_id.id)],
                                                                           limit=1)
                qty = xuqiul + OrderPoint.product_min_qty - product_id.qty_available
                mos = self.env["mrp.production"].search(
                        [("product_id", "=", product_id.id), ("state", "not in", ("cancel", "done"))])
                qty_in_procure = 0
                for mo in mos:
                    qty_in_procure += mo.product_qty
                if qty - qty_in_procure > 0:  # 需求量+最小存货-库存-在产数量
                    actual_need_qty = xuqiul + max(OrderPoint.product_min_qty,
                                                   OrderPoint.product_max_qty) - product_id.qty_available - qty_in_procure

        elif rule.action == "buy":
            xuqiul = product_id.qty_require + require_qty_this_time
            pos = self.env["purchase.order"].search([("state", "=", ("make_by_mrp", "draft"))])
            chose_po_lines = self.env["purchase.order.line"]
            total_draft_order_qty = 0
            for po in pos:
                for po_line in po.order_line:
                    if po_line.product_id.id == product_id.id:
                        chose_po_lines += po_line
                        total_draft_order_qty += po_line.product_qty
                        break
            if total_draft_order_qty + product_id.incoming_qty + product_id.qty_available - xuqiul < 0:
                actual_need_qty = xuqiul - (total_draft_order_qty + product_id.incoming_qty + product_id.qty_available)

        return actual_need_qty

    @api.model
    def _procure_orderpoint_confirm(self, use_new_cursor=False, company_id=False):
        """ Create procurements based on orderpoints.
        :param bool use_new_cursor: if set, use a dedicated cursor and auto-commit after processing each procurement.
            This is appropriate for batch jobs only.
        """
        if use_new_cursor:
            cr = registry(self._cr.dbname).cursor()
            self = self.with_env(self.env(cr=cr))

        OrderPoint = self.env['stock.warehouse.orderpoint']
        Procurement = self.env['procurement.order']
        ProcurementAutorundefer = Procurement.with_context(procurement_autorun_defer=True)
        procurement_list = []

        orderpoints_noprefetch = OrderPoint.with_context(prefetch_fields=False).search(
                company_id and [('company_id', '=', company_id)] or [],
                order=self._procurement_from_orderpoint_get_order())
        while orderpoints_noprefetch:
            orderpoints = OrderPoint.browse(orderpoints_noprefetch[:1000].ids)
            orderpoints_noprefetch = orderpoints_noprefetch[1000:]
            orderpoint_need_recal = self.env['stock.warehouse.orderpoint']
            # Calculate groups that can be executed together
            location_data = defaultdict(
                lambda: dict(products=self.env['product.product'], orderpoints=self.env['stock.warehouse.orderpoint'],
                             groups=list()))
            for orderpoint in orderpoints:
                key = self._procurement_from_orderpoint_get_grouping_key([orderpoint.id])
                location_data[key]['products'] += orderpoint.product_id
                location_data[key]['orderpoints'] += orderpoint
                location_data[key]['groups'] = self._procurement_from_orderpoint_get_groups([orderpoint.id])

            for location_id, location_data in location_data.iteritems():
                location_orderpoints = location_data['orderpoints']
                product_context = dict(self._context, location=location_orderpoints[0].location_id.id)
                substract_quantity = location_orderpoints.subtract_procurements_from_orderpoints()

                for group in location_data['groups']:
                    if group['to_date']:
                        product_context['to_date'] = group['to_date'].strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                    product_quantity = location_data['products'].with_context(product_context)._product_available()
                    for orderpoint in location_orderpoints:
                        try:
                            op_product_virtual = product_quantity[orderpoint.product_id.id]['virtual_available']
                            if op_product_virtual is None:
                                continue
                            if float_compare(op_product_virtual, orderpoint.product_min_qty,
                                             precision_rounding=orderpoint.product_uom.rounding) <= 0:
                                qty = max(orderpoint.product_min_qty, orderpoint.product_max_qty) - op_product_virtual
                                remainder = orderpoint.qty_multiple > 0 and qty % orderpoint.qty_multiple or 0.0

                                if float_compare(remainder, 0.0,
                                                 precision_rounding=orderpoint.product_uom.rounding) > 0:
                                    qty += orderpoint.qty_multiple - remainder

                                if float_compare(qty, 0.0, precision_rounding=orderpoint.product_uom.rounding) < 0:
                                    continue
                                qty -= substract_quantity[orderpoint.id]
                                qty_rounded = float_round(qty, precision_rounding=orderpoint.product_uom.rounding)
                                rule = self.get_suitable_rule(orderpoint.product_id)
                                if rule.action == "buy":
                                    total_draft_order_qty = self.get_draft_po_qty(orderpoint.product_id)
                                    qty_rounded -= total_draft_order_qty
                                if qty_rounded > 0:
                                    new_procurement = ProcurementAutorundefer.create(
                                            orderpoint._prepare_procurement_values(qty_rounded,
                                                                                   **group['procurement_values']))
                                    procurement_list.append(new_procurement)
                                    new_procurement.message_post_with_view('mail.message_origin_link',
                                                                           values={'self': new_procurement,
                                                                                   'origin': orderpoint},
                                                                           subtype_id=self.env.ref('mail.mt_note').id)
                                    self._procurement_from_orderpoint_post_process([orderpoint.id])
                                if use_new_cursor:
                                    cr.commit()

                        except OperationalError:
                            if use_new_cursor:
                                orderpoints_noprefetch += orderpoint.id
                                cr.rollback()
                                continue
                            else:
                                raise

            try:
                # TDE CLEANME: use record set ?
                procurement_list.reverse()
                procurements = self.env['procurement.order']
                orderpoints_noprefetch += orderpoint_need_recal  # 重新
                for p in procurement_list:
                    procurements += p
                procurements.run()
                if use_new_cursor:
                    cr.commit()
            except OperationalError:
                if use_new_cursor:
                    cr.rollback()
                    continue
                else:
                    raise

            if use_new_cursor:
                cr.commit()

        if use_new_cursor:
            cr.commit()
            cr.close()
        return {}


    @api.multi
    def make_mo(self):
        """ Create production orders from procurements """
        res = {}
        Production = self.env['mrp.production']
        for procurement in self:
            ProductionSudo = Production.sudo().with_context(force_company=procurement.company_id.id)
            bom = procurement._get_matching_bom()
            if bom:
                # create the MO as SUPERUSER because the current user may not have the rights to do it
                # (mto product launched by a sale for example)
                vals = procurement._prepare_mo_vals(bom)
                if vals["product_qty"] == 0:
                    print("dont need create mo")
                    return {procurement.id : 1}
                production = ProductionSudo.create(vals)
                res[procurement.id] = production.id
                procurement.message_post(body=_("Manufacturing Order <em>%s</em> created.") % (production.name))
            else:
                res[procurement.id] = False
                procurement.message_post(body=_("No BoM exists for this product!"))
        return res

# # class linkloving_mrp_reconsitution(models.Model):
# #     _name = 'linkloving_mrp_reconsitution.linkloving_mrp_reconsitution'
#
# #     name = fields.Char()
# #     value = fields.Integer()
# #     value2 = fields.Float(compute="_value_pc", store=True)
# #     description = fields.Text()
# #
# #     @api.depends('value')
# #     def _value_pc(self):
# #         self.value2 = float(self.
# ) / 100
#
# #需求量
# from odoo.exceptions import UserError
# from odoo.osv import expression
#
# class linkloving_mrp_requirement(models.Model):
#     _name = "mrp.requirement"
#
#     required_qty = fields.Float(u"需求数量")
#     product_id = fields.Many2one("product.product", u"需求产品")
#     state = fields.Selection([("draft", u"草稿"),
#                               ("running",u"运行中"),
#                               ("done", u"完成")], default="draft")
#
#     orign_order = fields.Char(u"源单据")
#     rule_id = fields.Many2one("procurement.rule")
#     location_id = fields.Many2one('stock.location', 'Procurement Location')  # not required because task may create procurements that aren't linked to a location with sale_service
#     route_ids = fields.Many2many(
#         'stock.location.route', 'stock_route_warehouse', 'warehouse_id', 'route_id',
#         'Routes', domain="[('warehouse_selectable', '=', True)]",
#         help='Defaults routes through the warehouse')
#
#     warehouse_id = fields.Many2one('stock.warehouse', string='Warehouse')
#     partner_dest_id = fields.Many2one('res.partner', 'Customer Address', help="In case of dropshipping, we need to know the destination address more precisely")
#     product_uom = fields.Many2one('product.uom', 'Unit of Measure')
#     company_id = fields.Many2one(
#         'res.company', 'Company',)
#
#     bom_id = fields.Many2one(
#         'mrp.bom', 'Bill of Material',
#         readonly=True, states={'confirmed': [('readonly', False)]},
#         help="Bill of Materials allow you to define the list of required raw materials to make a finished product.")
#
#     date_planned = fields.Datetime(
#         'Scheduled Date', default=fields.Datetime.now,
#         required=True, index=True, track_visibility='onchange')
#
#     @api.multi
#     def run(self, autocommit=False):
#         # TDE FIXME: avoid browsing everything -> avoid prefetching ?
#         for procurement in self:
#             # we intentionnaly do the browse under the for loop to avoid caching all ids which would be resource greedy
#             # and useless as we'll make a refresh later that will invalidate all the cache (and thus the next iteration
#             # will fetch all the ids again)
#             if procurement.state not in ("running", "done"):
#                res = procurement._run()
#                if res:
#                  procurement.write({'state': 'running'})
#         return True
#
#     @api.multi
#     def _run(self):
#         self.ensure_one()
#         all_parent_location_ids = self._find_parent_locations()
#         rule = self._search_suitable_rule([('location_id', 'in', all_parent_location_ids.ids)])
#         self.write({"rule_id" : rule.id})
#         if rule:
#             if rule.action == 'manufacture':#如果是製造就返回製造訂單
#                 return self.make_mo()
#             elif rule.action == 'buy':
#                 return self.make_po()
#
#     def get_actual_require_qty(self):
#         ori_require_qty = self.product_id.require_qty  # 初始需求数量
#         real_require_qty = self.required_qty + self.product_id.require_qty  # 加上本次销售的需求数量
#         stock_qty = self.product_id.qty_available  # 库存数量
#
#         actual_need_qty = 0
#         if ori_require_qty > stock_qty and real_require_qty > stock_qty:  # 初始需求 > 库存  并且 现有需求 > 库存
#             actual_need_qty = self.required_qty
#         elif ori_require_qty <= stock_qty and real_require_qty > stock_qty:
#             actual_need_qty = real_require_qty - stock_qty
#
#         return actual_need_qty
#     @api.multi
#     def make_mo(self):
#         """ Create production orders from procurements """
#         res = {}
#         Production = self.env['mrp.production']
#         for procurement in self:
#             ProductionSudo = Production.sudo().with_context()
#             bom = procurement._get_matching_bom()
#             if bom:
#                 # create the MO as SUPERUSER because the current user may not have the rights to do it (mto product launched by a sale for example)
#                 production = ProductionSudo.create(procurement._prepare_mo_vals(bom))
#
#                 bom_explores = bom.explode(self.product_id, self.required_qty)
#                 mrp_requirements = self._create_ro(bom_explores[1], production)
#                 mrp_requirements.run()
#                 res[procurement.id] = production.id
#             else:
#                 res[procurement.id] = False
#         return res
#
#     def _create_ro(self, bom_explode, production_order):
#         company = self.env.user.company_id.id
#         warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', company)], limit=1)
#
#         mrp_requirements = self.env["mrp.requirement"]
#         for bom_line, line_data in bom_explode:
#             requiment = mrp_requirements.create({
#                 "required_qty": line_data.get("qty"),
#                 "product_id": bom_line.product_id.id,
#                 "orign_order": production_order.name,
#                 "state": "draft",
#                 "location_id": warehouse_ids.lot_stock_id.id,
#                 'route_ids': bom_line.product_id.route_ids or [],
#                 'warehouse_id': warehouse_ids.id or False,
#                 # 'partner_dest_id': order_line.order_id.partner_shipping_id.id,
#                 'product_uom': bom_line.product_id.uom_id.id,
#                 'company_id':self.env.user.company_id.id,
#             })
#             mrp_requirements += requiment
#         return mrp_requirements
#     @api.multi
#     def _get_matching_bom(self):
#         """ Finds the bill of material for the product from procurement order. """
#         if self.bom_id:
#             return self.bom_id
#         return self.env['mrp.bom'].with_context(
#             company_id=self.company_id.id, force_company=self.company_id.id
#         )._bom_find(product=self.product_id, picking_type=self.rule_id.picking_type_id)  # TDE FIXME: context bullshit
#
#     @api.multi
#     def make_po(self):
#         cache = {}
#         res = []
#         for procurement in self:
#             suppliers = procurement.product_id.seller_ids.filtered(lambda r: not r.product_id or r.product_id == procurement.product_id)
#             if not suppliers:
#                 continue
#             supplier = suppliers[0]
#             partner = supplier.name
#
#             gpo = procurement.rule_id.group_propagation_option
#             group = (gpo == 'fixed' and procurement.rule_id.group_id) or \
#                     (gpo == 'propagate' and procurement.group_id) or False
#
#             domain = (
#                 ('partner_id', '=', partner.id),
#                 ('state', '=', 'make_by_mrp'),
#                 ('picking_type_id', '=', procurement.rule_id.picking_type_id.id),
#                 ('company_id', '=', procurement.company_id.id),
#                 ('dest_address_id', '=', procurement.partner_dest_id.id))
#             if group:
#                 domain += (('group_id', '=', group.id),)
#
#             if domain in cache:
#                 po = cache[domain]
#             else:
#                 po = self.env['purchase.order'].search([dom for dom in domain])
#                 po = po[0] if po else False
#                 cache[domain] = po
#             if not po:
#                 vals = procurement._prepare_purchase_order(partner)
#                 po = self.env['purchase.order'].create(vals)
#                 cache[domain] = po
#             elif not po.origin or procurement.orign_order not in po.origin.split(', '):
#                 # Keep track of all procurements
#                 if po.origin:
#                     if procurement.orign_order:
#                         po.write({'origin': po.origin + ', ' + procurement.orign_order})
#                     else:
#                         po.write({'origin': po.origin})
#                 else:
#                     po.write({'origin': procurement.orign_order})
#             if po:
#                 res += [procurement.id]
#
#             # Create Line
#             po_line = False
#             for line in po.order_line:
#                 if line.product_id == procurement.product_id and line.product_uom == procurement.product_id.uom_po_id:
#                     procurement_uom_po_qty = procurement.product_uom._compute_quantity(procurement.product_qty, procurement.product_id.uom_po_id)
#                     seller = procurement.product_id._select_seller(
#                         partner_id=partner,
#                         quantity=line.product_qty + procurement_uom_po_qty,
#                         date=po.date_order and po.date_order[:10],
#                         uom_id=procurement.product_id.uom_po_id)
#
#                     price_unit = self.env['account.tax']._fix_tax_included_price(seller.price, line.product_id.supplier_taxes_id, line.taxes_id) if seller else 0.0
#                     if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
#                         price_unit = seller.currency_id.compute(price_unit, po.currency_id)
#
#                     po_line = line.write({
#                         'product_qty': line.product_qty + procurement_uom_po_qty,
#                         'price_unit': price_unit,
#                         'procurement_ids': [(4, procurement.id)]
#                     })
#                     break
#             if not po_line:
#                 vals = procurement._prepare_purchase_order_line(po, supplier)
#                 self.env['purchase.order.line'].create(vals)
#         return res
#
#     def _get_date_planned(self):
#         format_date_planned = fields.Datetime.from_string(self.date_planned)
#         date_planned = format_date_planned - relativedelta(days=self.product_id.produce_delay or 0.0)
#         date_planned = date_planned - relativedelta(days=self.company_id.manufacturing_lead)
#         return date_planned
#
#     def _prepare_mo_vals(self, bom):
#         return {
#             'origin': self.orign_order,
#             'product_id': self.product_id.id,
#             'product_qty': self.get_actual_require_qty(),
#             'product_uom_id': self.product_uom.id,
#             'location_src_id': self.rule_id.location_src_id.id or self.location_id.id,
#             'location_dest_id': self.location_id.id,
#             'bom_id': bom.id,
#             'date_planned_start': fields.Datetime.to_string(self._get_date_planned()),
#             'date_planned_finished': self.date_planned,
#             # 'procurement_group_id': self.group_id.id,
#             'propagate': self.rule_id.propagate,
#             'picking_type_id': self.rule_id.picking_type_id.id or self.warehouse_id.manu_type_id.id,
#             'company_id': self.company_id.id,
#             'state' : 'draft',
#             'process_id': bom.process_id.id,
#             'unit_price': bom.process_id.unit_price,
#             'mo_type': bom.mo_type,
#             'hour_price': bom.hour_price,
#             'in_charge_id': bom.process_id.partner_id.id
#             # 'procurement_ids': [(6, 0, [self.id])],
#         }
#
#     def _search_suitable_rule(self, domain):
#         """ First find a rule among the ones defined on the procurement order
#         group; then try on the routes defined for the product; finally fallback
#         on the default behavior """
#         if self.warehouse_id:
#             domain = expression.AND([['|', ('warehouse_id', '=', self.warehouse_id.id), ('warehouse_id', '=', False)], domain])
#         Pull = self.env['procurement.rule']
#         res = self.env['procurement.rule']
#         if self.route_ids:
#             res = Pull.search(expression.AND([[('route_id', 'in', self.route_ids.ids)], domain]), order='route_sequence, sequence', limit=1)
#         if not res:
#             product_routes = self.product_id.route_ids | self.product_id.categ_id.total_route_ids
#             if product_routes:
#                 res = Pull.search(expression.AND([[('route_id', 'in', product_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
#         if not res:
#             warehouse_routes = self.warehouse_id.route_ids
#             if warehouse_routes:
#                 res = Pull.search(expression.AND([[('route_id', 'in', warehouse_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
#         if not res:
#             res = Pull.search(expression.AND([[('route_id', '=', False)], domain]), order='sequence', limit=1)
#         return res
#
#     def _find_parent_locations(self):
#         parent_locations = self.env['stock.location']
#         location = self.location_id
#         while location:
#             parent_locations |= location
#             location = location.location_id
#         return parent_locations
#
#
# class linkloving_mrp_product_extend(models.Model):
#     _inherit = "product.product"
#
#     @api.multi
#     def _compute_requirement_qty(self):
#         for product in self:
#             for req in product.mrp_requirement_ids:
#                 if req.state != "done":
#                     product.require_qty += req.required_qty
#     mrp_requirement_ids = fields.One2many("mrp.requirement", "product_id")
#     require_qty = fields.Float(u"需求数量", compute="_compute_requirement_qty")
#
class linkloving_sale_extend(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        self.ensure_one()
        for line in self.order_line:
            if self.env.ref(
                    "mrp.route_warehouse0_manufacture") in line.product_id.route_ids and not line.product_id.bom_ids:
                raise UserError(u"%s 未找到对应的Bom" % line.product_id.display_name)
        return super(linkloving_sale_extend, self).action_confirm()

    def action_cancel(self):
        # if self.state == "sale":
        # 剪掉需求
        # self.order_line.rollback_qty_require()
        return super(linkloving_sale_extend, self).action_cancel()
class linkloving_sale_order_line_extend(models.Model):
    _inherit = "sale.order.line"


    def _search_suitable_rule(self, product_id, domain):
        """ First find a rule among the ones defined on the procurement order
        group; then try on the routes defined for the product; finally fallback
        on the default behavior """
        if self.get_warehouse():
            domain = expression.AND([['|', ('warehouse_id', '=', self.get_warehouse().id), ('warehouse_id', '=', False)], domain])
        Pull = self.env['procurement.rule']
        res = self.env['procurement.rule']
        if product_id.route_ids:
            res = Pull.search(expression.AND([[('route_id', 'in', product_id.route_ids.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            product_routes = product_id.route_ids | product_id.categ_id.total_route_ids
            if product_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', product_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            warehouse_routes = self.get_warehouse().route_ids
            if warehouse_routes:
                res = Pull.search(expression.AND([[('route_id', 'in', warehouse_routes.ids)], domain]), order='route_sequence, sequence', limit=1)
        if not res:
            res = Pull.search(expression.AND([[('route_id', '=', False)], domain]), order='sequence', limit=1)
        return res

    def get_warehouse(self):
        warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1)
        return warehouse_ids

    def _find_parent_locations(self):
        parent_locations = self.env['stock.location']
        location = self.get_warehouse().lot_stock_id
        while location:
            parent_locations |= location
            location = location.location_id
        return parent_locations

    def get_suitable_rule(self, product_id):
        all_parent_location_ids = self._find_parent_locations()
        rule = self._search_suitable_rule(product_id ,[('location_id', 'in', all_parent_location_ids.ids)])
        return rule

    @api.multi
    def rollback_qty_require(self):
        for line in self:
            line.update_po_ordes_mrp_made()

    def update_po_ordes_mrp_made(self):
        if self.order_id:
            pos = self.env["purchase.order"].search([("origin", "ilike", self.order_id.name)])
            for po in pos:#SO2017040301269:MO/2017040322133, SO2017040301271:MO/2017040322137,
                for line in po.order_line:
                    yl_list = self.get_boms()  # 原材料
                    for yl in yl_list:
                        if line.product_id.id == yl.get("product_id").id:
                            # 找到原有的po_line 减掉数量
                            if line.product_qty > yl.get("qty"):
                                po_line = line.write({
                                    'product_qty': line.product_qty - yl.get("qty"),
                                })
                            else:
                                try:
                                    line.unlink()
                                except UserError, e:
                                    raise UserError(u"'%s' 订单中含有产品未设置供应商不能删除" % po.name)

    def get_boms(self):
        self.ensure_one()
        bom = self.env['mrp.bom'].with_context(
                company_id=self.env.user.company_id.id, force_company=self.env.user.company_id.id
        )._bom_find(product=self.product_id)
        boms, lines = bom.explode(self.product_id, self.product_qty, picking_type=bom.picking_type_id)
        yl_list = []

        def recursion_bom(bom_lines, order_line, yl_list):
            for b_line, data in bom_lines:
                child_bom = b_line.child_bom_id
                if b_line.product_id:
                    yl_list.append({"product_id": b_line.product_id, "qty": data.get("qty")})
                if child_bom:
                    boms, lines = child_bom.explode(child_bom.product_id, data.get("qty"),
                                                    picking_type=child_bom.picking_type_id)
                    recursion_bom(lines, order_line, yl_list)

        recursion_bom(lines, self, yl_list)  # 递归bom
        return yl_list

    def get_actual_require_qty(self,product_id, require_qty_this_time):
        actual_need_qty = 0

        rule = self.get_suitable_rule(product_id)

        if rule.action == "manufacture":
            if rule.procure_method == "make_to_order":
                ori_require_qty = product_id.qty_require  # 初始需求数量
                real_require_qty = product_id.qty_require + require_qty_this_time  # 加上本次销售的需求数量
                stock_qty = product_id.qty_available  # 库存数量

                if ori_require_qty > stock_qty and real_require_qty > stock_qty:  # 初始需求 > 库存  并且 现有需求 > 库存
                    actual_need_qty = require_qty_this_time
                elif ori_require_qty <= stock_qty and real_require_qty > stock_qty:
                    actual_need_qty = real_require_qty - stock_qty
            else:
                product_id.is_trigger_by_so = True
                xuqiul = product_id.qty_require + require_qty_this_time
                OrderPoint = self.env['stock.warehouse.orderpoint'].search([("product_id", "=", product_id.id)],
                                                                           limit=1)
                qty = xuqiul + OrderPoint.product_min_qty - product_id.qty_available
                mos = self.env["mrp.production"].search(
                        [("product_id", "=", product_id.id), ("state", "not in", ("cancel", "done"))])
                qty_in_procure = 0
                for mo in mos:
                    qty_in_procure += mo.product_qty
                if qty - qty_in_procure > 0:  # 需求量+最小存货-库存-在产数量
                    actual_need_qty = xuqiul + max(OrderPoint.product_min_qty,
                                                   OrderPoint.product_max_qty) - product_id.qty_available - qty_in_procure

        elif rule.action == "buy":
            xuqiul = product_id.qty_require + require_qty_this_time
            pos = self.env["purchase.order"].search([("state", "=", ("make_by_mrp","draft"))])
            chose_po_lines = self.env["purchase.order.line"]
            total_draft_order_qty = 0
            for po in pos:
                for po_line in po.order_line:
                    if po_line.product_id.id == product_id.id:
                        chose_po_lines += po_line
                        total_draft_order_qty += po_line.product_qty
                        break
            if total_draft_order_qty + product_id.incoming_qty + product_id.qty_available - xuqiul < 0:
                actual_need_qty = xuqiul - (total_draft_order_qty + product_id.incoming_qty + product_id.qty_available)

        return actual_need_qty

#
#     @api.multi
#     def _create_requirement_order(self):
#         ret = []
#         for order_line in self:
#             requiment = self.env["mrp.requirement"].create({
#                     "required_qty" : order_line.product_uom_qty,
#                     "product_id" : order_line.product_id.id,
#                     "orign_order" : order_line.order_id.name,
#                     "state" : "draft",
#                     "location_id" : order_line.order_id.warehouse_id.lot_stock_id.id,
#                     'route_ids': order_line.route_id and [(4, order_line.route_id.id)] or [],
#                     'warehouse_id': order_line.order_id.warehouse_id and order_line.order_id.warehouse_id.id or False,
#                     'partner_dest_id': order_line.order_id.partner_shipping_id.id,
#                     'product_uom': order_line.product_uom.id,
#                     'company_id': order_line.order_id.company_id.id,
#                 })
#             ret.append(requiment)
#
#         return ret