from odoo import models, fields, api,_
import requests
import json
from odoo.tools.safe_eval import pytz, _logger
from datetime import datetime, timedelta
from odoo.exceptions import ValidationError, UserError
from urllib.parse import urlencode



class BaseShopify(models.Model):
    _inherit ="base.shopify"

    def import_shopify_stock_to_odoo(self):
        """Fetch Shopify inventory and update stock for matching Odoo products by SKU"""
        connection_info = self.env['base.shopify'].get_shopify_connection_info()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }

        # Step 2: Get Products Updated Recently (optional time filter)
        updated_at_min = datetime.utcnow() - timedelta(minutes=30)
        timestamp = updated_at_min.isoformat() + "Z"
        query = urlencode({
            "limit": 100,
            "updated_at_min": timestamp
        })

        products_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/products.json?{query}"
        response = requests.get(products_url, headers=headers)
        if response.status_code != 200:
            raise UserError(f"Failed to fetch products from Shopify: {response.text}")

        products = response.json().get('products', [])
        inventory_item_map = {}
        for product in products:
            for variant in product.get('variants', []):
                sku = variant.get('sku')
                inventory_item_id = variant.get('inventory_item_id')
                if sku and inventory_item_id:
                    inventory_item_map[inventory_item_id] = sku

        if not inventory_item_map:
            return {
                'message': "⚠ No products with valid SKU and inventory_item_id found in Shopify."
            }

        # Step 3: Fetch Inventory Levels from Shopify
        inventory_ids = ','.join(str(iid) for iid in inventory_item_map.keys())
        inventory_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/inventory_levels.json?inventory_item_ids={inventory_ids}"
        inv_response = requests.get(inventory_url, headers=headers)
        if inv_response.status_code != 200:
            raise UserError(f"Failed to fetch inventory levels: {inv_response.text}")

        inventory_levels = inv_response.json().get('inventory_levels', [])

        # Step 4: Update Odoo Products by SKU
        Product = self.env['product.product'].sudo()
        Inventory = self.env['stock.quant'].sudo()
        Location = self.env['stock.location'].sudo()
        internal_location = Location.search([('usage', '=', 'internal')], limit=1)
        if not internal_location:
            raise UserError("No internal stock location found.")

        for item in inventory_levels:
            inventory_item_id = item['inventory_item_id']
            qty = item['available']
            sku = inventory_item_map.get(inventory_item_id)

            # Match Odoo product by SKU
            product = Product.search([('default_code', '=', sku)], limit=1)
            if not product:
                _logger.info(f"SKU '{sku}' not found in Odoo. Skipping.")
                continue

            stock_quant = Inventory.search([
                ('product_id', '=', product.id),
                ('location_id', '=', internal_location.id),
            ], limit=1)

            # Step 6: Update or create the stock quant record
            if stock_quant:
                # Update the quantity if the stock quant exists
                stock_quant.write({'quantity': qty})
                _logger.info(f"Stock quantity for SKU {sku} updated to {qty}.")
            else:
                # If no stock quant exists, create a new one
                Inventory.create({
                    'product_id': product.id,
                    'location_id': internal_location.id,
                    'quantity': qty,
                })
                _logger.info(f"New stock quant created for SKU {sku} with quantity {qty}.")

        return True


    def get_inventory_locations(self,inventory_item_id):
        connection_info = self.env['base.shopify'].get_shopify_connection_info()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }

        url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/inventory_levels.json"
        params = {
            "inventory_item_ids": inventory_item_id
        }
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json()
            return [level["location_id"] for level in data.get("inventory_levels", [])]
        else:
            raise Exception(f"Failed to fetch inventory levels: {response.text}")















