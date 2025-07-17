from odoo import models, fields, api
from odoo.exceptions import UserError
import base64

class SendJoiningEmail(models.TransientModel):
    _name = "send.joining.email.wizard"
    _description = "Send Joining Email Wizard"

    partner_name = fields.Char(string='Applicant Name')
    email_from = fields.Char(string='Email')
    email_cc = fields.Char(string='Email CC')
    to_email = fields.Char(string='Recipient Email')
    model = fields.Char('Related Document Model')
    subject = fields.Char(string='Subject')
    body_html = fields.Html(string='Body')
    applicant_id = fields.Many2one('hr.applicant')
    template_id = fields.Many2one('mail.template', string="Mail Template",
                domain=lambda self: [('model', '=', self.env.context.get('default_model'))])
    attachment_ids = fields.Many2many('ir.attachment', string="Attachments")

    def send_confirm_letter(self):
        self.ensure_one()
        model = self.model or self.env.context.get('active_model')
        if not model:
            raise ValueError("The related model is not specified.")
        record_id = self.env.context.get('active_id')
        if not record_id:
            raise ValueError("No related record found for sending email.")
        record = self.env[model].browse(record_id)
        if not record.exists():
            raise ValueError("The related record no longer exists.")
        if not self.template_id:
            raise ValueError("Please select an email template.")

        # Step 2: Generate email values
        email_values = self.template_id.generate_email(
            record.id,
            ['subject', 'body_html', 'email_from']
        )

        email_values['email_to'] = self.email_from

        mail = self.env['mail.mail'].sudo().create({
            'subject': email_values['subject'],
            'body_html': email_values['body_html'],
            'email_from': email_values['email_from'],
            'email_to': email_values['email_to'],
            'model': model,
            'res_id': record.id,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })

        mail.send()
        record.message_post(
            body=email_values['body_html'],
            subject=email_values['subject'],
            message_type='email',
            attachment_ids=self.attachment_ids.ids,
        )
        return {'type': 'ir.actions.act_window_close'}


    @api.onchange('template_id')
    def _onchange_template_id(self):
        """
        Update the subject and body fields when the template is changed.
        """
        if self.template_id:
            self.subject = self.template_id.subject
            self.body_html = self.template_id.body_html
        else:
            self.subject = ''
            self.body_html = ''