# -*- coding: utf-8 -*-
import logging
import json
from odoo import models, fields, _
# from ..tools.shopify_api_v2 import ShopifyApi
from odoo.exceptions import ValidationError

class ShopifyInstance(models.Model):
    _name = 'shopify.instance'
    _description = 'Shopify Instances'

    name = fields.Char(string="Instance Name", required=True)
    api_key = fields.Char(string="API Key", required=True)
    password = fields.Char(string="Password")
    api_version = fields.Char(string="API Version", required=True)
    shop_url = fields.Char(string="Shop URL")
    is_active = fields.Boolean(string="Active")
    is_authenticate = fields.Boolean(string="Authenticated", default=False)
    dashboard_graph_data = fields.Text(compute='_kanban_dashboard_graph')
    active = fields.Boolean(string='Active', default=True)
    is_import_scheduler = fields.Boolean(string='Import Scheduler', default=False)


    def button_test_connection(self):
        print('>>>>>>button_test_connection>>>>>>>>>>>>>',self)
        response = ShopifyApi(self)._test_connection()
        # print('>>>>>>response>>>>>>>>>>>>>',response)
        if isinstance(response, dict):
            if response.get('error'):
                self.is_authenticate = False
            # raise ValidationError(_(error_message))
        else:
            self.is_authenticate = True