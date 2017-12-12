# -*- coding: utf-8 -*-
import json

import requests
from requests import ConnectionError

from odoo import models, fields, api
from odoo.exceptions import UserError


class ResPartnerExtend(models.Model):
    _inherit = 'res.partner'

    sub_company = fields.Selection(string=u'附属公司类型', selection=[('normal', u'正常'),
                                                                ('sub', u'子公司'),
                                                                ('main', u'下单公司')],
                                   default="normal")
    request_host = fields.Char(string=u'请求地址(包含端口)')
    db_name = fields.Char(string=u'账套名称')


class PurchaseOrderExtend(models.Model):
    _inherit = 'purchase.order'

    def button_confirm(self):
        # todo
        res = super(PurchaseOrderExtend, self).button_confirm()
        if self.partner_id.sub_company == 'sub':
            so_val = self._prepare_so_values()
            self.request_to_create_so(so_val)
        return res

    def request_to_create_so(self, so):
        url = self.partner_id.request_host + '/linkloving_web/create_order'
        db = self.partner_id.db_name
        header = {'Content-Type': 'application/json'}
        try:
            response = requests.post(url, data=json.dumps({
                "db": db,
                "vals": so,
            }), headers=header)
            res_json = json.loads(response.content).get("result")
            if res_json and res_json.get("code") < 0:
                raise UserError(res_json.get("msg"))
            return res_json
        except ConnectionError:
            raise UserError(u"请求地址错误, 请确认")

    def _prepare_so_values(self):
        # if self.order_line.procurement_ids:
        #     origin = ''
        #     for procurement in self.order_line.procurement_ids:
        #         if procurement.move_dest_id and \
        #                 procurement.move_dest_id.procurement_id and \
        #                 procurement.move_dest_id.procurement_id.sale_line_id:
        #             order_id = procurement.move_dest_id.procurement_id.sale_line_id.order_id
        #             origin += order_id.name or '' + ':' + self.name + ":" + order_id.partner_id.name + ', '
        origin_so = self.env["sale.order"].search([("name", "=", self.first_so_number)])
        data = {
            'remark': self.first_so_number or '' + ':' + self.name + ':' + origin_so.partner_id.name or '',
        }
        line_list = []
        for order_line in self.order_line:
            line_list.append({
                "default_code": order_line.product_id.default_code,
                "product_name": order_line.product_id.name,
                "product_uom_qty": order_line.product_qty,
            })
        data["order_line"] = line_list
        return data
