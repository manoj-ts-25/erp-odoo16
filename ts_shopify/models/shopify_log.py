from odoo import models, fields, api



class ShopifySyncLog(models.Model):
    _name = 'shopify.sync.log'
    _description = 'Shopify Failed Sync Log'

    name = fields.Char("Product Name")
    variant_id = fields.Many2one('shopify.product.varient', string="Variant")  # Replace with your actual variant model
    default_code = fields.Char("SKU")
    shopify_variant_id = fields.Char("Shopify Variant ID")
    failure_reason = fields.Text("Failure Reason")
    sync_date = fields.Datetime("Sync Date", default=fields.Datetime.now)