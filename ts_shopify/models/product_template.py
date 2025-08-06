import base64

from odoo import models, fields, api
import requests
import json



class ProductTemplate(models.Model):
    _inherit = 'product.template'

    shopify_id = fields.Char(string="Shopify Id")
    description_sale = fields.Html(string="Product Description")




class ProductProduct(models.Model):
    _inherit = 'product.product'

    shopify_variant_id = fields.Char(string="Shopify Variant Id")








