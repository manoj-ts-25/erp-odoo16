from odoo import models,fields
from datetime import datetime

class ReportJoiningLetter(models.AbstractModel):
    _name = 'report.ts_hr_letters.joining_letter_pdf_report'
    _description = 'Joining Letter Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['hr.applicant'].browse(docids)
        current_datetime = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
        user = self.env.user
        return {
            'doc_ids': docids,
            'doc_model': 'hr.applicant',
            'docs': docs,
            'current_datetime': current_datetime,
            'user': user,
        }
