# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    cost = fields.Float(string='BOM成本', compute='_get_bom_cost')

    def get_bom_cost_new(self):
        result = []
        # for line in self.bom_line_ids:
        #     res.append(self.get_bom_line(line))
        if self.product_tmpl_id.product_ll_type:
            product_type_dict = dict(
                self.product_tmpl_id.fields_get(['product_ll_type'])['product_ll_type']['selection'])
        res = {
            'id': self.id,
            'pid': 0,
            'product_id': self.product_tmpl_id.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_specs': self.product_tmpl_id.product_specs,
            'name': self.product_tmpl_id.name_get()[0][1],
            'code': self.product_tmpl_id.default_code,
            'process_id': [self.process_id.id, self.process_id.name],
            'product_type': product_type_dict[self.product_tmpl_id.product_ll_type]
            # 'bom_ids': sorted(res, key=lambda product: product['code']),
        }
        result.append(res)
        if self.bom_line_ids:
            line_ids = []
            for line in self.bom_line_ids:
                line_ids.append(self.get_bom_line(line, result, product_type_dict))
        return result + sorted(line_ids, key=lambda product: product['has_lines'])

    def get_bom_line(self, line, result, product_type_dict):
        if line.child_line_ids:

            for l in line.child_line_ids:
                _get_rec(l, line, result, product_type_dict)

        bom_id = line.product_id.product_tmpl_id.bom_ids
        action = line.action_id

        process_id = action_id = []
        if bom_id:
            process_id = bom_id[0].process_id.name
        if action:
            action_id = action_id.name

        res = {
            'name': line.product_id.name_get()[0][1],
            'product_type': product_type_dict[line.product_id.product_ll_type],
            'product_id': line.product_id.id,
            'product_tmpl_id': line.product_id.product_tmpl_id.id,
            'id': line.id,
            'has_lines': 0 if line.child_line_ids else 1,
            'pid': line.bom_id.id,
            'product_specs': line.product_id.product_specs,
            'code': line.product_id.default_code,
            'qty': line.product_qty,
            'process_id': process_id,
            'process_action': action_id,
        }

        return res

    @api.multi
    def _get_bom_cost(self):
        for bom in self:
            bom.cost = sum(line.cost for line in bom.bom_line_ids)


def _get_rec(object, parnet, result, product_type_dict):
    for l in object:
        if l.child_line_ids:
            for line in l.child_line_ids:
                _get_rec(line, l, result, product_type_dict)

        bom_id = l.product_id.product_tmpl_id.bom_ids
        process_id = []
        if bom_id:
            process_id = [bom_id[0].process_id.id, bom_id[0].process_id.name]

        res = {
            'name': l.product_id.name_get()[0][1],
            'product_id': l.product_id.id,
            'product_type': product_type_dict[l.product_id.product_ll_type],
            'product_tmpl_id': l.product_id.product_tmpl_id.id,
            'code': l.product_id.default_code,
            'product_specs': l.product_id.product_specs,
            # 'is_highlight': l.is_highlight,
            # 'product_type': l.product_id.product_ll_type,
            'id': l.id,
            'pid': parnet.id,
            'material_cost': '',
            'manpower_cost': '',
            'parent_id': parnet.id,
            'qty': l.product_qty,
            'process_id': process_id,
            # 'bom_ids': bom_line_ids
        }
        result.append(res)

    return res


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'
    action_id = fields.Many2one('mrp.process.action')
    cost = fields.Float(string=u'动作成本', related='action_id.cost')
    sub_total_cost = fields.Float(compute='_get_sub_total_cost')

    @api.multi
    def _get_sub_total_cost(self):
        for line in self:
            line.sub_total_cost = line.cost * line.product_qty

    @api.one
    def get_action_options(self):
        domain = []
        if self.bom_id.process_id:
            domain = [('process_id', '=', self.bom_id.process_id.id)]
        res = []
        actions = self.env['mrp.process.action'].search(domain)
        for action in actions:
            res.append({
                'id': action.id,
                'name': action.name
            })
        return res
