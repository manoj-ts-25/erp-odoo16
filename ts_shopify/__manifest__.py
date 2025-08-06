{
    'name': 'Shopify Odoo Connector',
    'version': '16.0',
    'category': 'Connector',
    'sequence': 1,
    'website': '',
    'summary': 'odoo Shopify Integration',
    'description': 'Odoo Shopify Integration',
    'author': 'Technians',
    'depends': ['base','mail','product','sale','stock','web'],

    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_job.xml',
         'views/res_config_settings.xml',

        'views/base_shopify.xml',
        'views/shopify_product.xml',
        'views/product_template.xml',
        'views/shopify_order.xml',
        'wizard/shopify_operation_view.xml',
        'views/shopify_cancel_order.xml',
        'views/shopify_customer.xml',
        # 'views/assets.xml',
        'views/dashboard_menu.xml',
        'views/shopify_sync_log.xml',
        'views/shopify_product_varient.xml',
        # 'views/dashboard_action.xml',
        # 'views/dashboard_template.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'ts_shopify/static/src/js/inventory_check.js',
            # 'ts_shopify/static/src/js/shopify_dashboard.js',
            # 'ts_shopify/static/src/xml/dashboard_template.xml',
        ]
    },

    'demo': [
    ],

    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}