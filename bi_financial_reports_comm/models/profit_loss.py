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

class ProfitLossReport(models.Model):
	_name = 'profit.loss.report'
	_description = 'Profit and Loss Report'

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
	date_to = fields.Date(string = 'Date To')
	date_range = fields.Selection(DATE_SELECTION,string="Compare Date Range", default='this_financialyear')
	journal_ids = fields.Many2many('account.journal',string='Journal')

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


	def action_apply_filters_profitloss(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'date_from':self.date_from if self.date_from else None,
			'date_to':self.date_to if self.date_to else None,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'date_range':self.date_range if self.date_range else None,
		}
		
		records = self.with_context(context).get_data_profit_loss()
		return {
			'type': 'ir.actions.client',
			'tag': 'profit_loss_report_tag',
			'name': "Profit and Loss",
			'params': {
				'filtered_records': records if records else [],
			},
			'target':'current',
		}
		
	def _get_account_by_type(self, account_types):
		return self.env['account.account'].search([
			('account_type', 'in', account_types),
		])

	def get_account_balance(self, account, date_from, date_to):
		domain = [
			('account_id', '=', account.id),
			('parent_state', '=', 'posted'),
		]
		if date_from:
			domain.append(('date', '>=', date_from))

		if date_to:
			domain.append(('date', '<=', date_to))
		
		if self.env.context.get('journal_ids'):
			domain.append(('journal_id', 'in', self.env.context['journal_ids']))
		
		move_lines = self.env['account.move.line'].read_group(
			domain,
			['account_id', 'balance'],
			['account_id']
		)
		balance = move_lines[0]['balance'] if move_lines else 0.0
		if account.account_type in ['income', 'income_other']:
			return -balance
		return balance

	def account_balance_calculate(self,accounts_dict, date_from,date_to):
		result = {}
		for key, accounts in accounts_dict.items():
			account_data = []
			total = 0.0
			for account in accounts:
				balance = self.get_account_balance(account, date_from, date_to)
				if balance:
					account_data.append({
						'id': account.id,
						'name': account.name,
						'code': account.code,
						'balance': balance,
					})
					total += balance
			result[key] = {
				'accounts': account_data,
				'total': total
			}
		return result

	@api.model
	def get_data_profit_loss(self,date_range=None):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		domain = []
		total_amount=0.0
		date_from =context.get("date_from") or existing_record.date_from
		date_to = context.get("date_to") or existing_record.date_to
		date_range = context.get("date_range") or existing_record.date_range
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record.journal_ids else [])

		if not (date_range and date_from and date_to):
			fiscal_year = get_fiscal_year(fields.Date.today())
			date_from = fiscal_year[0]
			date_to = fields.Date.today()

		income_accounts = {
			'income': self._get_account_by_type(['income']),
			'income_other': self._get_account_by_type(['income_other']),
		}

		expense_accounts = {
			'expense': self._get_account_by_type(['expense']),
			'expense_depreciation': self._get_account_by_type(['expense_depreciation']),
			'expense_direct_cost': self._get_account_by_type(['expense_direct_cost']),
		}

		income = self.account_balance_calculate(income_accounts,date_from, date_to)
		expense = self.account_balance_calculate(expense_accounts,date_from, date_to)		

		currency = self.env.company.currency_id
		currency_data = {
			'symbol': currency.symbol,
			'position': currency.position,
			'decimal_places': currency.decimal_places,
		}
	
		return {
			'date_from': date_from if date_from else None,
			'date_to': date_to if date_to else None,
			'company': self.env.company.name,
			'currency_data': currency_data,
			'income': income,
			'expense': expense,
		}

	@api.model
	def profit_loss_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Profit and Loss Report")

		account_currency = self.env.company.currency_id
		currency_symbol = account_currency.symbol if account_currency else ""

		title_style = xlwt.easyxf(
			'font: bold True, name Arial, height 300; '
			'align: vertical center, horizontal center; '
			'pattern: pattern solid, fore_colour gray25;'
		)
		
		header_style = xlwt.easyxf(
			'font: bold True, name Arial, height 240; '
			'align: vertical center, horizontal center;'
		)

		line_style = xlwt.easyxf(
			'font: name Arial, height 230; '
			'align: vertical center, horizontal center; '
		)
		
		section_header_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal left;'
			'pattern: pattern solid, fore_colour gray25;'
		)
		
		line_style = xlwt.easyxf(
			'font: name Arial, height 220; '
			'align: vertical center, horizontal left;'
		)
		
		amount_style = xlwt.easyxf(
			'font: name Arial, height 200; '
			'align: vertical center, horizontal center;'
		)
		
		total_style = xlwt.easyxf(
			'font: bold True, name Arial, height 220; '
			'align: vertical center, horizontal right;'
		)

		worksheet.col(1).width = 12000
		worksheet.col(2).width = 5000

		ProfitLossData = data.get('ProfitLossData', {})
		income = ProfitLossData.get('income', {})
		expense = ProfitLossData.get('expense', {})
		grossProfitTotal = data.get('grossProfitTotal', 0)
		operatingIncomeTotal = data.get('operatingIncomeTotal', 0)
		expandedType = data.get('expandedType', {})
		date_from=''
		date_to=''
		if ProfitLossData['date_from']:
			date_from = f'From {ProfitLossData["date_from"]}'
		if ProfitLossData['date_to']:
			date_to = f'To {ProfitLossData["date_to"]}'

		worksheet.write_merge(0, 1, 1, 2, "PROFIT AND LOSS", title_style)
		worksheet.write_merge(3, 3, 1, 2, f"{date_from} {date_to} ", header_style)
		
		row = 5
		
		worksheet.write(row, 1, "Revenue", line_style)
		worksheet.write(row, 2, f"{currency_symbol} {income.get('income', {}).get('total', 0)}", amount_style)
		row += 1
		
		if 'income' in expandedType and 'accounts' in income.get('income', {}):
			for account in income['income']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, f"{currency_symbol} {account.get('balance', 0)}", amount_style)
				row += 1
		
		worksheet.write(row, 1, "Less Cost of Revenue", line_style)
		worksheet.write(row, 2, f"{currency_symbol} {expense.get('expense_direct_cost', {}).get('total', 0)}", amount_style)
		row += 1
		
		if 'expense_direct_cost' in expandedType and 'accounts' in expense.get('expense_direct_cost', {}):
			for account in expense['expense_direct_cost']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, f"{currency_symbol} {account.get('balance', 0)}", amount_style)
				row += 1
		
		worksheet.write(row, 1, "Gross Profit", section_header_style)
		worksheet.write(row, 2, f"           {currency_symbol} {grossProfitTotal}", section_header_style)
		row += 1
		
		worksheet.write(row, 1, "Less Operating Expenses", line_style)
		worksheet.write(row, 2, f"{currency_symbol} {expense.get('expense', {}).get('total', 0)}", amount_style)
		row += 1
		
		if 'expense' in expandedType and 'accounts' in expense.get('expense', {}):
			for account in expense['expense']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, f"{currency_symbol} {account.get('balance', 0)}", amount_style)
				row += 1
		
		worksheet.write(row, 1, "Operating Income (or Loss)", section_header_style)
		worksheet.write(row, 2, f"          {currency_symbol} {operatingIncomeTotal}", section_header_style)
		row += 1
		
		worksheet.write(row, 1, "Plus: Other Income", line_style)
		worksheet.write(row, 2, f"{currency_symbol} {income.get('income_other', {}).get('total', 0)}", amount_style)
		row += 1
		
		if 'income_other' in expandedType and 'accounts' in income.get('income_other', {}):
			for account in income['income_other']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, f"{currency_symbol} {account.get('balance', 0)}", amount_style)
				row += 1
		
		worksheet.write(row, 1, "Less: Other Expenses", line_style)
		worksheet.write(row, 2, f"{currency_symbol} {expense.get('expense_depreciation', {}).get('total', 0)}", amount_style)
		row += 1
		
		if 'expense_depreciation' in expandedType and 'accounts' in expense.get('expense_depreciation', {}):
			for account in expense['expense_depreciation']['accounts']:
				worksheet.write(row, 1, f"   {account.get('code', '')} - {account.get('name', '')}", line_style)
				worksheet.write(row, 2, f"{currency_symbol} {account.get('balance', 0)}", amount_style)
				row += 1
		
		net_profit = operatingIncomeTotal + income.get('income_other', {}).get('total', 0) - expense.get('expense_depreciation', {}).get('total', 0)
		worksheet.write(row, 1, "Net Profit", section_header_style)
		worksheet.write(row, 2, f"          {currency_symbol} {net_profit}", section_header_style)

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		today = datetime.now().strftime("%Y-%m-%d")
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': f'Profit_and_Loss_Statement.xls',
		}
