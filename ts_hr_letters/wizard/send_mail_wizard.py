from odoo import api, fields, models, _



class HrMailWizard(models.TransientModel):
    _name = 'hr.mail.wizard'
    _description = 'HR Mail Wizard'

    applicant_id = fields.Many2one('hr.applicant')
    name = fields.Char()
    template_id = fields.Many2one(
        'mail.template',
        string='Use template',
        domain=lambda self: [('model', '=', self.env.context.get('default_model'))],
    )
    model = fields.Char('Related Document Model')
    subject = fields.Char(string='Subject')
    body_html = fields.Html(string='Body')

    to_email = fields.Char(string='Recipient Email', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment', string='Attachments',
        help="You can attach files to include in the email."
    )

    def send_mail(self):
        self.ensure_one()
        if not self.model:
            self.model = self.env.context.get('active_model')
        if not self.model:
            raise ValueError("The related model is not specified or found in the context.")
        record_id = self.env.context.get('active_id')
        if not record_id:
            raise ValueError("No related record found for sending an email.")
        related_model = self.env[self.model]
        record = related_model.browse(record_id)
        if not record.exists():
            raise ValueError("The related record no longer exists.")
        if not self.template_id:
            raise ValueError("Please select a template before sending an email.")
        email_values = self.template_id.generate_email(
            record.id,  # Record ID
            ['subject', 'body_html', 'email_to']
        )
        email_values['email_to'] = self.to_email
        mail = self.env['mail.mail'].sudo().create({
            'subject': email_values['subject'],
            'body_html': email_values['body_html'],
            'email_to': email_values['email_to'],
            # 'reply_to': email_values['reply_to'],
            'model': 'hr.applicant',
            'res_id': self.applicant_id.id,

            'attachment_ids': [(6, 0, self.attachment_ids.ids)],
        })
        mail.send()
        record.message_post(
            body=email_values['body_html'],
            subject=email_values['subject'],
            message_type='email',
            attachment_ids=self.attachment_ids.ids
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








