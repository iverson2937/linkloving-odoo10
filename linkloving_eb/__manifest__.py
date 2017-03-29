# -*- coding: utf-8 -*-
{
    'name': "linkloving_eb",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/openerp/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base','sales_team','crm', 'stock', 'purchase', 'sale', 'linkloving_sale'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'security/stock_location.xml',
        'views/views.xml',
        'views/eb_refund_order.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}