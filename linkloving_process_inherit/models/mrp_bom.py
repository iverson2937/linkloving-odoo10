# -*- coding: utf-8 -*-

from odoo import models, fields, api


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    manpower_cost = fields.Float(string='工序动作成本', compute='_get_bom_cost')

    def _get_product_type_dict(self):
        return dict(
            self.product_tmpl_id.fields_get(['product_ll_type'])['product_ll_type']['selection'])

    def get_default_bom_cost(self):
        result = []

        if self.product_tmpl_id.product_ll_type:
            product_type_dict = self._get_product_type_dict()
        total_cost = self.product_tmpl_id.product_variant_ids[0].pre_cost_cal_new(raise_exception=False)

        man_cost = self.product_tmpl_id.product_variant_ids[0].get_pure_manpower_cost()
        material_cost = total_cost - man_cost
        res = {
            'id': 1,
            'pid': 0,
            'bom_id': self.id,
            'product_id': self.product_tmpl_id.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_specs': self.product_tmpl_id.product_specs,
            'name': self.product_tmpl_id.name_get()[0][1],
            'code': self.product_tmpl_id.default_code,
            'process_id': [self.process_id.id, self.process_id.name],
            'product_type': product_type_dict[self.product_tmpl_id.product_ll_type],
            # 'bom_ids': sorted(res, key=lambda product: product['code']),
        }
        result.append(res)
        if self.bom_line_ids:
            line_ids = []
            for line in self.bom_line_ids:
                line_ids.append(self.get_bom_line_default(self.product_templ_id.categ_id.id, self.id, line, result,
                                                          product_type_dict))
        return result + sorted(line_ids, key=lambda product: product['code'], reverse=True)

    def get_product_action_default(self, categ_id, p_product_id):
        res = {}
        domain = [('categ_id', '=', categ_id),
                  ('p_product_id', '=', p_product_id)('product_id', '=', self.product_id.id)]

        temp_id = self.env['bom.cost.category.temp'].search([domain])
        if temp_id:
            res.update({
                'action_id_1': temp_id.action_id_1.id,
                'action_id_1': temp_id.action_id_1.id,
                'rate1': temp_id.rate1,
                'rate2': temp_id.rate2,
            })
        return res

    def get_bom_line_default(self, categ_id, root_bom_id, line, result, product_type_dict):
        '''
        根据系列获取默认值
        :param categ_id:
        :param root_bom_id:
        :param line:
        :param result:
        :param product_type_dict:
        :return:
        '''
        if line.child_line_ids:

            for l in line.child_line_ids:
                _get_rec_default(categ_id, root_bom_id, l, line, result, product_type_dict)

        bom_id = line.product_id.product_tmpl_id.bom_ids

        process_id = []
        if bom_id:
            process_id = bom_id[0].process_id.name
        product_cost = line.product_id.pre_cost_cal_new(raise_exception=False)
        line_cost = product_cost if product_cost else 0
        # material_cost = line_cost * line.product_qty
        # man_cost = line.action_id.cost * line.product_qty if line.action_id else 0
        # total_cost = material_cost + man_cost
        temp_date = line.get_product_action_default(categ_id, root_bom_id)
        res = {
            'name': line.product_id.name_get()[0][1],
            'product_type': product_type_dict[line.product_id.product_ll_type],
            'product_id': line.product_id.id,
            'product_tmpl_id': line.product_id.product_tmpl_id.id,
            'id': line.id,
            'has_lines': 0 if line.child_line_ids else 1,
            'pid': 1,
            'product_specs': line.product_id.product_specs,
            'code': line.product_id.default_code,
            'qty': line.product_qty,
            # 'material_cost': round(material_cost, 2),
            # 'manpower_cost': round(man_cost, 2),
            # 'total_cost': round(total_cost, 2),
            'process_id': process_id,
            'process_action': [
                {
                    'action_id': 12,
                    'action_name': '包装',
                    'rate': 1
                }
            ],

        }
        return res

    def get_bom_cost_new(self):
        result = []

        if self.product_tmpl_id.product_ll_type:
            product_type_dict = self._get_product_type_dict()
        total_cost = self.product_tmpl_id.product_variant_ids[0].pre_cost_cal_new(raise_exception=False)

        man_cost = self.product_tmpl_id.product_variant_ids[0].get_pure_manpower_cost()
        material_cost = total_cost - man_cost
        res = {
            'id': 1,
            'pid': 0,
            'bom_id': self.id,
            'product_id': self.product_tmpl_id.id,
            'product_tmpl_id': self.product_tmpl_id.id,
            'product_specs': self.product_tmpl_id.product_specs,
            'name': self.product_tmpl_id.name_get()[0][1],
            'code': self.product_tmpl_id.default_code,
            'process_id': [self.process_id.id, self.process_id.name],
            'product_type': product_type_dict[self.product_tmpl_id.product_ll_type],
            'material_cost': round(material_cost, 2),
            'manpower_cost': round(man_cost, 2),
            'total_cost': round(total_cost, 2),
            # 'bom_ids': sorted(res, key=lambda product: product['code']),
        }
        result.append(res)
        if self.bom_line_ids:
            line_ids = []
            for line in self.bom_line_ids:
                line_ids.append(self.get_bom_line_new(line, result, product_type_dict))
        return result + sorted(line_ids, key=lambda product: product['code'], reverse=True)

    def get_bom_line_new(self, line, result, product_type_dict):
        if line.child_line_ids:

            for l in line.child_line_ids:
                _get_rec(l, line, result, product_type_dict)

        bom_id = line.product_id.product_tmpl_id.bom_ids

        process_id = []
        if bom_id:
            process_id = bom_id[0].process_id.name
        product_cost = line.product_id.pre_cost_cal_new(raise_exception=False)
        line_cost = product_cost if product_cost else 0
        # material_cost = line_cost * line.product_qty
        # man_cost = line.action_id.cost * line.product_qty if line.action_id else 0
        # total_cost = material_cost + man_cost

        res = {
            'name': line.product_id.name_get()[0][1],
            'product_type': product_type_dict[line.product_id.product_ll_type],
            'product_id': line.product_id.id,
            'product_tmpl_id': line.product_id.product_tmpl_id.id,
            'id': line.id,
            'has_lines': 0 if line.child_line_ids else 1,
            'pid': 1,
            'product_specs': line.product_id.product_specs,
            'code': line.product_id.default_code,
            'qty': line.product_qty,
            # 'material_cost': round(material_cost, 2),
            # 'manpower_cost': round(man_cost, 2),
            # 'total_cost': round(total_cost, 2),
            'process_id': process_id,
            'process_action': [
                {
                    'action_id': 12,
                    'action_name': '包装',
                    'rate': 1
                }
            ]
        }

        return res

    @api.multi
    def _get_bom_cost(self):
        for bom in self:
            bom.manpower_cost = 0
            # bom.manpower_cost = sum(line.cost for line in bom.bom_line_ids)


def _get_rec_default(categ_id, object, parnet, result, product_type_dict):
    for l in object:
        if l.child_line_ids:
            for line in l.child_line_ids:
                _get_rec_default(categ_id, line, l, result, product_type_dict)

        bom_id = l.product_id.product_tmpl_id.bom_ids
        process_id = []
        if bom_id:
            process_id = [bom_id[0].process_id.id, bom_id[0].process_id.name]

        product_cost = object.product_id.pre_cost_cal_new(raise_exception=False)
        line_cost = product_cost if product_cost else 0
        material_cost = line_cost * object.product_qty
        # man_cost = l.action_id.cost if l.action_id else 0
        # total_cost = material_cost + man_cost
        temp_date = object.get_product_action_default(categ_id, parnet.id)
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
            'process_action_1': temp_date.get('action_id_1'),
            'process_action_2': temp_date.get('action_id_2'),
            'action_rate2': temp_date.get('rate1'),
            'action_rate1': temp_date.get('rate12'),

            'material_cost': round(material_cost, 2),
            # 'manpower_cost': round(man_cost, 2),
            # 'total_cost': round(total_cost, 2),
            'parent_id': parnet.id,
            'qty': l.product_qty,
            'process_id': process_id,
        }
        result.append(res)

    return res


def _get_rec(object, parnet, result, product_type_dict):
    for l in object:
        if l.child_line_ids:
            for line in l.child_line_ids:
                _get_rec(line, l, result, product_type_dict)

        bom_id = l.product_id.product_tmpl_id.bom_ids
        process_id = []
        if bom_id:
            process_id = [bom_id[0].process_id.id, bom_id[0].process_id.name]

        product_cost = object.product_id.pre_cost_cal_new(raise_exception=False)
        line_cost = product_cost if product_cost else 0
        material_cost = line_cost * object.product_qty
        # man_cost = l.action_id.cost if l.action_id else 0
        # total_cost = material_cost + man_cost

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
            'process_action_1': l.action_id_1.name if l.action_id_1 else '',
            'process_action_2': l.action_id_2.name if l.action_id_2 else '',
            'material_cost': round(material_cost, 2),
            # 'manpower_cost': round(man_cost, 2),
            # 'total_cost': round(total_cost, 2),
            'parent_id': parnet.id,
            'qty': l.product_qty,
            'process_id': process_id,
        }
        result.append(res)

    return res


class MrpBomLine(models.Model):
    _inherit = 'mrp.bom.line'

    # sub_total_cost = fields.Float(compute='_get_sub_total_cost')
    action_line_ids = fields.One2many('process.action.line', 'bom_line_id')

    def get_process_action_ids(self):
        pass

    def parse_action_line_data(self):
        res = []
        for line in self.action_line_ids:
            data = {
                'action_id': line.action_id.id,
                'action_name': line.action_id.name,
                'rate': line.rate
            }
            res.append(data)
        return res

    @api.multi
    def _get_adjust_total_cost(self):
        for line in self:
            if line.adjust_time and line.bom_id.process_id.hourly_wage:
                line.adjust_cost = line.bom_id.process_id.hourly_wage * line.adjust_time
            else:
                line.adjust_cost = 0.0

    # @api.multi
    # def _get_sub_total_cost(self):
    #     for line in self:
    #         line.sub_total_cost = (line.cost + line.adjust_cost) * line.product_qty

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

    @api.model
    def save_multi_changes(self, args, **kwargs):
        bom_id = kwargs.get('bom_id')
        for arg in args:
            bom_line_id = self.env['mrp.bom.line'].browse(arg.get('id'))
            action_date = {
                'action_id_1': arg.get('action_id_1'),
                'rate1': arg.get('rate1'),
                'action_id_2': arg.get('action_id_2'),
                'rate2': arg.get('rate2'),
            }
            temp_date = {
                'category_id': bom_line_id.bom_id.product_tmpl_id.categ_id.id,
                'p_product_id': arg.get('product_id'),
                'product_id': arg.get('product_id'),
            }
            temp_date.update(action_date)
            self.env['bom.cost.category.temp'].create({
                temp_date
            })
            bom_line_id.write(action_date)

        return self.env['mrp.bom'].browse(int(bom_id)).get_bom_cost_new()


class ProcessActionLine(models.Model):
    _name = 'process.action.line'
    bom_line_id = fields.Many2one('mrp.bom.line')
    action_id = fields.Many2one('mrp.process.action')
    rate = fields.Float()
