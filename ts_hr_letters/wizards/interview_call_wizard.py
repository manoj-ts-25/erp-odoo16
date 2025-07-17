from odoo import models, fields, api
from odoo.exceptions import ValidationError
import pytz

from odoo.exceptions import UserError


class InterviewCallWizard(models.TransientModel):
    _name = "interview.call.wizard"
    _description = "Interview Call Letter wizard"

    applicant_id = fields.Many2one('hr.applicant', string='Recipient', required=True)
    subject = fields.Char(string='Subject', required=True)
    interview_time = fields.Datetime(string='Interview Time', required=True)
    body = fields.Html('Email', default='')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')

    @api.onchange('interview_time')
    def _onchange_interview_time(self):
        time = self.interview_time
        if time:
            user_tz = pytz.timezone(self.env.user.tz or 'Asia/Kolkata')
            utc_time = pytz.utc.localize(time)
            local_time = utc_time.astimezone(user_tz)
            time_str = local_time.strftime('%d %B, %Y %I:%M %p')
            # venue = self.applicant_id.job_id.address_id.contact_address if self.applicant_id.job_id.address_id else self.env.company.partner_id.contact_address
            body = f"""
                        Hi <span style=" font-weight: bold;">{self.applicant_id.partner_name}</span>,
                        <br/><br/>
                        <span >I hope this email finds you in great spirits.</span>
                        <br/>
                        <br/>
                        Your application for the role of <span style="font-weight: bold;">{self.applicant_id.job_id.name}</span> at <span  style="font-weight: bold;">{self.env.company.name}</span> has truly impressed us,
                        and we’re excited to invite you for a conversation. This discussion is an opportunity to explore your aspirations, share insights about our organization, and discuss how your expertise aligns with our goals.<br/><br/>
                        <span style="font-weight: bold;"> Discussion Details:</span>
                        <br/><br/>
                        <strong> Date & Time:</strong> <u>{time_str}</u>
                        <br/>
                        <strong> Venue: </strong><u>Technians Softech Pvt Ltd</u><br/>            <u>1101, 11th Floor, Welldone Techpark,</u><br/>            <u>Sohna Road, Sector 48 Gurugram</u>
                        <br/>
                        <strong> Location Map:</strong> <u>https://g.co/kgs/DfLMTPX</u>
                        <br/><br/>
                        <span>To confirm your availability, please reply to this email or contact us at</span> <span style="font-weight: bold;">+91-9716418899.</span>
                        <br/><br/>
                        <span>To make the most of our meeting, we recommend familiarizing yourself with our company’s website and profile. Also, please bring along a hard copy of your resume and any other relevant documents supporting your qualifications.</span>
                        <br/><br/>
                        <span>At <span  style="font-weight: bold;">{self.env.company.name}</span>, we are committed to excellence, innovation, and creating a culture that nurtures growth and collaboration.</span>
                        <br/><br/>
                        <span>Joining <span  style="font-weight: bold;">{self.env.company.name}</span> isn’t just about a role—it’s about being part of something meaningful, working with like-minded professionals, and building a brighter future together.</span>
                        <br/><br/>
                        <span>We’re looking forward to meeting you and exploring this exciting opportunity!</span>
                        <br/><br/>
                        <span>Best regards</span>
                        <br/><br/>
                        <span style="font-weight: bold;"><h5 class="mb-1">{self.env.user.signature}</h5></span></span>            
                    """
            self.body = body

    def send_interview_call_letter(self):
        if not self.applicant_id or not self.interview_time or not self.body or not self.subject:
            raise UserError("Please Enter all the Values, before Sending Email!!")
        mail_values = {
            'subject': self.subject,
            'body_html': self.body,
            'email_from': 'erp@dev.technians.com',
            'email_to': self.applicant_id.email_from,
            'model': 'hr.applicant',
            'res_id': self.applicant_id.id,
            'attachment_ids': [(6, 0, self.attachment_ids.ids)] if self.attachment_ids.ids else [],
        }

        mail = self.env['mail.mail'].sudo().create(mail_values)

        try:
            mail.sudo().send(raise_exception=True)

            self.applicant_id.sudo().message_post(
                body=f"Email sent successfully<br/><br/>Subject: {self.subject}<br/><br/>{self.body}<br/>",
                message_type="comment"
            )

        except Exception as e:
            raise ValidationError(f"Failed to send email: {str(e)}")
