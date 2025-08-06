import logging
import base64
import shopify

from odoo import models, fields, api


class ShopifyProduct(models.Model):
    _name = 'shopify.product'
    _description = 'Shopify Product'

    name = fields.Char(string='Name')
    shopify_instance_id = fields.Many2one('shopify.instance', string="Shopify Instance", required=True)
    product_tmpl_id = fields.Many2one('product.template', string="Product Template")
    product_category_id = fields.Many2one('product.category', string="Product Category")
    status = fields.Selection(
        [("publish", "Published"), ("unpublish", "Unpublished")],
        string="Status", default="unpublish")
    is_export = fields.Boolean(string='Exported in Shopify', default=False)
    product_body_html = fields.Html()

    shopify_images = fields.Many2many(comodel_name='shopify.image', string="Shopify Image")
