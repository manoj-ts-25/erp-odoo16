from odoo import models, fields,api,_



class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    last_shopify_sync_date = fields.Datetime("Last Shopify Sync Date",config_parameter='last_shopify_sync_date')
    shopify_instance_id = fields.Many2one('base.shopify', string="Shopify Instance" ,config_parameter='ts_shopify.shopify_instance_id')



    def action_create_shopify_instance(self):
        """Creates a new Shopify instance and links it to the settings."""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'base.shopify',
            'view_mode': 'form',
            'target': 'current',
        }