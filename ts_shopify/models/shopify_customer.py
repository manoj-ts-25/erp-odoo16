from odoo import models, fields, api
import requests
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
from urllib.parse import urlencode

class CustomerShopify(models.Model):
    _name ="customer.shopify"
    _rec_name= 'customer_name'

    customer_name = fields.Char("Customer Name")
    customer_phone = fields.Char("Customer Phone")
    billing_address1 = fields.Char("Billing Address")
    billing_zip = fields.Char("Billing ZIP Code")
    billing_state = fields.Char("Billing State")
    billing_city = fields.Char("Billing City")
    billing_country = fields.Char("Billing Country")
    customer_email = fields.Char(string="Customer Email")



    def _fetch_customer_details(self):
        connection_info = self.env['base.shopify'].get_shopify_connection_info()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }
        updated_at_min = datetime.utcnow() - timedelta(minutes=30)
        timestamp = updated_at_min.isoformat() + "Z"
        query = urlencode({
            "limit": 100,
            "updated_at_min": timestamp
        })

        customer_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/customers.json?{query}"
        response = requests.get(customer_url, headers=headers)
        if response.status_code != 200:
            raise UserError(f"Failed to fetch products from Shopify: {response.text}")
        customers = response.json().get('customers', [])
        if not customers:
            raise UserError("No customers found in Shopify.")

        for customer in customers:
            billing = customer.get('default_address', {}) or {}

            # Create record in your model
            self.create({
                'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                'customer_email': customer.get('email'),
                'customer_phone': customer.get('phone'),
                'billing_address1': billing.get('address1'),
                'billing_zip': billing.get('zip'),
                'billing_state': billing.get('province'),
                'billing_city': billing.get('city'),
                'billing_country': billing.get('country'),
            })

        return True




