from odoo import http
from odoo.http import request

class ShopifyDashboardController(http.Controller):
    pass

    # @http.route('/shopify/dashboard/data', type='json', auth='user')
    # def get_dashboard_data(self):
    #         customer_count = request.env['customer.shopify'].sudo().search_count([])
    #         order_count = request.env['shopify.order'].sudo().search_count([])
    #         product_count = request.env['shopify.product'].sudo().search_count([])
    #
    #         return {
    #             'customer_count': customer_count,
    #             'order_count': order_count,
    #             'product_count': product_count,
    #         }
