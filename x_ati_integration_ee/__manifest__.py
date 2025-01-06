# -*- coding: utf-8 -*-
{
    'name': "x_ati_integration_ee",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "Asop",
    'website': "https://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'sale_management', 'project', 'account', 'product', 'purchase', 'hr_expense'],

    # always loaded
    'data': [
        'data/system_parameter.xml',
        'data/datas.xml',
        'security/system_security.xml',
        'security/ir.model.access.csv',
        'views/account_move.xml',
        'views/integration_integration.xml',
        'views/purchase_order.xml',
        'views/sale_order.xml',
        'views/stock_picking.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
