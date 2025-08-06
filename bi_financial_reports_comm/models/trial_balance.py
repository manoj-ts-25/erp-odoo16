# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta
from odoo.tools import format_amount
from odoo.tools.date_utils import get_month, get_fiscal_year, get_quarter
from odoo import fields, models, api, _

class TrialBalanceReport(models.Model):
	_name = 'trial.balance.report'
	_description = 'Trial Balance Report'

	DATE_SELECTION = [
		('today', 'Today'),
		('this_week', 'This Week'),
		('this_month', 'This Month'),
		('this_quarter', 'This Quarter'),
		('this_financialyear', 'This Financial Year'),
		('yesterday', 'Yesterday'),
		('last_week', 'Last Week'),
		('last_month', 'Last Month'),
		('last_quarter', 'Last Quarter'),
		('last_financialyear', 'Last Financial Year'),
	]

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string="Date To")
	journal_ids = fields.Many2many('account.journal', string='Journals')
	account_ids = fields.Many2many('account.account', string='Accounts')
	account_tag_ids = fields.Many2many('account.account.tag', string="Account Tags")
	partner_ids = fields.Many2many('res.partner', string="Partners")
	target_move = fields.Selection([('posted', 'All Posted Entries'), ('all', 'All Entries')], 
								   string='Target Moves', default='posted')
	date_range = fields.Selection(DATE_SELECTION,string="Compare Date Range", default='this_financialyear')

	@api.onchange('date_range')
	def _onchange_date_range(self):
		today =fields.Date.today()
		if self.date_range == 'today':
			self.date_from = today
			self.date_to = today
		elif self.date_range == 'this_week':
			self.date_from = today - timedelta(days=today.weekday())
			self.date_to = today
		elif self.date_range == 'this_month':
			self.date_from = get_month(today)[0]
			self.date_to = today
		elif self.date_range == 'this_quarter':
			quarter = get_quarter(today)
			self.date_from = quarter[0]
			self.date_to = today
		elif self.date_range == 'this_financialyear':
			fiscal_year = get_fiscal_year(today)
			self.date_from = fiscal_year[0]
			self.date_to = today
		elif self.date_range == 'yesterday':
			yesterday = today - timedelta(days=1)
			self.date_from = yesterday
			self.date_to = yesterday
		elif self.date_range == 'last_week':
			last_week = today - timedelta(weeks=1)
			self.date_from = last_week - timedelta(days=last_week.weekday())
			self.date_to = self.date_from + timedelta(days=6)
		elif self.date_range == 'last_month':
			first_day_this_month = get_month(today)[0]
			self.date_to = first_day_this_month - timedelta(days=1)
			self.date_from = self.date_to.replace(day=1)
		elif self.date_range == 'last_quarter':
			current_quarter_start = get_quarter(today)[0]
			last_quarter_end = current_quarter_start - timedelta(days=1)
			last_quarter_start = last_quarter_end.replace(day=1) - relativedelta(months=2)
			self.date_from = last_quarter_start
			self.date_to = last_quarter_end
		elif self.date_range == 'last_financialyear':
			current_fiscal_start = get_fiscal_year(today)[0]
			last_fiscal_end = current_fiscal_start - timedelta(days=1)
			last_fiscal_start = get_fiscal_year(last_fiscal_end)[0]
			self.date_from = last_fiscal_start
			self.date_to = last_fiscal_end


	def action_apply_filters_trial_balance(self):
		self.ensure_one()
		context = {
			'date_from': self.date_from,
			'date_to': self.date_to,
			'date_range': self.date_range,
			'target_move': self.target_move,
			'journal_ids': self.journal_ids.ids if self.journal_ids else None,
			'account_ids': self.account_ids.ids if self.account_ids else None,
			'partner_ids': self.partner_ids.ids if self.partner_ids else None,
			'account_tag_ids': self.account_tag_ids.ids if self.account_tag_ids else None,
		}
		records = self.with_context(context).get_data_trial_balance()
		return {
			'type': 'ir.actions.client',
			'tag': 'trial_balance_report_tag',
			'name': "Trial Balance",
			'params': {
				'filtered_records': records if records else [],
			},
			'target': 'current',
		}

	@api.model
	def get_data_trial_balance(self,date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		date_from = context.get("date_from") or existing_record.date_from  or self.date_from
		date_to = context.get("date_to") or existing_record.date_to  or self.date_to
		# date_range = context.get("date_range") or existing_record.date_range or self.date_range
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record.journal_ids else [])
		account_ids = context.get("account_ids", existing_record.account_ids.ids if existing_record.account_ids else [])
		partner_ids = context.get("partner_ids", existing_record.partner_ids.ids if existing_record.partner_ids else [])
		account_tag_ids = context.get("account_tag_ids", existing_record.account_tag_ids.ids if existing_record.account_tag_ids else [])
		target_move = context.get("target_move", existing_record.target_move if existing_record else 'posted')
		def format_amount(amount):
			return f"{self.env.company.currency_id.symbol} {amount:.2f}"

		if not (date_from and date_to):
			fiscal_year = get_fiscal_year(fields.Date.today())
			date_from = fiscal_year[0]
			date_to = fields.Date.today()

		domain = []
		if journal_ids:
			domain.append(('journal_id', 'in', journal_ids))
		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		elif target_move == 'all':
			domain.append(('parent_state', 'in', ['draft', 'posted']))

		if partner_ids:
			domain.append(('partner_id', 'in', partner_ids))

		account_domain = []
		if account_ids:
			account_domain.append(('id', 'in', account_ids))
		if account_tag_ids:
			account_domain.append(('tag_ids', 'in', account_tag_ids))

		accounts = self.env['account.account'].search(account_domain)

		account_data = []
		total_initial_debit = 0.0
		total_initial_credit = 0.0
		total_period_debit = 0.0
		total_period_credit = 0.0
		total_ending_debit = 0.0
		total_ending_credit = 0.0

		for account in accounts:
			period_domain = domain + [('account_id', '=', account.id)]
			if date_from:
				period_domain.append(('date', '>=', date_from))
			if date_to:
				period_domain.append(('date', '<=', date_to))
			period_lines = self.env['account.move.line'].search(period_domain)

			if not period_lines:
				continue

			period_credit = 0.0
			period_debit = 0.0
			period_debit = sum(line.debit for line in period_lines)
			period_credit = sum(line.credit for line in period_lines)

			initial_credit = 0.0
			initial_debit = 0.0
			if date_from:
				initial_account_domain = domain + [('account_id', '=', account.id),('date', '<', date_from)]
				initial_lines = self.env['account.move.line'].search(initial_account_domain)
				initial_debit = sum(line.debit for line in initial_lines)
				initial_credit = sum(line.credit for line in initial_lines)

			total_debit = initial_debit + period_debit
			total_credit = initial_credit + period_credit
			debit_credit_diff = total_debit - total_credit
			if debit_credit_diff > 0:
				ending_debit = debit_credit_diff
				ending_credit = 0.0
			else:
				ending_debit = 0.0
				ending_credit = abs(debit_credit_diff)

			account_data.append({
				'id': account.id,
				'code': account.code,
				'name': account.name,
				'initial_debit': format_amount(initial_debit),
				'initial_credit': format_amount(initial_credit),
				'period_debit': format_amount(period_debit),
				'period_credit': format_amount(period_credit),
				'ending_debit': format_amount(ending_debit),
				'ending_credit': format_amount(ending_credit),
			})

			total_initial_debit += initial_debit
			total_initial_credit += initial_credit
			total_period_debit += period_debit
			total_period_credit += period_credit
			total_ending_debit += ending_debit
			total_ending_credit += ending_credit
		balance_dict = {
			'accounts': account_data,
			'journal_ids': journal_ids,
			'date_from': date_from,
			'date_to': date_to,
			'total_initial_debit': format_amount(total_initial_debit),
			'total_initial_credit': format_amount(total_initial_credit),
			'total_period_debit': format_amount(total_period_debit),
			'total_period_credit': format_amount(total_period_credit),
			'total_ending_debit': format_amount(total_ending_debit),
			'total_ending_credit': format_amount(total_ending_credit),
			'currency': {
				'symbol': self.env.company.currency_id.symbol,
				'position': self.env.company.currency_id.position,
			}
		}

		return account_data,balance_dict

	@api.model
	def trial_balance_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Trial Balance")

		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 250;'
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)

		title_style = xlwt.easyxf(
			'font: bold True, name Arial, height 320; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)

		sub_header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 240; '
			'align: vertical center, horizontal center; '
		)

		account_header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		line_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		amount_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)

		total_style = xlwt.easyxf(
			'font: bold True, name Arial, height 230; '
			'align: horizontal center; '
			'pattern: pattern solid,fore_colour gray25;'
		)

		col_widths = [45, 20, 20, 20, 20, 20, 20]
		for i, width in enumerate(col_widths):
			worksheet.col(i+1).width = 256 * width

		balanceData = data.get('balanceData', [])
		accountData = data.get('accountData', {})
		
		date_from=''
		date_to=''
		if balanceData['date_from']:
			date_from = f'From {balanceData["date_from"]}'
		if balanceData['date_to']:
			date_to = f'To {balanceData["date_to"]}'

		worksheet.write_merge(1, 3, 2, 5, "Trial Balance", title_style)
		today = datetime.now().strftime("%d-%m-%Y")
		worksheet.write_merge(6, 6, 2, 5, f"{date_from} {date_to} ", sub_header_style)

		worksheet.write_merge(8, 8, 2, 3, "Initial Balance", header_style)
		worksheet.write_merge(8, 8, 4, 5, "Trial Balance", header_style)
		worksheet.write_merge(8, 8, 6, 7, "End Balance", header_style)

		headers = ["Account", "Debit", "Credit", "Debit", "Credit", "Debit", "Credit"]
		row = 9
		for col, header in enumerate(headers):
			worksheet.write(row, col+1, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		for account in accountData:
			worksheet.write(row, 1, f"{account['code'] + ' ' + account['name']}", account_header_style)
			worksheet.write(row, 2, account['initial_debit'], line_style)
			worksheet.write(row, 3, account['initial_credit'], line_style)
			worksheet.write(row, 4, account['period_debit'], line_style)
			worksheet.write(row, 5, account['period_credit'], line_style)
			worksheet.write(row, 6, account['ending_debit'], line_style)
			worksheet.write(row, 7, account['ending_credit'], line_style)

			worksheet.row(row).height = 360
			row += 1

		worksheet.write(row, 1, "Total", total_style)
		worksheet.write(row, 2, balanceData['total_initial_debit'], total_style)
		worksheet.write(row, 3, balanceData['total_initial_credit'], total_style)
		worksheet.write(row, 4, balanceData['total_period_debit'], total_style)
		worksheet.write(row, 5, balanceData['total_period_credit'], total_style)
		worksheet.write(row, 6, balanceData['total_ending_debit'], total_style)
		worksheet.write(row, 7, balanceData['total_ending_credit'], total_style)
		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Trial Balance.xls',
		}