from odoo import api, fields, models, _
from ast import literal_eval

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    external_letter_layout_id = fields.Many2one('ir.ui.view', readonly=False,relation_table='ts_external_layout_rel',
                                                string="External Letter Layout")
                                                
    country_id = fields.Many2one("res.country", string="Country")

    resignation_cum_experience = fields.Text(string="Resignation cum Experience Letter")
    resignation_acceptance = fields.Text(string="Resignation Acceptance Letter")
    appraisal = fields.Text(string="Appraisal Letter")
    appointment = fields.Text(string="Appointment Letter")
    offer = fields.Text(string="Offer Letter")

    office_attachment_ids = fields.Many2many(comodel_name='ir.attachment', string='Office Attachments')

    def edit_custom_external_header(self):
        if not self.external_letter_layout_id:
            return False

        return {
            'name': 'External Letter Layout View',
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.view',
            'view_mode': 'form',
            'res_id': self.external_letter_layout_id.id,
        }

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        office_attachment_ids = self.env['ir.config_parameter'].sudo().get_param(
            'ts_hr_letters.office_attachment_ids', default=[]
        )
        attachment_ids = literal_eval(
            office_attachment_ids) if office_attachment_ids and office_attachment_ids != 'False' else []

        res.update(
            external_letter_layout_id=int(self.env['ir.config_parameter'].sudo().get_param('ts_hr_letters.external_letter_layout_id', False)),
            country_id=self.env.user.company_id.country_id.id if self.env.user.company_id.country_id else False,
            resignation_cum_experience=self.env['ir.config_parameter'].get_param('ts_hr_letters.resignation_cum_experience', default=''),
            resignation_acceptance=self.env['ir.config_parameter'].get_param('ts_hr_letters.resignation_acceptance',default=''),
            appraisal=self.env['ir.config_parameter'].get_param('ts_hr_letters.appraisal', default=''),
            appointment=self.env['ir.config_parameter'].get_param('ts_hr_letters.appointment', default=''),
            offer=self.env['ir.config_parameter'].get_param('ts_hr_letters.offer', default=''),
            office_attachment_ids=[(6, 0, attachment_ids)] if attachment_ids else False)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        self.env['ir.config_parameter'].set_param('ts_hr_letters.resignation_cum_experience',
                                                  self.resignation_cum_experience)
        self.env['ir.config_parameter'].set_param('ts_hr_letters.resignation_acceptance', self.resignation_acceptance)
        self.env['ir.config_parameter'].set_param('ts_hr_letters.appraisal', self.appraisal)
        self.env['ir.config_parameter'].set_param('ts_hr_letters.appointment', self.appointment)
        self.env['ir.config_parameter'].set_param('ts_hr_letters.offer', self.offer)

        self.env['ir.config_parameter'].sudo().set_param('ts_hr_letters.external_letter_layout_id',
                                                         self.external_letter_layout_id.id or False)
        self.env['ir.config_parameter'].sudo().set_param(
            'ts_hr_letters.office_attachment_ids', str(self.office_attachment_ids.ids or False)
        )

        if self.country_id:
            self.env.user.company_id.country_id = self.country_id.id 
    # @api.model
    # def get_values(self):
    #     res = super(ResConfigSettings, self).get_values()
    #     res.update(external_letter_layout_id=int(self.env['ir.config_parameter'].sudo().get_param('ts_hr_letters.external_letter_layout_id', False)),)
    #     return res
    #
    # def set_values(self):
    #     super(ResConfigSettings, self).set_values()
    #     self.env['ir.config_parameter'].sudo().set_param('ts_hr_letters.external_letter_layout_id', self.external_letter_layout_id.id or False)


    @api.model
    def edit_custom_appointment_letters(self, context=None):
        appointment_email_template = self.env.ref('ts_hr_letters.email_template_appointment_letter',
                                                  raise_if_not_found=False)
        if not appointment_email_template:
            return False

        return {
            'name': 'Appointment Letter Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': appointment_email_template.id,
        }

    @api.model
    def appraisal_letters_edit(self, context=None):
        appraisal_email_template = self.env.ref('ts_hr_letters.email_template_appraisal_letter',
                                                raise_if_not_found=False)
        if not appraisal_email_template:
            return False

        return {
            'name': 'Appraisal Letter Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': appraisal_email_template.id,
        }

    #
    @api.model
    def edit_custom_resignation_letters(self, context=None):
        resignation_email_template = self.env.ref('ts_hr_letters.email_template_resignation_letter',
                                                  raise_if_not_found=False)
        if not resignation_email_template:
            return False

        return {
            'name': 'Resignation Letter Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': resignation_email_template.id,
        }

    @api.model
    def edit_custom_promotion_letters(self, context=None):
        promotion_email_template = self.env.ref('ts_hr_letters.email_template_promotion_letter',
                                                raise_if_not_found=False)
        if not promotion_email_template:
            return False

        return {
            'name': 'Promotion Letter Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': promotion_email_template.id,
        }

    #
    @api.model
    def edit_custom_experience_letter_template(self, context=None):
        experience_letter_template = self.env.ref('ts_hr_letters.email_template_experience_letter',
                                                  raise_if_not_found=False)
        if not experience_letter_template:
            return False

        return {
            'name': 'Experience Letter Mail Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': experience_letter_template.id,
        }

    #
    @api.model
    def edit_joining_letter_mail_template(self, context=None):
        joining_letter_template = self.env.ref('ts_hr_letters.email_template_joining_letter',
                                               raise_if_not_found=False)
        if not joining_letter_template:
            return False

        return {
            'name': 'Joining Letter Mail Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': joining_letter_template.id,
        }

    #
    @api.model
    def edit_send_document_email_template(self, context=None):
        send_document_email_template = self.env.ref('ts_hr_letters.email_template_send_email',
                                                    raise_if_not_found=False)
        if not send_document_email_template:
            return False

        return {
            'name': 'Send Document Email Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': send_document_email_template.id,
        }

    #
    @api.model
    def edit_custom_offer_letter_template(self, context=None):
        offer_letter_template = self.env.ref('ts_hr_letters.email_template_offer_letter', raise_if_not_found=False)
        if not offer_letter_template:
            return False

        return {
            'name': 'Offer Letter Mail Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': offer_letter_template.id,
        }

    @api.model
    def edit_erp_creation_mail_template(self, context=None):
        erp_creation_template = self.env.ref('ts_hr_letters.email_template_erp_creation', raise_if_not_found=False)
        if not erp_creation_template:
            return False
        return {
            'name': 'ERP Creation Mail Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': erp_creation_template.id,
        }

    #
    @api.model
    def edit_mail_creation_template(self, context=None):
        mail_creation_template = self.env.ref('ts_hr_letters.email_template_mail_creation_id',
                                              raise_if_not_found=False)
        if not mail_creation_template:
            return False

        return {
            'name': 'Mail ID Creation Template View',
            'type': 'ir.actions.act_window',
            'res_model': 'mail.template',
            'view_mode': 'form',
            'res_id': mail_creation_template.id,
        }

    # Shitanshu Stop


class ResCompany(models.Model):
    _inherit = "res.company"

    external_letter_layout_id = fields.Many2one('ir.ui.view', 'Letters Template',domain="[('type','=', 'qweb')]")