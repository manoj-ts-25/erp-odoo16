from odoo import models, fields, api
import requests

from odoo.exceptions import ValidationError, UserError


class ShopifyOrderImport(models.Model):
    _name = 'shopify.order'
    _description = 'Shopify Orders'

    order_id = fields.Char(string="Shopify Order ID")
    name = fields.Char(string="Order Name")
    customer_email = fields.Char(string="Customer Email")
    total_price = fields.Float(string="Total Price")
    currency = fields.Char(string="Currency")
    created_at = fields.Datetime(string="Created At")
    financial_status = fields.Char(string="Financial Status")
    shopify_order_line_ids = fields.One2many('shopify.order.line', 'order_id', string="Order Lines")
    payment_gateway_names = fields.Char(string="payment gateway names")
    shopify_customer_id = fields.Many2one('customer.shopify')






    def fetch_shopify_orders(self):
        """Fetch all orders from Shopify and store them in Odoo"""
        connection_info = self.env['base.shopify'].get_shopify_connection_info()

        limit = 50
        orders_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/orders.json?limit={limit}"
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token":connection_info['access_token'] ,
        }

        while orders_url:
            response = requests.get(orders_url, headers=headers)

            if response.status_code != 200:
                raise UserError(f"Failed to fetch orders: {response.status_code} - {response.text}")

            data = response.json()
            orders = data.get("orders", [])
            existing_order_ids = set(self.env['shopify.order'].search([]).mapped('order_id'))

            order_values = []
            line_item_values = []

            for order in orders:
                shopify_order_id = str(order.get("id"))  # Convert to string to match Odoo records

                # Check if order already exists in Odoo
                if shopify_order_id in existing_order_ids:
                    continue  # Skip this order as it already exists
                customer = order.get("customer", {})
                note_attributes = order.get("note_attributes", [])
                payment_gateway_names = order.get("payment_gateway_names", [])
                default_address = customer.get("default_address", {})

                # Initialize default values
                extracted_data = {
                    "name": "",
                    "phone": "",
                    "address": "",
                    "pincode": "",
                    "state": "",
                    "city": "",
                    "country": "",
                }

                # Extract data from note_attributes
                for attribute in note_attributes:
                    name = attribute.get("name", "").lower()
                    value = attribute.get("value", "")

                    if name == "name":
                        extracted_data["name"] = value
                    elif name == "phone":
                        extracted_data["phone"] = value
                    elif name == "address":
                        extracted_data["address"] = value
                    elif name == "pin code":
                        extracted_data["pincode"] = value
                    elif name == "state":
                        extracted_data["state"] = value
                    elif name == "city":
                        extracted_data["city"] = value
                    elif name == "country":
                        extracted_data["country"] = value

                # Append final order data
                existing_customer = self.env['customer.shopify'].search([
                    ('customer_email', '=', customer.get("email"))
                ], limit=1)

                # ➕ Create if not exists
                if not existing_customer:
                    existing_customer = self.env['customer.shopify'].create({
                        'customer_name': extracted_data["name"],
                        'customer_email': customer.get("email"),
                        'customer_phone': extracted_data["phone"],
                        'billing_address1': extracted_data["address"],
                        'billing_zip': extracted_data["pincode"],
                        'billing_state': extracted_data["state"],
                        'billing_city': extracted_data["city"],
                        'billing_country': extracted_data["country"],
                    })

                # ➕ Create the order and link customer
                order_values.append({
                    'order_id': order.get("id"),
                    'name': order.get("name"),
                    'customer_email': customer.get("email"),
                    'total_price': float(order.get("total_price", 0.0)),
                    'currency': order.get("currency"),
                    'financial_status': order.get("financial_status"),
                    'payment_gateway_names': payment_gateway_names,

                    # 'customer_name': extracted_data["name"],
                    # 'customer_phone': extracted_data["phone"],
                    # 'billing_address1': extracted_data["address"],
                    # 'billing_zip': extracted_data["pincode"],
                    # 'billing_state': extracted_data["state"],
                    # 'billing_city': extracted_data["city"],
                    # 'billing_country': extracted_data["country"],

                    'shopify_customer_id': existing_customer.id,  # 🧩 Link customer
                })
                # Bulk create orders
                order_records = self.env['shopify.order'].create(order_values)

            # Create Order Line Items in batch
            for order, order_record in zip(orders, order_records):
                for line_item in order.get("line_items", []):
                    line_item_values.append({
                        'order_id': order_record.id,
                        'shopify_product_id': line_item.get("product_id"),
                        'product_variant_id': line_item.get("variant_id"),
                        'product_name': line_item.get("name"),
                        'quantity': line_item.get("quantity"),
                        'price': float(line_item.get("price", 0.0)),

                    })

            if line_item_values:
                self.env['shopify.order.line'].create(line_item_values)

            # Pagination handling
            next_page_url = None
            link_header = response.headers.get("Link", "")
            if 'rel="next"' in link_header:
                parts = link_header.split(",")
                for part in parts:
                    if 'rel="next"' in part:
                        next_page_url = part.split("<")[1].split(">")[0]
                        break

            orders_url = next_page_url

        return True

    def create_sale_order(self):
        """Create an Odoo Sale Order from the Shopify Order"""
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']
        Partner = self.env['res.partner']

        for order in self:
            # Find or create a customer in Odoo
            partner = Partner.search([('display_name', '=', order.shopify_customer_id.customer_email)], limit=1)
            if not partner:
                partner = Partner.create({
                    'name': order.shopify_customer_id.customer_name or order.shopify_customer_id.customer_email,
                    'email': order.shopify_customer_id.customer_email,
                    'phone': order.shopify_customer_id.customer_phone,
                    'street': order.shopify_customer_id.billing_address1,
                    'zip': order.shopify_customer_id.billing_zip,
                    'city': order.shopify_customer_id.billing_city,
                    'state_id': self.env['res.country.state'].search([('name', '=', order.shopify_customer_id.billing_state)], limit=1).id,
                    'country_id': self.env['res.country'].search([('name', '=', order.shopify_customer_id.billing_country)], limit=1).id,
                })

            # Create Sale Order
            sale_order = SaleOrder.create({
                'partner_id': partner.id,
                # 'date_order': order.created_at,
                'currency_id': self.env['res.currency'].search([('name', '=', order.currency)], limit=1).id,
                'origin': f"Shopify-{order.name}",
            })

            # Create Sale Order Lines
            for line in order.shopify_order_line_ids:
                product = self.env['product.product'].search([
                    ('shopify_id', '=', line.shopify_product_id),
                ], limit=1)

                SaleOrderLine.create({
                    'order_id': sale_order.id,
                    'product_id': product.id if product else False,
                    'name':  product.name,
                    'product_uom_qty': line.quantity,
                    'price_unit': line.price,
                })

        return True



class ShopifyOrderLine(models.Model):
    _name = 'shopify.order.line'
    _description = 'Shopify Order Line Items'

    order_id = fields.Many2one('shopify.order', string="Shopify Order")
    shopify_product_id = fields.Char(string="Shopify Product ID")
    product_variant_id = fields.Char(string="Shopify Variant ID")
    product_name = fields.Char(string="Product Name")
    quantity = fields.Integer(string="Quantity")
    price = fields.Float(string="Price")