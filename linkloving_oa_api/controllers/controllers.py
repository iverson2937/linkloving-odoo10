# -*- coding: utf-8 -*-
import base64
import json
import logging
from urllib2 import URLError

import time

import operator

import datetime

import jpush
import pytz
from pip import download

import odoo
import odoo.modules.registry

from odoo import fields
from odoo.osv import expression
from odoo.tools import float_compare, SUPERUSER_ID, werkzeug, os, safe_eval
from odoo.tools.translate import _
from odoo import http
from odoo.http import content_disposition, dispatch_rpc, request, \
                      serialize_exception as _serialize_exception
from odoo.exceptions import AccessError, UserError


STATUS_CODE_OK = 1
STATUS_CODE_ERROR = -1

#返回的json 封装
class JsonResponse(object):
    @classmethod
    def send_response(cls, res_code, res_msg='', res_data=None, jsonRequest=True):
        data_dic = {'res_code': res_code,
                    'res_msg': res_msg,}
        if res_data:
            data_dic['res_data'] = res_data
        if jsonRequest:
            return data_dic
        return json.dumps(data_dic)

class LinklovingOAApi(http.Controller):
    #供应商查询
    @http.route('/linkloving_oa_api/search_supplier', type='json', auth="none", csrf=False, cors='*')
    def search_supplier(self, **kw):
        name = request.jsonrequest.get("name")
        search_supplier_results = request.env['res.partner'].sudo().search([("name",'ilike',name),('supplier', '=', True), ("is_company", '=', True)],
                                                                           limit=10,
                                                                           offset=0,
                                                                           order='id desc')
        json_list = []
        for feedback in search_supplier_results:
            json_list.append(self.supplier_feedback_to_json(feedback))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    # 获取供应商
    @http.route('/linkloving_oa_api/get_supplier', type='json', auth="none", csrf=False, cors='*')
    def get_supplier(self, **kw):
        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        if request.jsonrequest.get("id"):
            supplier_detail_object = request.env['res.partner'].sudo().browse(request.jsonrequest.get("id"))
            return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.supplier_detail_object_to_json(supplier_detail_object))

        feedbacks = request.env['res.partner'].sudo().search([('supplier', '=', True), ("is_company", '=', True)],
                                                             limit=limit,
                                                             offset=offset,
                                                             order='id desc')
        json_list = []
        for feedback in feedbacks:
            json_list.append(self.supplier_feedback_to_json(feedback))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def get_supplier_tags(self,objs):
        data = []
        for obj in objs:
            data.append(obj.display_name)
        return data

    def supplier_detail_object_to_json(self, supplier_detail_object):
        supplier_details = {
            "name": supplier_detail_object.name,
            "phone": supplier_detail_object.phone,
            "street": self.get_supplier_address(supplier_detail_object),
            "email": supplier_detail_object.email or '',
            "website": supplier_detail_object.website or '',
            "express_sample_record": supplier_detail_object.express_sample_record or '',
            "lang": supplier_detail_object.lang,
            "contracts_count": len(supplier_detail_object.child_ids),  #联系人&地址个数
            "contracts": self.get_contracts_in_supplier(supplier_detail_object.child_ids),
            'category': self.get_supplier_tags(supplier_detail_object.category_id),
            "purchase_order_count": supplier_detail_object.purchase_order_count,  #订单数量
            "invoice": supplier_detail_object.supplier_invoice_count,  #对账
            "payment_count": supplier_detail_object.payment_count,   #付款申请
            "put_in_storage": request.env['stock.picking'].sudo().search_count([('partner_id', '=', request.jsonrequest.get("id")),('state','=','waiting_in')]),   #入库
        }
        return supplier_details

    def get_supplier_address(self,obj):
        data = []
        data.append({
            'continent': (obj.continent.display_name or '') + (obj.country_id.display_name or '') + (obj.state_id.name or '') + (obj.city or '') + (obj.street2 or '') + (obj.street or ''),
        })
        return data


    def get_contracts_in_supplier(self, objs):
        json_lists = []

        for obj in objs:
            json_lists.append({
                "name": obj.name,
                "phone": obj.phone,
                "email": obj.email,
                "street": obj.street2,
                "type": LinklovingOAApi.selection_get_map("res.partner", "type", obj.type),
            })
        return json_lists
    #英文对应的中文一起传回
    @classmethod
    def selection_get_map(cls, res_model, field, value):
        field_detail = request.env[res_model].sudo().fields_get([field])
        for f in field_detail[field].get("selection"):
            if f[0] == value:
                return f
            else:
                continue
        return (value, value)

    def supplier_feedback_to_json(self, feedback):
        data = {
            'internal_code': feedback.internal_code or '',
            'city': feedback.city or '',
            'company_name': feedback.commercial_company_name or '',
            'email': feedback.email or '',
            'phone': feedback.mobile or feedback.phone or '',
            'id': feedback.id or ''
        }
        return data

    #获取采购订单
    @http.route('/linkloving_oa_api/get_po', type='json', auth="none", csrf=False, cors='*')
    def get_po(self, **kw):
        #判断若传入了id则表示是要获取详细的orderlines
        if(request.jsonrequest.get("id")):
            po_detail_object = request.env['purchase.order'].sudo().browse(request.jsonrequest.get("id"))

            po_order_detail = {}
            po_order_detail['id'] = request.jsonrequest.get("id")
            po_order_detail['supplier'] = po_detail_object.partner_id.display_name
            po_order_detail['name'] = po_detail_object.name
            po_order_detail['data_order'] = po_detail_object.date_order   #单据日期
            po_order_detail['handle_date'] = po_detail_object.handle_date  #交期
            po_order_detail['tax'] = {
                'tax_id':po_detail_object.tax_id.name or ''
            }
            po_order_detail['currency'] = {
                'currency_name':po_detail_object.currency_id.name,
            }  #币种
            po_order_detail['amount_untaxed'] = po_detail_object.amount_untaxed  # 未含税金额
            po_order_detail['amount_tax'] = po_detail_object.amount_tax  # 税金
            po_order_detail['amount_total'] = po_detail_object.amount_total  # 总计
            po_order_detail['product_count'] = po_detail_object.product_count  # 总数量
            po_order_detail['notes'] = po_detail_object.notes
            po_order_detail["origin"] = po_detail_object.origin #源单据
            #交货及发票
            po_order_detail['date_planned'] = po_detail_object.date_planned  #安排的日期
            po_order_detail['stock_to'] = po_detail_object.picking_type_id.display_name  #交货到
            po_order_detail['incoterm_id'] = po_detail_object.incoterm_id.display_name or ''  # 贸易术语
            po_order_detail['invoice_status'] = LinklovingOAApi.selection_get_map("purchase.order", 'invoice_status', po_detail_object.invoice_status),  #账单状态
            po_order_detail['payment_term'] = po_detail_object.payment_term_id.display_name  # 付款条款
            po_order_detail['fiscal_position'] = po_detail_object.fiscal_position_id.display_name  # 财政状况

            po_order_detail['order_lines'] = []
            po_order_lines = po_detail_object.order_line
            for order_line in po_order_lines:
                po_order_detail['order_lines'].append(
                    {'name': order_line.product_id.name_get()[0][1],
                     'product_uom': order_line.product_uom.name,
                     'specs': order_line.product_id.product_specs,  #规格
                     'price_unit': order_line.price_unit,   #单价
                     'product_qty': order_line.product_qty,   #数量
                     'price_subtotal': order_line.price_subtotal,  #小计
                     'qty_invoiced': order_line.qty_invoiced,  #开单数量
                     'qty_received': order_line.qty_received,  #已接收数量
                     'price_tax': order_line.taxes_id.name,    #税金
                     }
                )
            return JsonResponse.send_response(STATUS_CODE_OK, res_data=po_order_detail)

        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        state = request.jsonrequest.get("state")
        domain = [('state', '=', state)]
        if state == 'purchase':
            domain = [('state', 'in', ('to approval','done','purchase'))]
        PO_orders = request.env['purchase.order'].sudo().search(domain,
                                                                limit=limit,
                                                                offset=offset,
                                                                order='id desc')
        json_list = []
        for po_order in PO_orders:
            json_list.append(self.po_order_to_json(po_order))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def po_order_to_json(self, po_order):
        data = {
            'id': po_order.id,
            'name': po_order.name,
            'order_line': po_order.order_line[0].product_id.display_name if po_order.order_line else '',
            'creater': po_order.create_uid.name,
            'supplier': po_order.partner_id.commercial_company_name or '',
            'status_light': po_order.status_light,
            'product_count': po_order.amount_total, #总数量
            'amount_total': po_order.product_count  #总金额
        }
        return data

    #采购退货
    @http.route('/linkloving_oa_api/get_prma', type='json', auth="none", csrf=False, cors='*')
    def get_prma(self, *kw):
        # 若传入id则获取详情
        if request.jsonrequest.get("id"):
            prma_detail_object = request.env['return.goods'].sudo().browse(request.jsonrequest.get("id"))
            return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.prma_detail_object_to_json(prma_detail_object))

        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        prma_lists = request.env['return.goods'].sudo().search([],
                                                               limit=limit,
                                                               offset=offset,
                                                               order='id desc')
        json_list = []
        for prma_list in prma_lists:
            json_list.append(self.prma_list_to_json(prma_list))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def prma_detail_object_to_json(self, prma_detail_object):
        prma_detail = {
            "name": prma_detail_object.name,
            "supplier": prma_detail_object.partner_id.display_name,
            "partner_invoice_add": prma_detail_object.partner_invoice_id.display_name,  #开票地址
            "partner_shipping_add": prma_detail_object.partner_shipping_id.display_name,  # 退货地址
            "refer_po": prma_detail_object.purchase_id.name,  # 参考订单号
            "refer_po_amount_total": prma_detail_object.purchase_id.amount_total,  # 参考订单号的总金额
            "tracking_number": prma_detail_object.tracking_number or '',  # 物流信息
            "remark": prma_detail_object.remark,  # 退货原因
            "date": prma_detail_object.date,  # 退货日期
            "tax": prma_detail_object.tax_id.display_name or '',
            "amount_untaxed": prma_detail_object.amount_untaxed,  #未含税金额
            "amount_tax": prma_detail_object.amount_tax,  # 税金
            "amount_total": prma_detail_object.amount_total,   #总计
            "prma_line_products": self.prma_line_products_parse(prma_detail_object.line_ids)
        }
        return prma_detail
    #具体的退货产品
    def prma_line_products_parse(self,objs):
        data = []
        for obj in objs:
            data.append({
                "name": obj.product_id.display_name,
                "uom": obj.product_uom.name,
                "invoice_status": LinklovingOAApi.selection_get_map("return.goods.line", 'invoice_status', obj.invoice_status),
                "product_uom_qty": obj.product_uom_qty, #退货数量
                "qty_delivered": obj.qty_delivered, #收到数量
                "price_unit": obj.price_unit, #单价
                "price_subtotal": obj.price_subtotal,  #小计
                "qty_to_invoice": obj.qty_to_invoice,  #待对账数量
            })
        return data

    def prma_list_to_json(self,prma_list):
        data = {
            'id': prma_list.id,
            'name': prma_list.name,
            'date': prma_list.date,
            'supplier': prma_list.partner_id.display_name,
            'remark': prma_list.remark,
            'amount_total': prma_list.amount_total
        }
        return data

    #订单搜索
    @http.route('/linkloving_oa_api/search_purchase_order', type='json', auth="none", csrf=False, cors='*')
    def search_purchase_order(self, *kw):
        model = request.jsonrequest.get("model")
        name = request.jsonrequest.get("po_number")
        search_supplier_results = request.env[model].sudo().search(
            [("name", 'ilike', name)],
            limit=10,
            offset=0,
            order='id desc')
        json_list = []
        for feedback in search_supplier_results:
            if model == 'purchase.order':
                json_list.append(self.search_po_feedback_to_json(feedback))
            else:
                json_list.append(self.prma_list_to_json(feedback))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def search_po_feedback_to_json(self, feedback):
        data = {
            'name': feedback.name,
            'supplier': feedback.partner_id.display_name,
            'product_count': feedback.amount_total, #总数量
            'amount_total': feedback.product_count if feedback.product_count else '',  #总金额
            'product': feedback.product_id.display_name,
            'state': LinklovingOAApi.selection_get_map("purchase.order", "state", feedback.state),
            'create': feedback.create_uid.display_name
        }
        return data

    # def search_prma_feedback_to_json(self, feedback):
    #     data = {
    #         'name': feedback.name,
    #         'supplier': feedback.partner_id.display_name,
    #         'date': feedback.date,
    #         'state': LinklovingOAApi.selection_get_map("return.goods", "state", feedback.state),
    #         'remark': feedback.remark
    #     }
    #     return data


    # 送货单详情页
    # 若是采购退货，除了id还要传一个prma  值随意
    @http.route('/linkloving_oa_api/get_delivery_notes', type='json', auth="none", csrf=False, cors='*')
    def get_delivery_notes(self, *kw):
        if request.jsonrequest.get("prma"):
            delivery_notes = request.env['return.goods'].sudo().browse(request.jsonrequest.get("id"))
        else:
            delivery_notes = request.env['purchase.order'].sudo().browse(request.jsonrequest.get("id"))
        json_list = []
        for obj in delivery_notes.picking_ids:
            json_list.append(self.get_delivery_notes_details(obj))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def get_delivery_notes_details(self, obj):
        return {
            'id': obj.id,
            'name': obj.name,
            'partner': obj.partner_id.display_name,  #合作伙伴
            'location_id': obj.location_id.display_name,  #源位置区域
            'tracking_number': obj.tracking_number or '',  #快递单号
            'is_emergency': obj.is_emergency,   #加急
            'min_date': obj.min_date,  #安排的日期
            'origin': obj.origin,   #源单据
            'state': LinklovingOAApi.selection_get_map("stock.picking", "state", obj.state),
            'creater': obj.create_uid.display_name,
            'backorder': obj.backorder_id.display_name or '',  #欠单于
            'move_type': LinklovingOAApi.selection_get_map("stock.picking", "move_type", obj.move_type),  #交货类型
            'picking_type': obj.picking_type_id.display_name,  #分拣类型
            'group': obj.group_id.display_name,  #补货组
            'priority': LinklovingOAApi.selection_get_map("stock.picking", "priority", obj.priority),  #优先级
            'carrier': obj.carrier_id.display_name or '',  #承运商
            'carrier_tracking_ref': obj.carrier_tracking_ref or '',  #跟踪参考
            'weight': obj.weight,  #重量
            'shipping_weight': obj.shipping_weight,  #航运重量
            'number_of_packages': obj.number_of_packages,  #包裹件数
            'products': self.delivery_notes_products(obj.pack_operation_product_ids)
        }

    def delivery_notes_products(self, objs):
        data = []
        for obj in objs:
            data.append({
                'product_name': obj.product_id.display_name,
                'uom': obj.product_uom_id.name, #计量单位
                'to_loc': obj.to_loc,  #至
                'from_loc': obj.from_loc,   #从
                'ordered_qty': obj.ordered_qty,  #待办
                'qty_done': obj.qty_done,  #完成
            })
        return data

    # 送货单详情页-初始需求
    @http.route('/linkloving_oa_api/get_delivery_notes_initial_requ', type='json', auth="none", csrf=False, cors='*')
    def get_delivery_notes_initial_requ(self, *kw):
        initial_requs = request.env['stock.picking'].sudo().browse(request.jsonrequest.get("id"))
        json_list = []
        for obj in initial_requs.move_lines:
            json_list.append(self.get_dnir_details(obj))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def get_dnir_details(self, obj):
        return {
            'name': obj.name,
            'amount': obj.product_uom_qty,
            'uom': obj.product_uom.display_name,
            'state': LinklovingOAApi.selection_get_map("stock.picking", "state", obj.state),  #优先级
        }

    #联系电话
    @http.route('/linkloving_oa_api/get_contact_phone_number', type='json', auth="none", csrf=False, cors='*')
    def get_contact_phone_number(self, *kw):
        model = request.jsonrequest.get("model")
        po_object = request.env[model].sudo().browse(request.jsonrequest.get("id"))
        json_list = {
            "supplier": [{"name": po_object.partner_id.display_name, "phone": po_object.partner_id.phone}],
            "creater": [{"name": po_object.create_uid.name, "phone": po_object.create_uid.mobile or po_object.create_uid.phone or ''}],
        }
        json_list.update(self.get_all_phone_numbers())
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def get_all_phone_numbers(self):
        request.uid = SUPERUSER_ID
        pj_users = request.env.ref("linkloving_mrp_extend.group_charge_inspection").users
        ck_users = request.env.ref("linkloving_mrp_extend.group_charge_warehouse").users
        sc_users = request.env.ref("linkloving_mrp_extend.group_charge_produce").users
        data = {}
        data["pj"] = []
        data["ck"] = []
        data['sc'] = []
        for user in pj_users:
            data["pj"].append({
                'name': user.name,
                'phone': user.employee_ids[0].mobile_phone or '' if user.employee_ids else ''
            })
        for user in ck_users:
            data["ck"].append({
                'name': user.name,
                'phone': user.employee_ids[0].mobile_phone or '' if user.employee_ids else ''
            })
        for user in sc_users:
            data["sc"].append({
                'name': user.name,
                'phone': user.employee_ids[0].mobile_phone or '' if user.employee_ids else ''
            })
        return data

    #对账-付款申请
    @http.route('/linkloving_oa_api/get_account_checking_lists_tab1', type='json', auth="none", csrf=False, cors='*')
    def get_account_checking_lists_tab1(self, *kw):
        #若传入了id  获取详情页
        if(request.jsonrequest.get("id")):
            payment_request_detail_object = request.env['account.payment.register'].sudo().browse(request.jsonrequest.get("id"))
            return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.payment_request_detail_object_parse(payment_request_detail_object))

        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        payment_request_lists = request.env['account.payment.register'].sudo().search([('payment_type','=','1')],
                                                                                      limit=limit,
                                                                                      offset=offset,
                                                                                      order='id desc')
        json_list = []
        for payment_request_list in payment_request_lists:
            json_list.append(self.payment_request_list_to_json(payment_request_list))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def payment_request_list_to_json(self, obj):
        data = {
            'name': obj.name,
            'create_date': obj.create_date,
            'amount': obj.amount,
            'partner_name': obj.partner_id.display_name,
            'creater': obj.create_uid.display_name,
            'remark': obj.remark or '',
            'state': LinklovingOAApi.selection_get_map("account.payment.register", "state", obj.state),
            'id': obj.id
        }
        return data

    def payment_request_detail_object_parse(self,obj):
        return {
            'name': obj.name,
            'supplier': obj.partner_id.display_name,
            'bank': obj.bank_id.display_name,
            'amount': obj.amount,
            'receive_date': obj.receive_date,
            'remark': obj.remark or '',
            'supplier_account_check': self.get_supplier_account_check(obj.invoice_ids)
        }

    def get_supplier_account_check(self, objs):
        data = []
        for obj in objs:
            data.append({
                'supplier': obj.partner_id.display_name,
                'number': obj.number,
                'date_invoice': obj.date_invoice, #开票日期
                'date_due': obj.date_due or '',  #截止日期
                'remain_apply_balance': obj.remain_apply_balance,  #待申请付款金额
                'name': obj.name,
                'residual': obj.residual,   #待支付
                'amount_total': obj.amount_total, #总计
                'state': LinklovingOAApi.selection_get_map("account.invoice", "state", obj.state)
            })
        return data

    # 对账-供应商账单、退货对账单
    @http.route('/linkloving_oa_api/get_account_checking_lists_tab2', type='json', auth="none", csrf=False, cors='*')
    def get_account_checking_lists_tab2(self, *kw):
        #若传入了id  则获取详情页
        if request.jsonrequest.get("id"):
            bill_detail_object = request.env['account.invoice'].sudo().browse(request.jsonrequest.get("id"))
            return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.bill_detail_object_parse(bill_detail_object))

        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        type = request.jsonrequest.get("type")     #供应商账单in_invoice   退货对账单in_refund
        bill_lists = request.env['account.invoice'].sudo().search([('type', '=', type)],
                                                                  limit=limit,
                                                                  offset=offset,
                                                                  order='id desc')
        json_list = []
        for bill_list in bill_lists:
            json_list.append(self.bill_list_to_json(bill_list))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=json_list)

    def bill_detail_object_parse(self, obj):
        return {
            'supllier': obj.partner_id.display_name,   #供应商
            'deduct_amount': obj.deduct_amount,  #扣款
            'po': obj.po_id.display_name,  #采购单
            'origin': obj.origin,   #源单据
            'amount_untaxed': obj.amount_untaxed,  #未含税金额
            'amount_tax': obj.amount_tax,  #税金
            'amount_total': obj.amount_tax,  #总计
            'date_invoice': obj.date_invoice or '',  #账单日期
            'date_due': obj.date_due or '',     #截止日期
            'reference': obj.reference or '',   #供应商参考
            'payments': self.get_payment_ids(obj.payment_ids) or '',   #付款申请单
            'remark': obj.remark or '',  #备注
            'currency': obj.currency_id.name,  #币种
            # 'payments_widget': obj.payments_widget if obj.payments_widget else '',  #已付金额
            'residual': obj.residual if obj.residual is not None else '',   #截止金额
            'bill_detail_lists': self.get_bill_detail_lists(obj.invoice_line_ids)
        }

    def get_payment_ids(self, objs):
        data = []
        for obj in objs:
            data.append(obj.name)
        return data

    def get_bill_detail_lists(self, objs):
        data = []
        for obj in objs:
            data.append({
                'id': obj.id,
                'product': obj.product_id.display_name,  #产品
                'explain': obj.name,  #说明
                'price_unit': obj.price_unit,  #单价
                'price_unit_o': obj.price_unit_o,    #original price
                'uom': obj.uom_id.display_name,
                'subject': obj.account_id.display_name,  #科目
                'quantity': obj.quantity,
                'price_subtotal': obj.price_subtotal,  #金额
                'tax': obj.invoice_line_tax_ids.name,   #税金
            })
        return data

    def bill_list_to_json(self, obj):
        data = {
            'client': obj.partner_id.display_name,
            'date_invoice': obj.date_invoice or '',
            'number': obj.number,
            'date_due': obj.date_due or '',
            # 'commercial_partner': obj.commercial_partner_id.display_name,
            'state': LinklovingOAApi.selection_get_map("account.invoice", "state", obj.state),
            'origin': obj.origin or '',
            'residual_signed': obj.residual_signed,    #待支付
            'amount_total_signed': obj.amount_total_signed,    #总计
            'remain_apply_balance': obj.remain_apply_balance,  #待申请付款金额
            'id': obj.id
        }
        return data

    # 对账-order lines
    @http.route('/linkloving_oa_api/get_order_lines', type='json', auth="none", csrf=False, cors='*')
    def get_order_lines(self, *kw):
        Order_Lines = request.env['account.invoice'].sudo().browse(request.jsonrequest.get("id"))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.get_account_checking_order_line(Order_Lines.order_line))

    def get_account_checking_order_line(self, objs):
        data = []
        for obj in objs:
            data.append({
                'explain': obj.name,  #说明
                'supplier': obj.partner_id.display_name,
                'order': obj.order_id.display_name,   #订单关联
                'product': obj.product_id.display_name,   #产品
                'price_unit': obj.price_unit,  #单价
                'product_qty': obj.product_qty,  #数量
                'price_total': obj.price_total,   #小计
                'date_planned': obj.date_planned,
                'uom': obj.product_uom.name
            })
        return data

    # 对账-其他信息  税说明
    @http.route('/linkloving_oa_api/get_account_checking_order_lines', type='json', auth="none", csrf=False, cors='*')
    def get_account_checking_order_lines(self, *kw):
        Data_Object = request.env['account.invoice'].sudo().browse(request.jsonrequest.get("id"))
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=self.get_account_checking_more_message(Data_Object))

    def get_account_checking_more_message(self, obj):
        return {
            'journal': obj.journal_id.display_name,
            'user': obj.user_id.display_name,
            'account': obj.account_id.display_name,  #科目
            'fiscal': obj.fiscal_position_id.display_name or '',
            'date': obj.date or '',
            'tax_lines': self.get_account_checking_taxs(obj.tax_line_ids)
        }

    def get_account_checking_taxs(self, objs):
        data = []
        for obj in objs:
            data.append({
                'explain': obj.display_name,
                'amount': obj.amount,
                'account': obj.account_id.display_name
            })
        return data


    #-----------销售部分-----------#
    # 线索
    @http.route('/linkloving_oa_api/get_clues', type='json', auth="none", csrf=False, cors='*')
    def get_clues(self, *kw):
        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        user_id = request.jsonrequest.get("user_id")
        clues = request.env['crm.lead'].sudo().search([('type', '=', 'lead' or False),('user_id','=',user_id)],
                                                        limit=limit,
                                                        offset=offset,
                                                        order='id desc')
        data = []
        for clue in clues:
            data.append({
                'name': clue.name,
                'contact_name': clue.contact_name or '',
                'team': clue.team_id.display_name,
                'user': clue.user_id.display_name,
                'category': self.get_supplier_tags(clue.partner_id.category_id),
                'priority': clue.priority,
            })
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=data)

    # 客户（客户，潜在客户，公海客户）
    @http.route('/linkloving_oa_api/get_customers', type='json', auth="user", csrf=False, cors='*')
    def get_customers(self, *kw):
        limit = request.jsonrequest.get("limit")
        offset = request.jsonrequest.get("offset")
        user_id = request.jsonrequest.get("user_id")
        domain = [('customer', '=', '1'), ('is_company', '=', True), ('user_id','=',user_id)]
        if request.jsonrequest.get("is_order"):
            if request.jsonrequest.get("is_order") == 'False':
                domain.append(('is_order','=',False))
            else:
                domain.append(('is_order', '=', True))
        if request.jsonrequest.get("public_partners"):
            if request.jsonrequest.get("public_partners") == '!=':      #public值 !=或=
                domain.append(('public_partners', '!=', 'public'))
            else:
                domain.append(('public_partners', '=', 'public'))

        print domain
        customers = request.env['res.partner'].search(domain,
                                                      limit=limit,
                                                      offset=offset,
                                                      order='id desc')
        data = []
        for customer in customers:
            data.append({
                'name': customer.display_name,
                'team': customer.team_id.display_name,
                'user': customer.user_id.display_name,
                'category': self.get_supplier_tags(customer.category_id),
                'priority': customer.priority,
                'level': customer.level
            })
        return JsonResponse.send_response(STATUS_CODE_OK, res_data=data)

    #订单
    @http.route('/linkloving_oa_api/get_purchase_orders', type='json', auth="user", csrf=False, cors='*')
    def get_purchase_orders(self, *kw):
        pass
