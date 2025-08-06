import pytz
from datetime import datetime, timedelta
from odoo import models, fields, api, _
import calendar
import logging

_logger = logging.getLogger(__name__)


class EmployeeAttendanceReminder(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def is_holiday_or_weekend(self, date):
        public_holiday = self.env['resource.calendar.leaves'].search([
            ('date_from', '<=', date.strftime('%d-%B-%Y 23:59:59')),
            ('date_to', '>=', date.strftime('%d-%B-%Y 00:00:00'))
        ], limit=1)

        is_weekend = date.weekday() in [calendar.SATURDAY, calendar.SUNDAY]
        return bool(public_holiday) or is_weekend

    def get_previous_working_day(self, today):
        days_offset = 1
        while True:
            previous_day = today - timedelta(days=days_offset)
            if not self.is_holiday_or_weekend(previous_day):
                return previous_day
            days_offset += 1

    def send_missed_attendance_email(self):
        today = fields.Date.today()

        if self.is_holiday_or_weekend(today):
            _logger.info("Today is a holiday or weekend. No emails sent.")
            return

        previous_working_day = self.get_previous_working_day(today)
        subject = "Action Required: Clarification on Missed Punch-In & Out"

        employees = self.search([('active', '=', True), ('is_wfh', '=', False)])
        hr_email = 'career@technians.com'

        for employee in employees:
            attendance_exists = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', datetime.combine(previous_working_day, datetime.min.time())),
                ('check_in', '<', datetime.combine(previous_working_day + timedelta(days=1), datetime.min.time()))
            ], limit=1)

            time_off_exists = self.env['hr.leave'].search([
                ('employee_id', '=', employee.id),
                ('date_from', '<=', datetime.combine(previous_working_day, datetime.max.time())),
                ('date_to', '>=', datetime.combine(previous_working_day, datetime.min.time()))
            ], limit=1)

            if not attendance_exists and not time_off_exists and employee.work_email:
                manager_email = employee.parent_id.work_email if employee.parent_id else None

                body_html = f"""
                    <p>Dear {employee.name},</p>
                    <p>This is a reminder that we noticed a missed punch-in/out for your shift on 
                    <strong>{previous_working_day.strftime('%d-%B-%Y')}</strong>.</p>
                    <p>
                        Kindly provide clarification as to why you were unable to punch in/out, and if there were any 
                        issues that prevented you from doing so.
                    </p>
                    <p>
                        Please note that if we do not receive a response within the next 4 hours, by replying directly 
                        to this email, your absence for {previous_working_day.strftime('%d-%B-%Y')} may be recorded as unexcused.
                    </p>
                """

                cc_recipients = [manager_email] if manager_email else []
                cc_recipients.append(hr_email)

                mail_values = {
                    'subject': subject,
                    'body_html': body_html,

                    'email_to': employee.work_email,
                    'email_cc': ', '.join(cc_recipients) if cc_recipients else None,
                }

                try:
                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()
                    _logger.info(f"Email sent to {employee.name} for missing attendance on {previous_working_day}")
                except Exception as e:
                    _logger.error(f"Failed to send email to {employee.work_email}: {str(e)}")

    def send_missed_punch_in_reminder(self):
        today = fields.Date.today()

        # Check if today is a holiday or weekend
        if self.is_holiday_or_weekend(today):
            _logger.info("Today is a holiday or weekend. No reminders sent.")
            return

        formatted_date = today.strftime('%d-%B-%Y')
        # subject = f"Action Required: Missing Punch-In for {formatted_date}"

        # Get the list of active employees who are not working from home
        employees = self.search([('active', '=', True), ('is_wfh', '=', False)])
        hr_email = 'career@technians.com'
        reminder_time_limit = datetime.strptime('10:31:00', '%H:%M:%S').time()
        local_tz = pytz.timezone('Asia/Kolkata')

        for employee in employees:
            # Check if the employee has any leave records for today
            time_off_exists = self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today),
            ]) > 0

            if time_off_exists:
                continue

            # Check if the employee has punched in today
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today),
                ('check_in', '<', today + timedelta(days=1))
            ], limit=1)

            send_email = False

            # Determine if an email needs to be sent
            if not attendance:
                send_email = True
            elif attendance:
                check_in_utc = fields.Datetime.from_string(attendance.check_in)
                check_in_local = check_in_utc.astimezone(local_tz).time()

                if check_in_local > reminder_time_limit:
                    send_email = True

            # Send the reminder email if required
            if send_email and employee.work_email:
                manager_email = employee.parent_id.work_email if employee.parent_id else None

                subject = f"Action Required: {employee.name}, Missing Punch-In for {formatted_date}"


                body_html = f"""
                        <p>Dear {employee.name},</p>
                        <p>This is a reminder that we noticed a missed punch-in on {formatted_date}. Kindly provide clarification as to why you were unable to punch in, and if there were any issues that prevented you from doing so.</p>
                        <p>Please note that if we do not receive a response with the necessary clarification within the next 4 hours, by replying directly to this email, your half-day absence for {formatted_date} may be recorded as unexcused.</p>
                        <p>We appreciate your prompt attention to this matter. If you have any questions or concerns, feel free to reach out to your reporting manager for assistance.</p>
                    """

                cc_recipients = [manager_email] if manager_email else []
                cc_recipients.append(hr_email)

                mail_values = {
                    'subject': subject,
                    'body_html': body_html,

                    'email_to': employee.work_email,
                    'email_cc': ', '.join(cc_recipients) if cc_recipients else None,
                }
                try:
                    mail = self.env['mail.mail'].create(mail_values)
                    mail.send()
                except Exception as e:
                    _logger.error(f"Failed to send email to {employee.work_email}: {str(e)}")

    # def send_missed_punch_in_reminder(self):
    #     today = fields.Date.today()
    #     if self.is_holiday_or_weekend(today):
    #         return
    #
    #     formatted_date = today.strftime('%d-%B-%Y')
    #
    #     subject = f"Action Required: Missing Punch-In for {formatted_date}"
    #     employees = self.search([('active', '=', True), ('is_wfh', '=', False)])
    #     hr_email = 'career@technians.com'
    #
    #     for employee in employees:
    #         attendance_exists = self.env['hr.attendance'].search_count([
    #             ('employee_id', '=', employee.id),
    #             ('check_in', '>=', today),
    #             ('check_in', '<', today + timedelta(days=1))
    #         ]) > 0
    #
    #         time_off_exists = self.env['hr.leave'].search_count([
    #             ('employee_id', '=', employee.id),
    #             ('date_from', '<=', today),
    #             ('date_to', '>=', today)
    #         ]) > 0
    #
    #         if not attendance_exists and not time_off_exists and employee.work_email:
    #             manager_email = employee.parent_id.work_email if employee.parent_id else None
    #
    #             # formatted_date = today.strftime('%d-%B-%Y')
    #             body_html = f"""
    #                     <p>Dear {employee.name},</p>
    #                     <p>This is a reminder that we noticed a missed punch-in on {formatted_date}. Kindly provide clarification as to why you were unable to punch in, and if there were any issues that prevented you from doing so.</p>
    #                     <p>Please note that if we do not receive a response with the necessary clarification within the next 4 hours, by replying directly to this email, your half-day absence for {formatted_date} may be recorded as unexcused.</p>
    #                     <p>We appreciate your prompt attention to this matter. If you have any questions or concerns, feel free to reach out to your reporting manager for assistance.</p>
    #                 """
    #
    #             cc_recipients = [manager_email] if manager_email else []
    #             cc_recipients.append(hr_email)
    #
    #             mail_values = {
    #                 'subject': subject,
    #                 'body_html': body_html,
    #
    #                 'email_to': employee.work_email,
    #                 'email_cc': ', '.join(cc_recipients) if cc_recipients else None,
    #             }
    #             try:
    #                 mail = self.env['mail.mail'].create(mail_values)
    #                 mail.send()
    #             except Exception as e:
    #                 _logger.error(f"Failed to send email to {employee.work_email}: {str(e)}")

    def send_missed_punch_out_reminder(self):
        today = fields.Date.today()
        if self.is_holiday_or_weekend(today):
            return

        formatted_date = today.strftime('%d-%B-%Y')

        # subject = f"Action Required: Missing Punch-Out for {formatted_date}"
        employees = self.search([('active', '=', True), ('is_wfh', '=', False)])
        hr_email = 'career@technians.com'

        for employee in employees:
            attendance_records = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today),
                ('check_in', '<', today + timedelta(days=1)),
                ('check_out', '!=', False)
            ])

            time_off_exists = self.env['hr.leave'].search_count([
                ('employee_id', '=', employee.id),
                ('date_from', '<=', today),
                ('date_to', '>=', today)
            ]) > 0

            if attendance_records and not time_off_exists:
                for attendance in attendance_records:
                    work_duration = attendance.check_out - attendance.check_in
                    if work_duration < timedelta(hours=8) and employee.work_email:
                        manager_email = employee.parent_id.work_email if employee.parent_id else None

                        subject = f"Action Required: {employee.name}, Missing Punch-Out Alert for {formatted_date}"

                        body_html = f"""
                                <p>Dear {employee.name},</p>
                                <p>This is a reminder that we noticed a missed punch-out on {formatted_date}. Kindly provide clarification as to why you were unable to punch out, and if there were any issues that prevented you from doing so.</p>
                                <p>Please note that if we do not receive a response with the necessary clarification within the next 4 hours, by replying directly to this email, your half-day absence for {formatted_date} may be recorded as unexcused.</p>
                                <p>We appreciate your prompt attention to this matter. If you have any questions or concerns, feel free to reach out to your reporting manager for assistance.</p>
                            """
                        cc_recipients = [manager_email] if manager_email else []
                        cc_recipients.append(hr_email)

                        mail_values = {
                            'subject': subject,
                            'body_html': body_html,

                            'email_to': employee.work_email,
                            'email_cc': ', '.join(cc_recipients) if cc_recipients else None,
                        }
                        try:
                            mail = self.env['mail.mail'].create(mail_values)
                            mail.send()
                        except Exception as e:
                            _logger.error(f"Failed to send insufficient hours email to {employee.work_email}: {str(e)}")
