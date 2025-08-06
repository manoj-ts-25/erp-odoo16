from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShopifyOperation(models.Model):
    _name = 'shopify.operation'

    shopify_instance_id = fields.Many2one('base.shopify', string="Shopify Instance",
                                          default=lambda self: self._get_default_shopify_instance())
    operation = fields.Selection([('import_order', '🛒 Import Order'),
                                ('import_product', '📦 Import Product'),
                                ('import_cancel_order','❌ Import Cancel Order'),
                                ('import_stock',' 🔄 Import Product Stock'),
                                ('import_customer',' 🙍 Import Customer')],string="Import Operation")

    export_operation = fields.Selection([('export_product', ' 📤 Export Product')], string="Export Operation")


    @api.model
    def _get_default_shopify_instance(self):
        """Fetch default Shopify Instance from res.config.settings"""
        shopify_instance_id = self.env["ir.config_parameter"].sudo().get_param("ts_shopify.shopify_instance_id")
        return int(shopify_instance_id) if shopify_instance_id else False





    def execute_operation(self):
        if self.operation == 'import_order':
            self.env['shopify.order'].fetch_shopify_orders()
        elif self.operation == 'import_product':
            self.env['base.shopify']._fetch_and_store_shopify_products()
        elif self.operation == 'import_cancel_order':
            self.env['shopify.cancel.order']._fetch_cancel_order()
        elif self.operation == "import_stock":
            self.env['base.shopify'].import_shopify_stock_to_odoo()
        elif self.operation == 'import_customer':
            self.env['customer.shopify']._fetch_customer_details()
        elif self.export_operation == 'export_product':
            self.env['shopify.product'].create_shopify_product()
        else:
            raise UserError("Invalid operation selected!")

