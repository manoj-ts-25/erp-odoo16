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

class BalanceSheetReport(models.Model):
	_name = 'balance.sheet.report'
	_description = 'Balance Sheet Report'

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

	def action_apply_filters_balancesheet(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'date_from':self.date_from if self.date_from else None,
			'date_to':self.date_to if self.date_to else None,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'date_range':self.date_range if self.date_range else None,
		}
		records = self.with_context(context).get_data_balance_sheet()
		return {
			'type': 'ir.actions.client',
			'tag': 'balance_sheet_report_tag',
			'name': "Balance Sheet",
			'params': {
				'filtered_records': records if records else [],
			},
			'target':'current',
		}
		
	def _get_account_by_type(self, account_types):
		return self.env['account.account'].search([
			('account_type', 'in', account_types)])

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
		return move_lines[0]['balance'] if move_lines else 0.0

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
	def get_data_balance_sheet(self,date_range=None):
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

		asset_accounts = {
			'bank_cash': self._get_account_by_type(['asset_cash']),
			'receivables': self._get_account_by_type(['asset_receivable']),
			'current_assets': self._get_account_by_type(['asset_current']),
			'prepayments': self._get_account_by_type(['asset_prepayments']),
			'fixed_assets': self._get_account_by_type(['asset_fixed']),
			'non_current': self._get_account_by_type(['asset_non_current']),
		}

		liability_accounts = {
			'payables': self._get_account_by_type(['liability_payable']),
			'credit_card': self._get_account_by_type(['liability_credit_card']),
			'current_liabilities': self._get_account_by_type(['liability_current']),
			'non_current_liabilities': self._get_account_by_type(['liability_non_current']),
		}

		equity_accounts = {
			'equity': self._get_account_by_type(['equity']),
			'current_year_earnings': self._get_account_by_type(['equity_unaffected']),
		}
		assets = self.account_balance_calculate(asset_accounts,date_from, date_to)
		liabilities = self.account_balance_calculate(liability_accounts,date_from, date_to)
		equity = self.account_balance_calculate(equity_accounts,date_from, date_to)
		
		total_assets = sum(data['total'] for data in assets.values())
		total_liabilities = sum(data['total'] for data in liabilities.values())
		total_equity = sum(data['total'] for data in equity.values())

		currency = self.env.company.currency_id
		currency_data = {
			'symbol': currency.symbol,
			'position': currency.position,
			'decimal_places': currency.decimal_places,
		}
	
		return {
			'date_from': date_from,
			'date_to': date_to,
			'company': self.env.company.name,
			'currency_data': currency_data,
			'assets': assets,
			'liabilities': liabilities,
			'equity': equity,
			'totals': {
				'assets': total_assets,
				'liabilities': total_liabilities,
				'equity': total_equity,
				'liabilities_equity': total_liabilities + total_equity,
			}
		}

	@api.model
	def balance_sheet_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Balance Sheet Report")

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
		
		section_header_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal left;'
			'pattern: pattern solid, fore_colour gray25;'
		)

		section_amount_style = xlwt.easyxf(
			'font: bold True, height 220; '
			'align: vertical center, horizontal center;'
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

		balanceSheetData = data.get('balanceSheetData', {})
		currentAssetsTotal = data.get('currentAssetsTotal', 0)
		AssetsTotalBalance = data.get('AssetsTotalBalance', 0)
		currentLiabilitiesTotal = data.get('currentLiabilitiesTotal', 0)
		totals = data.get('totals', 0)
		assets = balanceSheetData['assets']
		liabilities = balanceSheetData['liabilities']
		equity = balanceSheetData['equity']
		totals = data.get('totals', 0)
		expandedType = data.get('expandedType', {})

		date_from=''
		date_to=''

		account_currency = self.env.company.currency_id
		currency_symbol = account_currency.symbol if account_currency else ""

		def format_amount(amount):
			return f"{currency_symbol} {amount:.2f}"

		if balanceSheetData['date_from']:
			date_from = f'From {balanceSheetData["date_from"]}'
		if balanceSheetData['date_to']:
			date_to = f'To {balanceSheetData["date_to"]}'

		worksheet.write_merge(0, 1, 1, 2, "Balance Sheet Report", title_style)
		worksheet.write_merge(3, 3, 1, 2, f"{date_from} {date_to} ", header_style)
		
		row = 5
		
		worksheet.write(row, 1, "Assets", section_header_style)
		worksheet.write(row, 2, format_amount(totals['assets']), section_amount_style)
		row += 1

		worksheet.write(row, 1, "   Current Assets	", line_style)
		worksheet.write(row, 2, format_amount(currentAssetsTotal), amount_style)
		row += 1

		worksheet.write(row, 1, "     Bank and Cash Accounts", line_style)
		worksheet.write(row, 2, format_amount(assets['bank_cash']['total']), amount_style)
		row += 1
		
		if 'bank_cash' in expandedType and 'accounts' in assets['bank_cash']:
			for account in assets['bank_cash']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Receivables", line_style)
		worksheet.write(row, 2, format_amount(assets['receivables']['total']), amount_style)
		row += 1
		
		if 'receivables' in expandedType and 'accounts' in assets['receivables']:
			for account in assets['receivables']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}",line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Current Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['bank_cash']['total']), amount_style)
		row += 1

		if 'current_assets' in expandedType and 'accounts' in assets['current_assets']:
			for account in assets['current_assets']['accounts']:
				worksheet.write(rowx, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Prepayments", line_style)
		worksheet.write(row, 2, format_amount(assets['prepayments']['total']), amount_style)
		row += 1
		
		if 'prepayments' in expandedType and 'accounts' in assets['prepayments']:
			for account in assets['prepayments']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "   Plus Fixed Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['fixed_assets']['total']), amount_style)
		row += 1
		
		if 'fixed_assets' in expandedType and 'accounts' in assets['fixed_assets']:
			for account in assets['fixed_assets']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "   Plus Non-current Assets", line_style)
		worksheet.write(row, 2, format_amount(assets['non_current']['total']), amount_style)
		row += 1
		
		if 'non_current' in expandedType and 'accounts' in assets['non_current']:
			for account in assets['non_current']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "LIABILITIES", section_header_style)
		worksheet.write(row, 2, format_amount(totals['liabilities']), section_amount_style)
		row += 1
		
		worksheet.write(row, 1, "   Current Liabilities", line_style)
		worksheet.write(row, 2, format_amount(liabilities['current_liabilities']['total']), amount_style)
		row += 1
		
		if 'current_liabilities' in expandedType and 'accounts' in liabilities['current_liabilities']:
			for account in liabilities['current_liabilities']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "     Payables", line_style)
		worksheet.write(row, 2, format_amount(liabilities['payables']['total']), amount_style)
		row += 1
		
		if 'payables' in expandedType and 'accounts' in liabilities['payables']:
			for account in liabilities['payables']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "     Credit Card", line_style)
		worksheet.write(row, 2, format_amount(liabilities['credit_card']['total']), amount_style)
		row += 1
		
		if 'credit_card' in expandedType and 'accounts' in liabilities['credit_card']:
			for account in liabilities['credit_card']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "   Plus Non-current Liabilities", line_style)
		worksheet.write(row, 2, format_amount(liabilities['non_current_liabilities']['total']), amount_style)
		row += 1
		
		if 'non_current_liabilities' in expandedType and 'accounts' in liabilities['non_current_liabilities']:
			for account in liabilities['non_current_liabilities']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "EQUITY", section_header_style)
		worksheet.write(row, 2, format_amount(totals['equity']), section_amount_style)
		row += 1
		
		worksheet.write(row, 1, "    Equity", line_style)
		worksheet.write(row, 2, format_amount(equity['equity']['total']), amount_style)
		row += 1
		
		if 'equity' in expandedType and 'accounts' in equity['equity']:
			for account in equity['equity']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1
		
		worksheet.write(row, 1, "    Current Year Earnings", line_style)
		worksheet.write(row, 2, format_amount(equity['current_year_earnings']['total']), amount_style)
		row += 1
		
		if 'current_year_earnings' in expandedType and 'accounts' in equity['current_year_earnings']:
			for account in equity['current_year_earnings']['accounts']:
				worksheet.write(row, 1, f"         {account['code']} - {account['name']}", line_style)
				worksheet.write(row, 2, format_amount(account['balance']), amount_style)
				row += 1

		worksheet.write(row, 1, "LIABILITIES + EQUITY", section_header_style)
		worksheet.write(row, 2, format_amount(totals['liabilities_equity']), section_amount_style)
		row += 1
		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		today = datetime.now().strftime("%Y-%m-%d")
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': f'Balance_Sheet.xls',
		}
