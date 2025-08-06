import base64
import os
from odoo import models, fields, api
import requests
import json
from odoo.tools.safe_eval import pytz, _logger
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
# from odoo.odoo.exceptions import UserError
from urllib.parse import urlencode

import io
from io import BytesIO
import requests
from PIL import Image
import base64
# import requests
#
# def image_url_to_base64(url):
#     try:
#         response = requests.get(url)
#         if response.status_code == 200:
#             return base64.b64encode(response.content)
#     except Exception as e:
#         _logger.error(f"Image download failed: {e}")
#     return False




class Shopify_product(models.Model):
    _name = "shopify.product"



    name =fields.Char(string="Title")
    shopify_id = fields.Char(string='Shopify Id')
    list_price = fields.Float(string="List Price")
    image_1920 = fields.Binary(string='Image', attachment=True)
    description = fields.Html(string="Description")
    vendor = fields.Char(string="Your Brand")
    product_type = fields.Char(string="Product Type")
    tags = fields.Char(string="Tags")
    varient_product_ids = fields.One2many('shopify.product.varient','product_tmplt_id')
    attribute_ids = fields.One2many("shopify.product.attribute", "product_id", string="Attributes")
    status = fields.Char(string="status")


    # def _process_image(self, image_data, record_id):
    #     """Convert image to PNG and save to /tmp/"""
    #     try:
    #         image = Image.open(BytesIO(image_data))
    #
    #         buffer = BytesIO()
    #         image.save(buffer, format='PNG')
    #         buffer.seek(0)
    #
    #         filename = f'image_{record_id}.png'
    #         file_path = f'/tmp/{filename}'
    #
    #         with open(file_path, 'wb') as f:
    #             f.write(buffer.read())
    #
    #         _logger.info(f"Image saved: {file_path}")
    #         return filename, file_path
    #
    #     except Exception as e:
    #         _logger.error(f"Image processing error for record {record_id}: {e}")
    #         return False, False
    #
    # @api.model
    # def create(self, vals):
    #     """Override create to process image"""
    #     image_data = vals.get('image_1920')
    #     if image_data:
    #         decoded_data = base64.b64decode(image_data)
    #         # Create record first to get ID
    #         record = super().create(vals)
    #         filename, file_path = self._process_image(decoded_data, record.id)
    #         if filename and file_path:
    #             record.write({
    #                 'image_filename': filename,
    #                 'image_file_path': file_path,
    #             })
    #         return record
    #     return super().create(vals)
    #
    # def write(self, vals):
    #     """Override write to process image when changed"""
    #     res = super().write(vals)
    #     for record in self:
    #         if vals.get('image_1920'):
    #             try:
    #                 decoded_data = base64.b64decode(vals['image_1920'])
    #                 filename, file_path = self._process_image(decoded_data, record.id)
    #                 if filename and file_path:
    #                     record.image_filename = filename
    #                     record.image_file_path = file_path
    #             except Exception as e:
    #                 _logger.error(f"Error updating image in write() for record {record.id}: {e}")
    #     return res
    #



    def create_inventory_product(self):
        ProductTemplate = self.env['product.template']
        ProductAttribute = self.env['product.attribute']
        ProductAttributeValue = self.env['product.attribute.value']
        ProductTemplateAttributeLine = self.env['product.template.attribute.line']
        ProductProduct = self.env['product.product']
        StockQuant = self.env['stock.quant']
        StockLocation = self.env['stock.location']

        stock_location = StockLocation.search([('usage', '=', 'internal')], limit=1)

        for shopify_product in self:
            # print("____",shopify_product.image_1920)
            # image_base64 = shopify_product.image_1920
            # if isinstance(image_base64, str) and image_base64.startswith('http'):
            #     image_base64 = image_url_to_base64(shopify_product.image_1920)

            # 1. Create or Update Product Template
            product_template = ProductTemplate.search([('shopify_id', '=', shopify_product.shopify_id)], limit=1)
            if not product_template:
                product_template = ProductTemplate.create({
                    'name': shopify_product.name,
                    'shopify_id': shopify_product.shopify_id,
                    'list_price': shopify_product.list_price,
                    'image_1920': shopify_product.image_1920,
                    'description_sale': shopify_product.description,
                    'detailed_type': 'product',
                    'shopify_status': shopify_product.status,
                })
            else:
                product_template.write({
                    'name': shopify_product.name,
                    'list_price': shopify_product.list_price,
                    'image_1920': shopify_product.image_1920,
                    'description_sale': shopify_product.description,
                    'shopify_status': shopify_product.status,
                })

            # 2. Handle Attributes & Attribute Lines
            attribute_lines = []
            for shopify_attribute in shopify_product.attribute_ids:
                attribute = ProductAttribute.search([('name', '=', shopify_attribute.name)], limit=1)
                if not attribute:
                    attribute = ProductAttribute.create({'name': shopify_attribute.name})

                value_ids = []
                for val in shopify_attribute.value_ids:
                    attr_val = ProductAttributeValue.search([
                        ('name', '=', val.name),
                        ('attribute_id', '=', attribute.id)
                    ], limit=1)
                    if not attr_val:
                        attr_val = ProductAttributeValue.create({
                            'name': val.name,
                            'attribute_id': attribute.id
                        })
                    value_ids.append(attr_val.id)

                attr_line = ProductTemplateAttributeLine.search([
                    ('product_tmpl_id', '=', product_template.id),
                    ('attribute_id', '=', attribute.id)
                ], limit=1)

                if not attr_line:
                    attr_line = ProductTemplateAttributeLine.create({
                        'product_tmpl_id': product_template.id,
                        'attribute_id': attribute.id,
                        'value_ids': [(6, 0, value_ids)],
                    })
                else:
                    attr_line.write({'value_ids': [(6, 0, value_ids)]})

                attribute_lines.append(attr_line.id)

            if attribute_lines:
                product_template.write({'attribute_line_ids': [(6, 0, attribute_lines)]})


                # Step 7: Create or update stock quant


    @api.model
    def log_failed_variant(self, variant, reason='Sync failed'):
        self.env['shopify.sync.log'].create({
            'name': variant.product_tmplt_id.name,
            # 'variant_id': variant.id,
            'default_code': variant.default_code,
            'shopify_variant_id': variant.shopify_variant_id,
            'failure_reason': reason,
        })

    def _get_shopify_current_stock(self,inventory_item_id, location_id, headers, connection_info):
        """Helper to fetch current inventory from Shopify"""

        url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/inventory_levels.json"
        params = {
            'inventory_item_ids': inventory_item_id,
            'location_ids': location_id
        }
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            levels = response.json().get("inventory_levels", [])
            return levels[0]["available"] if levels else 0
        else:
            _logger.warning(f"Failed to fetch current inventory for item {inventory_item_id}: {response.text}")
            return 0

    def update_stock(self):
        """Export updated Odoo stock to Shopify using inventory_stock from shopif.product.variant (last 1 hour)"""

        # Step 1: Get Shopify connection
        connection_info = self.env['base.shopify'].get_shopify_connection_info()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }

        # Step 2: Get variants updated in the last hour
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        Variant = self.env['shopify.product.varient'].sudo()
        recent_variants = Variant.search([
            ('write_date', '>=', one_hour_ago.strftime('%Y-%m-%d %H:%M:%S')),
            ('shopify_variant_id', '!=', False),
            ('default_code', '!=', False),
            ('shopify_inventory', '!=', False),
        ])

        if not recent_variants:
            return {'message': 'No variants with updated stock in the last hour.'}

        # Step 3: Get Shopify location (use the first available)
        location_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/locations.json"
        location_response = requests.get(location_url, headers=headers)
        if location_response.status_code != 200:
            raise UserError(f"Failed to fetch Shopify locations: {location_response.text}")

        locations = location_response.json().get('locations', [])
        if not locations:
            raise UserError("No inventory locations found in Shopify.")

        shopify_location_id = locations[0]['id']

        # Step 4: Adjust inventory for each updated variant
        for variant in recent_variants:
            sku = variant.default_code
            inventory_item_id = variant.shopify_variant_id
            odoo_qty = int(variant.shopify_inventory)
            update_payload = {
                "inventory_item_id": inventory_item_id,
                "location_id": shopify_location_id,
                "available": odoo_qty
            }

            update_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/inventory_levels/adjust.json"
            response = requests.post(update_url, headers=headers, json=update_payload)

            if response.status_code in [200, 201]:
                _logger.info(f"✅ Adjusted stock for SKU {sku} by  → Shopify now matches Odoo ({odoo_qty})")
            else:
                _logger.warning(f"❌ Failed to adjust stock for SKU {sku}: {response.text}")

        return {'status': 'done', 'message': 'Odoo stock adjustments pushed to Shopify.'}


            # for variant in shopify_product.varient_product_ids:
            #     PTAV = self.env['product.template.attribute.value']
            #
            #     combination = PTAV.search([
            #         ('product_tmpl_id', '=', product_template.id),
            #         ('product_attribute_value_id.name', 'in', [val.name for val in variant.attribute_value_ids])
            #     ])
            #
            #     product_variant = product_template._get_variant_for_combination(combination)
            #
            #     if product_variant:
            #         product_variant.write({
            #             'barcode': variant.barcode,
            #             'list_price': variant.list_price,
            #             'weight': variant.weight,
            #             'default_code': variant.default_code,
            #             'shopify_variant_id': variant.shopify_variant_id,
            #             # 'lst_price': variant.list_price
            #         })
            #
            #     if stock_location:
            #         stock_quant = self.env['stock.quant'].search([
            #             ('product_id', '=', product_variant.id),
            #             ('location_id', '=', stock_location.id)
            #         ], limit=1)
            #
            #         if stock_quant:
            #             stock_quant.write({'quantity': float(variant.shopify_inventory)})
            #         else:
            #             self.env['stock.quant'].create({
            #                 'product_id': product_variant.id,
            #                 'location_id': stock_location.id,
            #                 'quantity': float(variant.shopify_inventory),
            #             })
    #
    # def update_price(self):
    #     stock_quant = self.env['stock.quant'].search([
    #         ('product_id', '=', product_variant.id),
        # for variant in self.varient_product_ids:
        #     ProductProduct = self.env['product.product'].search([
        #         ('shopify_variant_id', '=', variant.shopify_variant_id)
        #     ])
        #
        #     if ProductProduct:
        #         ProductProduct.write({
        #             'qty_available': float(variant.shopify_inventory)  # ✅ Update custom field from Shopify variant
        #         })




    # def create_shopify_product(self):
    #     """Create or update a product in Shopify from Odoo."""
    #     self.ensure_one()
    #
    #     shopify_config = self.env["base.shopify"].search([], limit=1)
    #     if not shopify_config:
    #         raise UserError("Shopify credentials not found in base.shopify model.")
    #
    #     shop_url = shopify_config.website_url.strip("/")
    #     access_token = shopify_config.shopify_api_token
    #
    #     if not shop_url or not access_token:
    #         raise UserError("Shop URL and API Token are required in base.shopify.")
    #
    #     api_version = "2025-01"  # Use the latest stable API version
    #
    #     # Determine API URL and HTTP method (POST for create, PUT for update)
    #     if self.shopify_id:
    #         url = f"https://{shop_url}/admin/api/{api_version}/products/{self.shopify_id}.json"
    #         method = requests.put  # Update existing product
    #     else:
    #         url = f"https://{shop_url}/admin/api/{api_version}/products.json"
    #         method = requests.post  # Create new product
    #
    #     # Prepare images (Base64 encoding or URL)
    #     # images = []
    #     # if self.image_1920:
    #     #     image_base64 = base64.b64encode(self.image_1920).decode("utf-8")
    #     #     images.append({"src": f"data:image/jpeg;base64,{image_base64}"})  # Shopify accepts Base64 format
    #
    #     # Prepare product options (attributes)
    #     options = []
    #     for attribute in self.attribute_ids:
    #         options.append({
    #             "name": attribute.name,
    #             "values": attribute.value_ids.mapped("name"),  # Extract all attribute values
    #         })
    #
    #     # Prepare product variants
    #     variants = []
    #     for variant in self.varient_product_ids:
    #         variants.append({
    #             "price": variant.list_price ,  # Default price if missing
    #             "sku": variant.default_code,
    #             "inventory_quantity": variant.shopify_inventory,
    #         })
    #
    #     # Product data payload
    #     payload = {
    #         "product": {
    #             "title": self.name,
    #             "body_html": self.description or "<p>No description</p>",
    #             "vendor": self.vendor or '',
    #             "product_type": self.product_type or '',
    #             "tags": self.tags or '',
    #             "options": options,  # Shopify product options
    #             "variants": variants,
    #             # "images": images,  # Product images
    #         }
    #     }
    #
    #     headers = {
    #         "Content-Type": "application/json",
    #         "X-Shopify-Access-Token": access_token,
    #     }
    #
    #     try:
    #         response = method(url, headers=headers, json=payload)
    #         response.raise_for_status()  # Raise an error for HTTP errors (4xx, 5xx)
    #
    #         product_data = response.json().get("product", {})
    #         self.shopify_id = product_data.get("id")
    #         shopify_variants = product_data.get("variants", [])
    #         for local_variant in self.varient_product_ids:
    #             for shopify_variant in shopify_variants:
    #                 if local_variant.default_code == shopify_variant.get("sku"):
    #                     local_variant.shopify_variant_id = shopify_variant.get("id")
    #
    #         return product_data  # Return product details
    #     except requests.exceptions.RequestException as e:
    #         raise UserError(f"Error creating/updating product in Shopify: {e}")


    def create_shopify_product(self):
        """Create or update a product in Shopify from Odoo."""

        shopify_config = self.env["base.shopify"].search([], limit=1)
        if not shopify_config:
            raise UserError("Shopify credentials not found in base.shopify model.")

        shop_url = shopify_config.website_url.strip("/")
        access_token = shopify_config.shopify_api_token

        if not shop_url or not access_token:
            raise UserError("Shop URL and API Token are required in base.shopify.")

        api_version = "2025-01"

        # Determine API URL and HTTP method
        if self.shopify_id:
            url = f"https://{shop_url}/admin/api/{api_version}/products/{self.shopify_id}.json"
            method = requests.put
        else:
            url = f"https://{shop_url}/admin/api/{api_version}/products.json"
            method = requests.post

        # Prepare options (attribute definitions)
        options = []
        for attribute in self.attribute_ids:
            options.append({
                "name": attribute.name,
                "values": attribute.value_ids.mapped("name"),
            })

        # Prepare variants
        variants = []
        for variant in self.varient_product_ids:
            variant_data = {
                "price": variant.list_price,
                "sku": variant.default_code,
                "inventory_quantity": int(variant.shopify_inventory or 0),
                "weight": variant.weight,
                "weight_unit": variant.weight_unit or "kg",
                "barcode": variant.barcode or '',
            }

            # Add option1, option2, etc.
            attr_values = variant.attribute_value_ids.mapped('name')
            for idx, val in enumerate(attr_values):
                variant_data[f"option{idx + 1}"] = val

            variants.append(variant_data)

        payload = {
            "product": {
                "title": self.name,
                "body_html": self.description or "<p>No description</p>",
                "vendor": self.vendor or '',
                "product_type": self.product_type or '',
                "tags": self.tags or '',
                "options": options,
                "variants": variants,
                # You can include images later
            }
        }

        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": access_token,
        }

        # Debug log
        _logger.info("Sending product payload to Shopify: %s", json.dumps(payload, indent=2))

        try:
            response = method(url, headers=headers, json=payload)
            response.raise_for_status()

            product_data = response.json().get("product", {})
            self.shopify_id = product_data.get("id")
            shopify_variants = product_data.get("variants", [])

            for local_variant in self.varient_product_ids:
                for shopify_variant in shopify_variants:
                    if local_variant.default_code == shopify_variant.get("sku"):
                        local_variant.shopify_variant_id = shopify_variant.get("id")

            self.update_images()

            return product_data

        except requests.exceptions.HTTPError as e:
            try:
                error_response = response.json()
                message = json.dumps(error_response, indent=2)
            except Exception:
                message = response.text
            raise UserError(f"Shopify API error ({response.status_code}): {message}")

        except requests.exceptions.RequestException as e:
            raise UserError(f"Error creating/updating product in Shopify: {e}")

    def get_odoo_image_url(self):
        """Convert Odoo image_1920 to a publicly accessible URL."""
        if not self.image_1920:
            return None

        attachment = self.env['ir.attachment'].create({
            'name': f"{self.name}_image",
            'type': 'binary',
            'datas': self.image_1920,
            'mimetype': 'image/jpeg',
            'public': True,  # Make it publicly accessible
        })
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/web/content/{attachment.id}"


    def update_images(self):
        connection_info = self.env['base.shopify'].get_shopify_connection_info()
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": connection_info['access_token'],
        }

        images_url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/products/{self.shopify_id}/images.json"

        # if not self.image_1920:
        #     raise ValueError("No image found in image_1920 field.")

            # Use image_1920 directly, it's already base64 encoded in Odoo
        image_base64 = self.image_1920.decode('utf-8') if isinstance(self.image_1920, bytes) else self.image_1920

        # Optional: if you want to send a filename
        filename = f"{self.name or 'image'}.png"

        payload = {
            "image": {
                "attachment": image_base64,
                "filename": filename
            }
        }

        response = requests.post(images_url, json=payload, headers=headers)
        print(response.status_code, response.json())
    # def create_inventory_product(self):
    #     """Create or Update product.template & product.product from Shopify data."""
    #     ProductTemplate = self.env['product.template']
    #     ProductAttribute = self.env['product.attribute']
    #     ProductAttributeValue = self.env['product.attribute.value']
    #     ProductTemplateAttributeLine = self.env['product.template.attribute.line']
    #
    #     for shopify_product in self:
    #         # Check if product template already exists
    #         product_template = ProductTemplate.search([('shopify_id', '=', shopify_product.shopify_id)], limit=1)
    #
    #         if not product_template:
    #             product_template = ProductTemplate.create({
    #                 'name': shopify_product.name,
    #                 'shopify_id': shopify_product.shopify_id,
    #                 'list_price': shopify_product.list_price,
    #                 'image_1920': shopify_product.image_1920,
    #                 'description_sale': shopify_product.description,
    #                 'detailed_type': 'product',  # Physical product
    #             })
    #         else:
    #             # Update the existing product.template
    #             product_template.write({
    #                 'name': shopify_product.name,
    #                 'list_price': shopify_product.list_price,
    #                 'image_1920': shopify_product.image_1920,
    #                 'description_sale': shopify_product.description,
    #             })
    #
    #         # Handle product attributes
    #         attribute_lines = []
    #         for shopify_attribute in shopify_product.attribute_ids:
    #             # Search for existing attribute
    #             attribute = ProductAttribute.search([('name', '=', shopify_attribute.name)], limit=1)
    #
    #             if not attribute:
    #                 attribute = ProductAttribute.create({'name': shopify_attribute.name})
    #
    #             # Search or create attribute values
    #             value_ids = []
    #             for value in shopify_attribute.value_ids:
    #                 attr_value = ProductAttributeValue.search([
    #                     ('name', '=', value.name),
    #                     ('attribute_id', '=', attribute.id)
    #                 ], limit=1)
    #
    #                 if not attr_value:
    #                     attr_value = ProductAttributeValue.create({
    #                         'name': value.name,
    #                         'attribute_id': attribute.id
    #                     })
    #
    #                 value_ids.append(attr_value.id)
    #
    #             # Check if attribute line exists before creating
    #             attribute_line = ProductTemplateAttributeLine.search([
    #                 ('product_tmpl_id', '=', product_template.id),
    #                 ('attribute_id', '=', attribute.id)
    #             ], limit=1)
    #
    #             if not attribute_line:
    #                 attribute_line = ProductTemplateAttributeLine.create({
    #                     'product_tmpl_id': product_template.id,
    #                     'attribute_id': attribute.id,
    #                     'value_ids': [(6, 0, value_ids)]
    #                 })
    #             else:
    #                 attribute_line.write({'value_ids': [(6, 0, value_ids)]})
    #
    #             attribute_lines.append(attribute_line.id)
    #
    #         if attribute_lines:
    #             product_template.write({'attribute_line_ids': [(6, 0, attribute_lines)]})
    #
    #     # Let Odoo generate variants instead of creating them manually
    #     for variant in shopify_product.varient_product_ids:
    #         product_variant = product_template.product_variant_ids.filtered(
    #             lambda v: v.default_code == variant.default_code
    #         )
    #
    #         if product_variant:
    #             product_variant.write({
    #                 'barcode': variant.barcode,
    #                 'list_price': variant.list_price,
    #             })
    #         else:
    #             # Update variant default codes if missing
    #             existing_variant = product_template.product_variant_ids[:1]
    #             existing_variant.write({'default_code': variant.default_code})

    # def create_inventory_product(self):
    #     """Create or Update product.template & product.product from Shopify data."""
    #     ProductTemplate = self.env['product.template']
    #     ProductAttribute = self.env['product.attribute']
    #     ProductAttributeValue = self.env['product.attribute.value']
    #     ProductTemplateAttributeLine = self.env['product.template.attribute.line']
    #     ProductProduct = self.env['product.product']
    #     StockQuant = self.env['stock.quant']
    #     StockLocation = self.env['stock.location']
    #
    #     # Get the default stock location (internal warehouse)
    #     stock_location = StockLocation.search([('usage', '=', 'internal')], limit=1)
    #
    #     for shopify_product in self:
    #         # Check if product template already exists
    #         product_template = ProductTemplate.search([('shopify_id', '=', shopify_product.shopify_id)], limit=1)
    #
    #         if not product_template:
    #             product_template = ProductTemplate.create({
    #                 'name': shopify_product.name,
    #                 'shopify_id': shopify_product.shopify_id,
    #                 'list_price': shopify_product.list_price,
    #                 'image_1920': shopify_product.image_1920,
    #                 'description_sale': shopify_product.description,
    #                 'detailed_type': 'product',  # Physical product
    #             })
    #         else:
    #             # Update the existing product.template
    #             product_template.write({
    #                 'name': shopify_product.name,
    #                 'list_price': shopify_product.list_price,
    #                 'image_1920': shopify_product.image_1920,
    #                 'description_sale': shopify_product.description,
    #             })
    #
    #         # Handle product attributes
    #         attribute_lines = []
    #         for shopify_attribute in shopify_product.attribute_ids:
    #             attribute = ProductAttribute.search([('name', '=', shopify_attribute.name)], limit=1)
    #
    #             if not attribute:
    #                 attribute = ProductAttribute.create({'name': shopify_attribute.name})
    #
    #             # Search or create attribute values
    #             value_ids = []
    #             for value in shopify_attribute.value_ids:
    #                 attr_value = ProductAttributeValue.search([
    #                     ('name', '=', value.name),
    #                     ('attribute_id', '=', attribute.id)
    #                 ], limit=1)
    #
    #                 if not attr_value:
    #                     attr_value = ProductAttributeValue.create({
    #                         'name': value.name,
    #                         'attribute_id': attribute.id
    #                     })
    #
    #                 value_ids.append(attr_value.id)
    #
    #             # Check if attribute line exists before creating
    #             attribute_line = ProductTemplateAttributeLine.search([
    #                 ('product_tmpl_id', '=', product_template.id),
    #                 ('attribute_id', '=', attribute.id)
    #             ], limit=1)
    #
    #             if not attribute_line:
    #                 attribute_line = ProductTemplateAttributeLine.create({
    #                     'product_tmpl_id': product_template.id,
    #                     'attribute_id': attribute.id,
    #                     'value_ids': [(6, 0, value_ids)]
    #                 })
    #             else:
    #                 attribute_line.write({'value_ids': [(6, 0, value_ids)]})
    #
    #             attribute_lines.append(attribute_line.id)
    #
    #         if attribute_lines:
    #             product_template.write({'attribute_line_ids': [(6, 0, attribute_lines)]})

            # Let Odoo generate variants instead of creating them manually
            # for variant in shopify_product.varient_product_ids:
            #     product_variant = ProductProduct.search([
            #         ('product_tmpl_id', '=', product_template.id),
            #         ('default_code', '=', variant.default_code)
            #     ], limit=1)
            #
            #     if product_variant:
            #         product_variant.write({
            #             'barcode': variant.barcode,
            #             'list_price': variant.list_price,
            #             'weight': variant.weight,
            #             'shopify_variant_id': variant.shopify_variant_id,
            #         })
            #     else:
            #         product_variant = ProductProduct.create({
            #             'product_tmpl_id': product_template.id,
            #             'default_code': variant.default_code,
            #             'barcode': variant.barcode,
            #             'list_price': variant.list_price,
            #             'weight':variant.weight,
            #             'shopify_variant_id':variant.shopify_variant_id,
            #         })
            #
            #     # Update stock quantity using shopify_inventory field
            #     if stock_location:
            #         stock_quant = StockQuant.search([
            #             ('product_id', '=', product_variant.id),
            #             ('location_id', '=', stock_location.id)
            #         ], limit=1)
            #
            #         if stock_quant:
            #             stock_quant.write({'quantity': variant.shopify_inventory})  # Updating existing stock
            #         else:
            #             StockQuant.create({
            #                 'product_id': product_variant.id,
            #                 'location_id': stock_location.id,
            #                 'quantity': variant.shopify_inventory,  # Setting new stock
            #             })


class shopify_product_varient(models.Model):

    _name="shopify.product.varient"
    _rec_name='default_code'

    product_tmplt_id = fields.Many2one('shopify.product', string="Product Template", ondelete="cascade")
    shopify_variant_id = fields.Char()
    default_code = fields.Char()
    list_price =fields.Float()
    shopify_inventory=fields.Char()
    weight = fields.Float(string="Weight")
    weight_unit = fields.Char(string="Weight Unit")
    barcode = fields.Char(string="Barcode")
    # sku_code= fields.Char(string='SKU Code')
    cost_per_item = fields.Float(string="Cost per Item")
    attribute_value_ids = fields.Many2many(
        "shopify.product.attribute.value",
        "shopify_varient_attribute_value_rel",  # relation table name
        "varient_id",  # column referencing this model
        "value_id",  # column referencing attribute value
        string="Attribute Values"
    )
    status_shopify = fields.Selection([
        ('success','Success' ),
        ('failed', 'Failed'),
    ])





class ShopifyProductAttribute(models.Model):
    _name = "shopify.product.attribute"
    _description = "Shopify Product Attributes"
    _order = "id desc"

    name = fields.Char("Attribute Name", required=True, index=True)
    shopify_id = fields.Char("Shopify ID", index=True, unique=True)  # Shopify attribute ID
    product_id = fields.Many2one("shopify.product", string="Shopify Product", ondelete="cascade")  # 🔹 Added this field
    value_ids = fields.One2many("shopify.product.attribute.value", "attribute_id", string="Values")  # One2many to Values

class ShopifyProductAttributeValue(models.Model):
    _name = "shopify.product.attribute.value"
    _description = "Shopify Product Attribute Values"
    _order = "attribute_id, id desc"

    name = fields.Char("Value Name", required=True, index=True)
    attribute_id = fields.Many2one("shopify.product.attribute", string="Attribute", required=True, ondelete="cascade")
    shopify_id = fields.Char("Shopify ID", index=True)  # Store Shopify Value ID if needed





class ProductProduct(models.Model):
    _inherit = "product.product"

    shopify_variant_id = fields.Char(string="Shopify Variant Id")



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_published = fields.Boolean(string="Publish to Shopify")
    shopify_status= fields.Char(string="Status")

    @api.onchange('shopify_published')
    def _onchange_shopify_status(self):
       if self.shopify_published:
           self.shopify_status = 'active'
       else:
           self.shopify_status ='draft'


    @api.onchange('shopify_published')
    def _onchange_shopify_publish(self):
        for product in self:
            if product.shopify_id:  # Assume this field stores Shopify ID
                product._update_shopify_publish_status()

    def _update_shopify_publish_status(self):
        for product in self:
            try:
                connection_info = self.env['base.shopify'].get_shopify_connection_info()
                # headers = {
                #                 #     "Content-Type": "application/json",
                #                 #     "X-Shopify-Access-Token": connection_info['access_token'],
                #                 # }
                shopify_product_id = product.shopify_id
                if product.shopify_published:
                    url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/products/{shopify_product_id}.json"
                    payload = {
                        "product": {
                            "id": shopify_product_id,
                            "status": 'active',
                        }
                    }
                else:
                    url = f"https://{connection_info['shop_url']}/admin/api/{connection_info['api_version']}/products/{shopify_product_id}.json"
                    payload = {
                        "product": {
                            "id": shopify_product_id,
                            "status": 'draft',
                        }
                    }

                headers = {
                    "Content-Type": "application/json",
                    "X-Shopify-Access-Token": connection_info['access_token'],
                }

                response = requests.put(url, json=payload, headers=headers)

                if response.status_code == 200:
                    _logger.info(f"Product {product.name} updated on Shopify: {status}")
                else:
                    _logger.error(f"Failed to update Shopify product {product.name}: {response.text}")

            except Exception as e:
                _logger.error(f"Error updating Shopify status for {product.name}: {str(e)}")










