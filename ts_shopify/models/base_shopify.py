import base64

from odoo import models, fields, api
import requests
import json
from datetime import date,datetime,timedelta
from odoo.exceptions import ValidationError, UserError
from urllib.parse import quote


class BaseShopify(models.Model):
    _name ="base.shopify"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "shopify api Connector"

    name = fields.Char(string="Instance Name")
    image =fields.Binary(string="image")

    website_url = fields.Char(string="Shop Url")
    shopify_api_token = fields.Char(string="Api Access Token")
    shopify_api_key = fields.Char(string="Api Key")
    shopify_secret_key = fields.Char(string="Secret Key")
    api_version  = fields.Char(string="Api Version Year")

    @api.model
    def get_shopify_connection_info(self):
        config = self.env['ir.config_parameter'].sudo()
        shopify_instance_id = config.get_param('ts_shopify.shopify_instance_id')

        if not shopify_instance_id:
            raise UserError("Shopify Instance ID is not configured in system settings.")

        shopify_instance = self.env["base.shopify"].sudo().browse(int(shopify_instance_id))

        if not shopify_instance.exists():
            raise UserError("Invalid Shopify Instance ID configured.")

        shop_url = shopify_instance.website_url.strip("/")
        access_token = shopify_instance.shopify_api_token
        api_version = shopify_instance.api_version

        if not shop_url or not access_token:
            raise UserError("Shop URL and API Token are required.")

        return {
            "shop_url": shop_url,
            "access_token": access_token,
            "api_version": api_version,
        }

    @api.model
    def get_shopify_products(self):
        """Fetch all products from Shopify store"""
        for record in self:  # Loop through each record
            record._fetch_and_store_shopify_products()

    def _fetch_and_store_shopify_products(self):
        print('>>>>_fetch_and_store_shopify_products>>>>>>>', self)

        # Get last sync time
        last_sync = self.env["ir.config_parameter"].sudo().get_param("last_shopify_sync_date")
        print('>>>>last_sync>>>>>>>', last_sync)

        if last_sync:
            start_date = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
        else:
            start_date = datetime.now() - timedelta(days=7)  # Default to last 7 days

        end_date = datetime.now()  # New sync time
        print('>>>>end_date>>>>>>>', end_date)

        # Format and encode date for Shopify API
        start_date = start_date.replace(microsecond=0)
        start_date_str = start_date.isoformat() + "Z"
        encoded_date = quote(start_date_str)

        # Shopify API setup
        all_products = []
        headers = {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": "your_access_token_here"  # ← Replace this with your actual token
        }
        shop_url = "https://your-store.myshopify.com"  # ← Replace this with your real store
        next_page_url = f"{shop_url}/admin/api/2023-07/products.json?updated_at_min={encoded_date}"
        print('>>>>next_page_url>>>>>>>', next_page_url)

        # Fetch paginated products
        while next_page_url:
            response = requests.get(next_page_url, headers=headers)
            print('>>>>response status>>>>>>>', response.status_code)

            if response.status_code == 401:
                data = response.json()
                print('>>>>data>>>>>>>', data)

                all_products.extend(data.get("products", []))

                # Handle pagination
                next_page_url = None  # Reset
                link_header = response.headers.get("Link")
                print('>>>>link_header>>>>>>>', link_header)
                if link_header:
                    links = link_header.split(",")
                    print('>>>>links>>>>>>>', links)

                    for link in links:
                        if 'rel="next"' in link:
                            next_page_url = link.split(";")[0].strip()[1:-1]  # Clean <url>
                            print('>>>>next_page_url>>>>>>>', next_page_url)
            else:
                raise UserError(f"Error {response.status_code}: {response.text}")

        # Process and store products in Odoo
        self._create_odoo_products(all_products)
        print('>>>>_create_odoo_products called>>>>>>>')

        # Save sync time
        self.env["ir.config_parameter"].sudo().set_param(
            "last_shopify_sync_date", end_date.strftime("%Y-%m-%d %H:%M:%S")
        )

    # def _fetch_and_store_shopify_products(self):
    #     print('>>>>_fetch_and_store_shopify_products>>>>>>>',self)
    #     """Fetch all products from Shopify store"""
    #     """
    #                    Fetch data from a Shopify API endpoint.
    #                    :param resource_path: API resource path, e.g., 'products.json'
    #                    :return: Parsed JSON response
    #                    """
    #
    #     last_sync = self.env["ir.config_parameter"].sudo().get_param("last_shopify_sync_date")
    #     print('>>>>last_sync>>>>>>>',last_sync)
    #
    #     if last_sync:
    #         start_date = datetime.strptime(last_sync, "%Y-%m-%d %H:%M:%S")
    #     else:
    #         start_date = datetime.now() - timedelta(days=7)  # Default: last 7 days if no sync date
    #     end_date = datetime.now()  # Set new end date as current time
    #     print('>>>>end_date>>>>>>>',end_date)
    #
    #     # Format dates for Shopify API (ISO 8601 format)
    #     start_date_str = start_date.isoformat() + "Z"
    #     # end_date_str = end_date.isoformat() + "Z"
    #
    #     while next_page_url:
    #         response = requests.get(next_page_url, headers=headers)
    #         if response.status_code == 200:
    #             data = response.json()
    #             all_products.extend(data.get("products", []))
    #
    #             # Shopify pagination handling
    #             next_page_url = None
    #             link_header = response.headers.get("Link")
    #             if link_header:
    #                 links = link_header.split(",")
    #                 for link in links:
    #                     if 'rel="next"' in link:
    #                         next_page_url = link.split(";")[0].strip()[1:-1]  # Extract URL
    #         else:
    #             raise UserError(f"Error {response.status_code}: {response.text}")
    #
    #     # Process and store products in Odoo
    #     self._create_odoo_products(all_products)
    #
    #     self.env["ir.config_parameter"].sudo().set_param(
    #         "last_shopify_sync_date", end_date.strftime("%Y-%m-%d %H:%M:%S")
    #     )


    # def _create_odoo_products(self,products):
    #     ProductTemplate = self.env["shopify.product"]
    #     ProductVariant = self.env["shopify.product.varient"]
    #
    #     for product in products:
    #         # Extract basic product data
    #         product_vals = {
    #             "name": product.get("title"),
    #             "shopify_id": product.get("id"),
    #             'description':product.get("body_html"),
    #             "vendor":product.get("vendor"),
    #             "product_type": product.get("product_type"),
    #             "tags": product.get("tags"),
    #             "list_price": product.get("variants")[0].get("price") if product.get("variants") else 0.0,
    #             "image_1920": self._get_image(product.get("image")),  # Convert image
    #         }
    #
    #         # Check if product already exists in Odoo
    #         existing_product = ProductTemplate.search([("shopify_id", "=", product_vals["shopify_id"])], limit=1)
    #         if existing_product:
    #             existing_product.write(product_vals)
    #             product_record = existing_product
    #         else:
    #             product_record = ProductTemplate.create(product_vals)
    #
    #         for variant in product.get("variants", []):
    #             variant_vals = {
    #                 "product_tmplt_id": product_record.id,  # Ensure this is a Many2one reference
    #                 # "shopify_product_id": product_record.id,  # Ensure proper linking
    #                 "shopify_variant_id": variant.get("id"),
    #                 "default_code": variant.get("sku"),
    #                 "list_price": variant.get("price"),
    #                 "shopify_inventory": variant.get("inventory_quantity"),
    #                 "weight":variant.get("weight"),
    #                 "weight_unit":variant.get("weight_unit"),
    #                 "barcode":variant.get("barcode"),
    #                 "cost_per_item":variant.get("cost"),
    #
    #             }
    #
    #             # Check if variant exists
    #             existing_variant = ProductVariant.search(
    #                 [("shopify_variant_id", "=", variant_vals["shopify_variant_id"])], limit=1
    #             )
    #             if existing_variant:
    #                 existing_variant.write(variant_vals)
    #             else:
    #                 ProductVariant.create(variant_vals)
    #
    # def _get_image(self, image_data):
    #     """Convert Shopify image URL to base64 for Odoo storage."""
    #     if image_data and image_data.get("src"):
    #         try:
    #             response = requests.get(image_data.get("src"))
    #             if response.status_code == 200:
    #                 return base64.b64encode(response.content)
    #         except:
    #             return False
    #     return False




    def _create_odoo_products(self, products):
        ProductTemplate = self.env["shopify.product"]
        ProductVariant = self.env["shopify.product.varient"]
        ProductAttribute = self.env["shopify.product.attribute"]
        ProductAttributeValue = self.env["shopify.product.attribute.value"]

        for product in products:
            # Extract basic product data
            product_vals = {
                "name": product.get("title"),
                "shopify_id": product.get("id"),
                "description": product.get("body_html"),
                "vendor": product.get("vendor"),
                "product_type": product.get("product_type"),
                "tags": product.get("tags"),
                "list_price": product.get("variants")[0].get("price") if product.get("variants") else 0.0,
                "image_1920": self._get_image(product.get("image")),
                'status': product.get('status')# Convert image
            }

            # Check if product already exists in Odoo
            existing_product = ProductTemplate.search([("shopify_id", "=", product_vals["shopify_id"])], limit=1)
            if existing_product:
                existing_product.write(product_vals)
                product_record = existing_product
            else:
                product_record = ProductTemplate.create(product_vals)

            # Process product attributes
            attribute_ids = []
            for option in product.get("options", []):
                attribute_vals = {
                    "name": option.get("name"),
                    "shopify_id": option.get("id"),
                    "product_id": product_record.id,  # Link attribute to product
                }

                # Check if attribute exists
                existing_attribute = ProductAttribute.search([("shopify_id", "=", attribute_vals["shopify_id"])],
                                                             limit=1)
                if existing_attribute:
                    existing_attribute.write(attribute_vals)
                    attribute_record = existing_attribute
                else:
                    attribute_record = ProductAttribute.create(attribute_vals)

                attribute_ids.append(attribute_record.id)

                # Process attribute values
                for value in option.get("values", []):
                    value_vals = {
                        "name": value,
                        "attribute_id": attribute_record.id,
                    }

                    # Check if value exists
                    existing_value = ProductAttributeValue.search(
                        [("name", "=", value), ("attribute_id", "=", attribute_record.id)], limit=1
                    )
                    if existing_value:
                        existing_value.write(value_vals)
                    else:
                        ProductAttributeValue.create(value_vals)

            # Update the product with attributes
            product_record.write({"attribute_ids": [(6, 0, attribute_ids)]})

            # Process product variants
            # Process product variants
            for variant in product.get("variants", []):
                variant_vals = {
                    "product_tmplt_id": product_record.id,
                    "shopify_variant_id": variant.get("id"),
                    "default_code": variant.get("sku"),
                    "list_price": variant.get("price"),
                    "shopify_inventory": variant.get("inventory_quantity"),
                    "weight": variant.get("weight"),
                    "weight_unit": variant.get("weight_unit"),
                    "barcode": variant.get("barcode"),
                    "cost_per_item": variant.get("cost"),
                }

                # Create or update the variant
                existing_variant = ProductVariant.search(
                    [("shopify_variant_id", "=", variant_vals["shopify_variant_id"])], limit=1
                )
                if existing_variant:
                    existing_variant.write(variant_vals)
                    variant_record = existing_variant
                else:
                    variant_record = ProductVariant.create(variant_vals)

                # Map attribute values to this variant
                variant_attr_values = []

                for idx, option_name in enumerate(["option1", "option2", "option3"]):
                    value_name = variant.get(option_name)
                    if not value_name:
                        continue
                    # Get corresponding attribute name
                    if idx < len(product.get("options", [])):
                        attribute_name = product["options"][idx]["name"]

                        # Find the attribute
                        attribute = ProductAttribute.search(
                            [("name", "=", attribute_name), ("product_id", "=", product_record.id)], limit=1)
                        if not attribute:
                            continue

                        # Find the attribute value
                        attr_value = ProductAttributeValue.search([
                            ("name", "=", value_name),
                            ("attribute_id", "=", attribute.id)
                        ], limit=1)

                        if attr_value:
                            variant_attr_values.append(attr_value.id)

                # Update the variant with attribute values
                variant_record.write({"attribute_value_ids": [(6, 0, variant_attr_values)]})

            # for variant in product.get("variants", []):
            #     variant_vals = {
            #         "product_tmplt_id": product_record.id,  # Ensure this is a Many2one reference
            #         "shopify_variant_id": variant.get("id"),
            #         "default_code": variant.get("sku"),
            #         "list_price": variant.get("price"),
            #         "shopify_inventory": variant.get("inventory_quantity"),
            #         "weight": variant.get("weight"),
            #         "weight_unit": variant.get("weight_unit"),
            #         "barcode": variant.get("barcode"),
            #         "cost_per_item": variant.get("cost"),
            #     }
            #
            #     # Check if variant exists
            #     existing_variant = ProductVariant.search(
            #         [("shopify_variant_id", "=", variant_vals["shopify_variant_id"])], limit=1
            #     )
            #     if existing_variant:
            #         existing_variant.write(variant_vals)
            #     else:
            #         ProductVariant.create(variant_vals)

    def _get_image(self, image_data):
        """Convert Shopify image URL to base64 for Odoo storage."""
        if image_data and image_data.get("src"):
            try:
                response = requests.get(image_data.get("src"))
                if response.status_code == 200:
                    return base64.b64encode(response.content)
            except:
                return False
        return False


