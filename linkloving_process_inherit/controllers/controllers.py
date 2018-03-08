# -*- coding: utf-8 -*-
import json
import logging

import requests
from psycopg2._psycopg import OperationalError

from odoo import http, registry
from odoo.exceptions import UserError
from odoo.http import request
import base64


class LinklovingBomCost(http.Controller):

    @http.route('/linkloving_process_inherit/get_bom_cost', auth='none', type='json', csrf=False)
    def get_report(self):
        print request.jsonrequest

        bom_id = request.jsonrequest.get('bom_id')
        print bom_id
        return request.env["mrp.bom"].sudo().browse(7020).get_bom_cost_new()
