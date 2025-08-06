from odoo import api, fields, models,_

class ResPartner(models.Model):
    _inherit='res.partner'

    is_parent = fields.Boolean(string='Is Parent', compute='_compute_is_parent', store=True, index=True)


    def _compute_is_parent(self):
        for partner in self:
            partner.is_parent = not  partner.parent_id


    def open_child_view(self):
        self.ensure_one()
        ctx= {
            'default_child_ids': self.child_ids.ids,
        }
        return {
            'name': ('Child Contacts'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'child.contacts',
            'view_id': self.env.ref('customer_hierachy_chart.child_contacts_form_views').id,
            'target': 'new',
            'context': ctx,
        }