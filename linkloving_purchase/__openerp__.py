# -*- coding: utf-8 -*-
{
    'name': "linkloving_purchase",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Your Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'purchase','linkloving_account','sale','linkloving_sale'],

    # always loaded
    'data': [
        'report/purchase_order_report_template.xml',
        'report/purchase_order_report.xml',
        'security/ir.model.access.csv',
        'views/supplier_view.xml',
        'views/purchase_view.xml',
        'views/purchase_config_view.xml',
        'views/partner_view.xml',
        'views/sale_view.xml',
        'wizard/purchase_order_wizard.xml',
        'templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo.xml',

    ],
}
