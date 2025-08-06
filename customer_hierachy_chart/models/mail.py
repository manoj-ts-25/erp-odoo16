from odoo import models, fields, api

class MailMessage(models.Model):
    _inherit = 'mail.message'

    email_status_color = fields.Selection([
        ('green', 'Full Delivery'),
        ('orange', 'Partial Delivery'),
        ('red', 'Failed')
    ], string='Email Delivery Color', compute='_compute_email_status_color')

    @api.depends('mail_ids.state')
    def _compute_email_status_color(self):
        for msg in self:
            states = msg.mail_ids.mapped('state')
            if not states:
                msg.email_status_color = False
            elif all(state == 'sent' for state in states):
                msg.email_status_color = 'green'
            elif all(state == 'exception' for state in states):
                msg.email_status_color = 'red'
            elif any(state == 'exception' for state in states):
                msg.email_status_color = 'orange'
            else:
                msg.email_status_color = False
