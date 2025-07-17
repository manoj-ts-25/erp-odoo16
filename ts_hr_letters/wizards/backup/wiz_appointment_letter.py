from odoo import models,fields,api, _
from odoo.exceptions import UserError
import base64


class WizSalaryStructure(models.TransientModel):
    _name = "wiz.salary.structure"
    _description = "Salary Structure"

    def _get_default_wage(self):
        """Get default wage for appointment letter"""
        active_id = self.env.context.get('active_id')
        if active_id:
            employee = self.env['hr.employee'].browse(active_id)
            if employee:
                active_contract = employee.contract_ids.filtered(lambda contract: contract.state == 'open' and contract.date_end >= fields.Date.today())
                if active_contract:
                    return int(active_contract[0].wage) if active_contract[0].wage else 0
                else:
                    return ''

    name = fields.Char(string="Basic", compute="_compute_basic_hra", readonly=False)
    hra = fields.Char(string="HRA")
    ca = fields.Char(string="Conveyance Allowance")
    sa = fields.Char(string="Special Allowance")
    gratuity = fields.Char(string="Gratuity")
    retention = fields.Char(string="Retention")
    pf = fields.Char(string="PF")
    esi = fields.Char(string="ESI")
    tds = fields.Char(string="TDS")
    gross = fields.Char(string="Gross Salary")
    professional_tax = fields.Char(string="Professional Tax")
    wage = fields.Char(string="Wage", default=lambda self: self._get_default_wage())
    net_pay = fields.Char(string="Net Pay")
    employee_id = fields.Many2one("hr.employee", string="Employee", default=lambda self: self.env.context.get('active_id'))
    display_salary_table = fields.Boolean(string="Display Salary Table", default=True)
    pf_eligible = fields.Boolean(string="Eligible PF", default=True)
    gratuity_eligible = fields.Boolean(string="Eligible Gratuity", default=True)
    master_net_pay = fields.Char(string="Master Net Pay")

    @api.depends('wage', 'retention', 'tds', 'esi', 'professional_tax', 'pf_eligible', 'gratuity_eligible')
    def _compute_basic_hra(self):
        for record in self:
            if record.wage:
                wage_value = float(record.wage)
                basic = int(wage_value * 0.50)  # 50% of wage
                record.name = basic
                hra = int(basic * 0.50)  # 50% of basic
                record.hra = hra
                record.ca = int(1600)
                total_deductions = basic + hra + int(record.ca)
                record.sa = int(wage_value - total_deductions)

                if record.gratuity_eligible:
                    gratuity = int(basic * 0.0481)  # 4.81% of basic
                    record.gratuity = gratuity
                else:
                    record.gratuity = 0  # Set gratuity to 0 if not eligible

                # If eligible for PF
                if record.pf_eligible:
                    pf = min(int(basic * 0.24), 3600)  # 24% of basic or 3600, whichever is lower
                    record.pf = pf
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + pf + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)
                else:
                    record.pf = 0  # Set PF to 0 if not eligible
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)

                # If wage is below 21000 for ESI calculation
                if wage_value <= 21000:
                    esi = float(record.net_pay) * .04  # 4% of net pay
                    record.esi = int(esi)
                    print('ESI: ', record.esi)

                record.master_net_pay = int(record.net_pay) - int(record.esi)
            else:
                record.name = ""
                record.hra = ""
                record.ca = ""
                record.sa = ""
                record.pf = ""
                record.gross = ""
                record.net_pay = ""
                record.tds = ""
                record.esi = ""
                record.retention = ""
                record.professional_tax = ""
                record.master_net_pay = ""

    def confirm(self):
        try:
            action = self.action_appointment_letter()
            return action
        except UserError as e:
            raise UserError(e)

    def action_appointment_letter(self):
        template_id = self.env.ref('ts_hr_letters.email_template_appointment_letter').id
        compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        template = self.env['mail.template'].browse(template_id)

        # Render the appointment letter report and create an attachment
        appointment_report = self.env.ref('ts_hr_letters.action_appointment_letter_report_wiz')
        data_record = base64.b64encode(self.env['ir.actions.report'].sudo()._render_qweb_pdf(appointment_report, [self.id], data=None)[0])
        employee_name = self.employee_id.name
        report_name = 'Appointment Letter - %s' % employee_name
        ir_values = {
            'name': report_name,
            'type': 'binary',
            'datas': data_record,
            'store_fname': data_record,
            'mimetype': 'application/pdf',
            'res_model': 'wiz.salary.structure',
        }
        appointment_report_attachment = self.env['ir.attachment'].sudo().create(ir_values)

        # Compose the email using the mail template
        ctx = {
            'default_model': 'wiz.salary.structure',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "mail.mail_notification_paynow",
            'force_email': False,
            'default_attachment_ids': [(4, appointment_report_attachment.id)]
        }
        return {
            'name': 'Appointment Letter Mail',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }


class WizAppraisalLetter(models.TransientModel):
    _name = "wiz.appraisal.letter"
    _description = "Appraisal Letter"

    def _get_default_wage(self):
        """Get default wage for appraisal letter"""
        active_id = self.env.context.get('active_id')
        if active_id:
            employee = self.env['hr.employee'].browse(active_id)
            if employee:
                active_contract = employee.contract_ids.filtered(lambda contract: contract.state == 'open' and contract.date_end >= fields.Date.today())
                if active_contract:
                    return int(active_contract[0].wage) if active_contract[0].wage else 0
                else:
                    return ''

    # def _get_default_wage(self):
    #     active_id = self.env.context.get('active_id')
    #     if active_id:
    #         employee = self.env['hr.employee'].browse(active_id)
    #         if employee:
    #             wage = employee.contract_ids.wage if employee.contract_ids else ''
    #             return int(float(wage)) if wage else 0
    #     return 0

    basic = fields.Char(string="Basic", compute="_compute_salary_calculation", readonly=False)
    hra = fields.Char(string="HRA")
    ca = fields.Char(string="Conveyance Allowance")
    sa = fields.Char(string="Special Allowance")
    gratuity = fields.Char(string="Gratuity")
    retention = fields.Char(string="Retention")
    pf = fields.Char(string="PF")
    esi = fields.Char(string="ESI")
    tds = fields.Char(string="TDS")
    gross = fields.Char(string="Gross Salary")
    professional_tax = fields.Char(string="Professional Tax")
    wage = fields.Char(string="Wage", default=lambda self: self._get_default_wage())
    net_pay = fields.Char(string="Net Pay")
    employee_id = fields.Many2one("hr.employee", string="Employee", default=lambda self: self.env.context.get('active_id'))
    display_salary_table = fields.Boolean(string="Display Salary Table", default=True)
    pf_eligible = fields.Boolean(string="Eligible PF", default=True)
    gratuity_eligible = fields.Boolean(string="Eligible Gratuity", default=True)
    master_net_pay = fields.Char(string="Master Net Pay")

    @api.depends('wage', 'retention', 'tds', 'esi', 'professional_tax', 'pf_eligible', 'gratuity_eligible')
    def _compute_salary_calculation(self):
        for record in self:
            if record.wage:
                wage_value = float(record.wage)
                basic = int(wage_value * 0.50)  # 50% of wage
                record.basic = basic
                hra = int(basic * 0.50)  # 50% of basic
                record.hra = hra
                record.ca = int(1600)
                total_deductions = basic + hra + int(record.ca)
                record.sa = int(wage_value - total_deductions)

                if record.gratuity_eligible:
                    gratuity = int(basic * 0.0481)  # 4.81% of basic
                    record.gratuity = gratuity
                else:
                    record.gratuity = 0  # Set gratuity to 0 if not eligible

                # If eligible for PF
                if record.pf_eligible:
                    pf = min(int(basic * 0.24), 3600)  # 24% of basic or 3600, whichever is lower
                    record.pf = pf
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + pf + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)
                else:
                    record.pf = 0  # Set PF to 0 if not eligible
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)

                # If wage is below 21000 for ESI calculation
                if wage_value <= 21000:
                    esi = float(record.net_pay) * .04  # 4% of net pay
                    record.esi = int(esi)

                record.master_net_pay = int(record.net_pay) - int(record.esi)
            else:
                record.basic = ""
                record.hra = ""
                record.ca = ""
                record.sa = ""
                record.pf = ""
                record.gross = ""
                record.net_pay = ""
                record.tds = ""
                record.esi = ""
                record.retention = ""
                record.professional_tax = ""
                record.master_net_pay = ""

    def action_appraisal_letter(self):
        template_id = self.env.ref('ts_hr_letters.email_template_appraisal_letter').id
        compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        template = self.env['mail.template'].browse(template_id)

        appraisal_report = self.env.ref('ts_hr_letters.action_appraisal_letter_report_id')
        data_record = base64.b64encode(self.env['ir.actions.report'].sudo()._render_qweb_pdf(appraisal_report, [self.id], data=None)[0])
        employee_name = self.employee_id.name
        report_name = 'Appraisal Letter - %s' % employee_name
        ir_values = {
            'name': report_name,
            'type': 'binary',
            'datas': data_record,
            'store_fname': data_record,
            'mimetype': 'application/pdf',
            'res_model': 'wiz.appraisal.letter',
        }
        appraisal_report_attachment_id = self.env['ir.attachment'].sudo().create(ir_values)
        ctx = {
            'default_model': 'wiz.appraisal.letter',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "mail.mail_notification_paynow",
            'force_email': False,
            'default_attachment_ids': [(4, appraisal_report_attachment_id.id)]
        }
        return {
            'name': 'Appraisal Letter Mail',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }


class WizOfferLetter(models.TransientModel):
    _name = "wizard.offer.letter"
    _description = "Offer Letter"

    def _get_default_wage(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            applicant = self.env['hr.applicant'].browse(active_id)
            if applicant:
                wage = applicant.salary_proposed if applicant.salary_proposed else ''
                return int(float(wage)) if wage else 0
        return 0

    wage = fields.Char(string="Wage", default=lambda self: self._get_default_wage())
    basic = fields.Char(string="Basic", compute="_compute_salary_calculation", readonly=False)
    hra = fields.Char(string="HRA")
    ca = fields.Char(string="Conveyance Allowance")
    sa = fields.Char(string="Special Allowance")
    gratuity = fields.Char(string="Gratuity")
    retention = fields.Char(string="Retention")
    pf = fields.Char(string="PF")
    esi = fields.Char(string="ESI")
    tds = fields.Char(string="TDS")
    gross = fields.Char(string="Gross Salary")
    professional_tax = fields.Char(string="Professional Tax")
    net_pay = fields.Char(string="Net Pay")
    application_id = fields.Many2one("hr.applicant", string="Application", default=lambda self: self.env.context.get('active_id'))
    display_salary_table = fields.Boolean(string="Display Salary Table", default=True)
    pf_eligible = fields.Boolean(string="Eligible PF", default=True)
    gratuity_eligible = fields.Boolean(string="Eligible Gratuity", default=True)
    master_net_pay = fields.Char(string="Master Net Pay")

    @api.depends('wage', 'retention', 'tds', 'esi', 'professional_tax', 'pf_eligible', 'gratuity_eligible')
    def _compute_salary_calculation(self):
        for record in self:
            if record.wage:
                wage_value = float(record.wage)
                basic = int(wage_value * 0.50)  # 50% of wage
                record.basic = basic
                hra = int(basic * 0.50)  # 50% of basic
                record.hra = hra
                record.ca = int(1600)
                total_deductions = basic + hra + int(record.ca)
                record.sa = int(wage_value - total_deductions)

                if record.gratuity_eligible:
                    gratuity = int(basic * 0.0481)  # 4.81% of basic
                    record.gratuity = gratuity
                else:
                    record.gratuity = 0  # Set gratuity to 0 if not eligible

                # If eligible for PF
                if record.pf_eligible:
                    pf = min(int(basic * 0.24), 3600)  # 24% of basic or 3600, whichever is lower
                    record.pf = pf
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + pf + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)
                else:
                    record.pf = 0  # Set PF to 0 if not eligible
                    total_gross = basic + hra + int(record.ca) + int(record.sa)
                    record.gross = int(total_gross)

                    total_net_pay = (int(record.gratuity) + int(record.retention or 0) + int(record.tds or 0) +
                                     int(record.professional_tax or 0))
                    record.net_pay = int(int(record.gross) - total_net_pay)

                # If wage is below 21000 for ESI calculation
                if wage_value <= 21000:
                    esi = float(record.net_pay) * .04  # 4% of net pay
                    record.esi = int(esi)

                record.master_net_pay = int(record.net_pay) - int(record.esi)
            else:
                record.basic = ""
                record.hra = ""
                record.ca = ""
                record.sa = ""
                record.pf = ""
                record.gross = ""
                record.net_pay = ""
                record.tds = ""
                record.esi = ""
                record.retention = ""
                record.professional_tax = ""
                record.master_net_pay = ""

    def action_offer_letter(self):
        template_id = self.env.ref('ts_hr_letters.email_template_offer_letter').id
        compose_form_id = self.env.ref('mail.email_compose_message_wizard_form').id
        template = self.env['mail.template'].browse(template_id)
        offer_letter_rpt_id = self.env.ref('ts_hr_letters.action_offer_letter_report_id')
        data_record = base64.b64encode(self.env['ir.actions.report'].sudo()._render_qweb_pdf(offer_letter_rpt_id, [self.id], data=None)[0])
        employee_name = self.application_id.partner_name
        report_name = 'Offer Letter - %s' % employee_name
        ir_values = {
            'name': report_name,
            'type': 'binary',
            'datas': data_record,
            'store_fname': data_record,
            'mimetype': 'application/pdf',
            'res_model': 'hr.applicant',
        }
        offer_letter_rpt_attachment_id = self.env['ir.attachment'].sudo().create(ir_values)
        ctx = {
            'default_model': 'wizard.offer.letter',
            'default_res_id': self.id,
            'default_use_template': bool(template_id),
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'custom_layout': "mail.mail_notification_paynow",
            'force_email': False,
            'default_attachment_ids': [(4, offer_letter_rpt_attachment_id.id)]
        }
        return {
            'name': 'Offer Letter Mail',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(compose_form_id, 'form')],
            'view_id': compose_form_id,
            'target': 'new',
            'context': ctx,
        }