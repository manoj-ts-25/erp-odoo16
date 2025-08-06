# -- coding: utf-8 --
{
    'name': 'Ts Shopify Connector',
    'version': '16.0.0.1',
    'author': 'Technians Softech Pvt.Ltd',
    'depends': ['base','sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/shopify_instance.xml',
        'views/shopify_products.xml',
    ],

    'external_dependencies': {
        'python': ['ShopifyAPI']
    },
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'application': False,
}
