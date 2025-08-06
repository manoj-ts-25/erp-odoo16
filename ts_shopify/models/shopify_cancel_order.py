import base64

from odoo import models, fields, api
import requests
import json
from datetime import date,datetime,timedelta
from odoo.exceptions import ValidationError, UserError

class CancelOrder(models.Model):
    _name = "shopify.cancel.order"
    _description = "fetch cancel order"
    _rec_name='customer_id'


    order_id = fields.Char(string='Order Id ')
    cancelled_at = fields.Char(string="Cancelled At")
    cancelled_reason = fields.Char(string="Cancelled Reason")
    customer_id = fields.Many2one('res.partner' ,string="Customer")


    def _fetch_cancel_order(self):
        connection_info = self.env['base.shopify'].get_shopify_connection_info()

        if not connection_info['shop_url'] or not connection_info['access_token']:
            raise UserError("Shop URL and API Token are required.")
        base_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/orders.json?status=cancelled"

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }

        all_orders = []
        next_page_url = base_url

        while next_page_url:
            response = requests.get(next_page_url, headers=headers)
            if response.status_code != 200:
                raise UserError(f"Failed to fetch orders: {response.text}")

            data = response.json()
            all_orders.extend(data.get("orders", []))

            # Handle pagination
            link_header = response.headers.get("Link")
            if link_header and 'rel="next"' in link_header:
                links = requests.utils.parse_header_links(link_header.rstrip('>').replace('>,', '>,'))
                next_page_url = next((link['url'] for link in links if link['rel'] == 'next'), None)
            else:
                next_page_url = None
        for order in all_orders:
            cancelled_at = order.get("cancelled_at")
            cancelled_reason = order.get("cancel_reason")
            order_id = order.get("id")
            customer_data = order.get("customer", {})

            # Find existing customer or skip if not found
            customer = None
            if customer_data:
                email = customer_data.get("email")
                customer = self.env['res.partner'].sudo().search([('email', '=', email)], limit=1)

            # Create cancel order record
            self.env['shopify.cancel.order'].create({
                'order_id': str(order_id),
                'cancelled_at': cancelled_at,
                'cancelled_reason': cancelled_reason,
                'customer_id': customer.id if customer else False,
            })

        return all_orders

