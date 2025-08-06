# -- coding: utf-8 --
{
    'name': 'Ts Move Sale Type',
    'version': '16.0.0.1',
    'author': 'Technians Softech Pvt.Ltd',
    'website': 'https://technians.com/',
    'depends': ['base','sale_management', 'account'],
    'data': [
        'views/sale_order_line.xml',
        'views/account_move_line.xml',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'application': False,
}
