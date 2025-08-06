from odoo import api, fields, models,_

class ChildContacts(models.Model):
    _name = 'child.contacts'

    child_ids = fields.Many2many('res.partner',string='Child Contacts')
