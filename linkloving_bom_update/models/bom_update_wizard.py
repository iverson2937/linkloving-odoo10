# -*- coding: utf-8 -*-
import json
import uuid

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class BomUpdateWizard(models.TransientModel):
    _name = "bom.update.wizard"
    postfix = fields.Char(string=u'后缀')

    @api.multi
    def bom_line_update(self):
        context = self._context
        main_bom_id = int(context.get('bom_id'))
        postfix = self.postfix if self.postfix else ''
        update = context.get('update')
        vals = context.get('back_datas')
        line_obj = self.env['mrp.bom.line']
        bom_obj = self.env['mrp.bom']
        product_tmpl_obj = self.env['product.template']
        product_id_obj = self.env['product.product']
        products = {}

        if not update:
            for val in vals:
                temp_product_id = False
                product_id = val.get('product_id')
                parents = val.get('parents')
                modify_type = val.get('modify_type')
                last_bom_line_id = val.get('last_product_id')
                del_bom_line_id = val.get('del_bom_id')
                qty = val.get('qty')
                to_update_bom_line_ids = parents.split(',')
                name_product_name = val.get('copy_name')

                for line in to_update_bom_line_ids:
                    line = int(line)
                    if line != main_bom_id:
                        old_line_id = self.env['mrp.bom.line'].browse(line)
                        if not products.get(old_line_id.product_id):
                            old_product_tmpl_id = old_line_id.product_id
                            default_code = self.get_next_default_code(old_product_tmpl_id.default_code)
                            new_product_tmpl_id = old_line_id.product_id.product_tmpl_id.copy(
                                {'name': old_product_tmpl_id.name + postfix,
                                 'default_code': default_code})
                            new_bom_id = old_line_id.product_id.product_tmpl_id.bom_ids[0].copy()
                            new_bom_id.product_tmpl_id = new_product_tmpl_id.id
                            products.update({
                                old_line_id.product_id: {
                                    'new_product_tmpl_id': new_product_tmpl_id.id,
                                    'new_bom_id': new_bom_id.id
                                }
                            })
                        else:
                            new_product_tmpl_id = product_tmpl_obj.browse(
                                products.get(old_line_id.product_id).get('new_product_tmpl_id'))
                            new_bom_id = bom_obj.browse(products.get(old_line_id.product_id).get('new_bom_id'))
                    else:
                        bom_id = bom_obj.browse(line)
                        old_product_tmpl_id = bom_id.product_tmpl_id
                        if not products.get('bom'):
                            default_code = self.get_next_default_code(old_product_tmpl_id.default_code)
                            new_product_tmpl_id = old_product_tmpl_id.copy({'name': old_product_tmpl_id.name + postfix,
                                                                            'default_code': default_code})
                            new_bom_id = bom_id.copy()
                            new_bom_id.product_tmpl_id = new_product_tmpl_id.id
                            products.update({
                                'bom': {
                                    'new_product_tmpl_id': new_product_tmpl_id.id,
                                    'new_bom_id': new_bom_id.id
                                }
                            })
                        else:
                            new_product_tmpl_id = product_tmpl_obj.browse(
                                products.get('bom').get('new_product_tmpl_id'))
                            new_bom_id = bom_obj.browse(products.get('bom').get('new_bom_id'))

                    if temp_product_id:
                        tmp_id = product_tmpl_obj.browse(temp_product_id)
                        update_bom_line_copy(new_bom_id, tmp_id.product_variant_ids[0].id, old_line_id.product_id)
                    temp_product_id = new_product_tmpl_id.id

                    if modify_type == 'add':
                        if product_id:
                            line_obj.create({
                                'product_id': product_id,
                                'product_qty': qty,
                                'bom_id': new_bom_id.id,
                            })
                            product_id = False
                            # 此为修改bom，需要删除一个bom_line
                    elif modify_type == 'edit':
                        old_product_id = line_obj.browse(last_bom_line_id).product_id
                        if product_id and old_product_id.id != product_id:
                            line_obj.create({
                                'product_id': product_id,
                                'product_qty': qty,
                                'bom_id': new_bom_id.id,
                            })
                            update_bom_line_delete(new_bom_id, old_product_id)
                        elif product_id and old_product_id.id == product_id:
                            update_bom_line_update(new_bom_id, old_product_id, qty)
                        # 第二次循环只需要拷贝bom,product,不需要修改创建修改bom line
                        product_id = False
                    elif modify_type == 'copy':
                        if name_product_name:
                            new_default_code = self.get_next_default_code(
                                product_id_obj.browse(product_id).default_code)
                            new_product_id = product_id_obj.browse(product_id).product_tmpl_id.copy(
                                {'name': name_product_name, 'default_code': new_default_code})
                            line_obj.create({
                                'product_id': new_product_id.product_variant_ids[0].id,
                                'qty': qty,
                                'bom_id': new_bom_id.id,
                            })
                            name_product_name = False
                            old_product_id = line_obj.browse(last_bom_line_id).product_id
                            update_bom_line_delete(new_bom_id, old_product_id)

                    # 直接删除line无需添加

                    elif modify_type == 'del':
                        old_product_id = line_obj.browse(int(del_bom_line_id)).product_id
                        update_bom_line_delete(new_bom_id, old_product_id)
            return {
                'type': 'ir.actions.client',
                'tag': 'bom_update',
                'bom_id': new_bom_id.id
            }
        else:
            # 修改bOM
            for val in vals:
                product_id = val.get('product_id')
                parents = val.get('parents')
                last_bom_line_id = val.get('last_product_id')
                qty = val.get('qty')
                modify_type = val.get('modify_type')
                del_bom_line_id = val.get('del_bom_id')

                to_update_bom_line_ids = parents.split(',')
                line = int(to_update_bom_line_ids[0])
                if line != main_bom_id:
                    line_id = self.env['mrp.bom.line'].browse(int(line))
                    bom_id = line_id.product_id.product_tmpl_id.bom_ids[0]
                else:
                    bom_id = bom_obj.browse(line)

                if modify_type == 'add':
                    if product_id:
                        line_obj.create({
                            'product_id': int(product_id),
                            'product_qty': qty,
                            'bom_id': bom_id.id,
                        })
                        product_id = False
                        # 此为修改bom，需要删除一个bom_line
                elif modify_type == 'edit':
                    last_bom_line_id = line_obj.browse(int(last_bom_line_id))
                    if product_id:
                        last_bom_line_id.write({
                            'product_id': int(product_id),
                            'product_qty': qty,
                        })

                # 直接删除line无需添加
                elif modify_type == 'del':
                    old_product_id = line_obj.browse(int(del_bom_line_id)).product_id
                    update_bom_line_delete(bom_id, old_product_id)
            return {
                'type': 'ir.actions.client',
                'tag': 'bom_update',
                'bom_id': main_bom_id
            }

    def get_next_default_code(self, default_code):
        if not default_code:
            raise UserError(u'产品没有对应料号')

        # 取前10位
        prefix = default_code[0:11]
        products = self.env['product.template'].search([('default_code', 'ilike', prefix)])
        versions = []
        for product in products:
            versions.append(int(product.default_code.split('.')[-1]))
        version = ('000' + str(int(max(versions)) + 1))[-2:]
        new_code = prefix + version
        return new_code


def update_bom_line_copy(new_bom_id, new_product_id, old_product_id):
    if new_product_id:
        for line in new_bom_id.bom_line_ids:
            if line.product_id.id == old_product_id.id:
                line.product_id = new_product_id
                return True


def update_bom_line_delete(new_bom_id, old_product_id):
    for line in new_bom_id.bom_line_ids:
        if line.product_id.id == old_product_id.id:
            line.unlink()


def update_bom_line_update(new_bom_id, old_product_id, qty):
    for line in new_bom_id.bom_line_ids:
        if line.product_id.id == old_product_id.id:
            line.product_qty = qty


if __name__ == '__main__':
    aaa = '001'
    abcv = int(aaa, base=3) + 1
    ddd = '000' + str(abcv)
    ac = '010'
    ccc = ('000' + str(int(ac) + 1))[-3:]
    print ccc