# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from datetime import datetime
from odoo.tools import format_amount
from odoo import fields, models, api, _

class PartnerLedgerReport(models.Model):
	_name = 'partner.ledger.report'
	_description = 'Partner Ledger Report'

	date_from = fields.Date(string="Date From")
	date_to = fields.Date(string = 'Date To')
	partner_ids = fields.Many2many('res.partner', string="Partner")
	journal_ids = fields.Many2many('account.journal',string='Journal')
	account_ids = fields.Many2many('account.account',string='Account')
	target_move = fields.Selection([('posted', 'All Posted Entries'),
									('all', 'All Entries'),
									], string='Target Moves', required=True, default='posted')
	
	initial_balance = fields.Boolean(string='Include Initial Balances')

	account_tag_ids = fields.Many2many('account.account.tag', string="Account Tags")
	partner_tag_ids = fields.Many2many('res.partner.category', string="Partner Tags")
	include_initial_balance = fields.Boolean(string = 'Include Initial Balance')

	def action_apply_filters_partner(self):
		self.ensure_one()
		existing_record = self.search([], limit=1, order="id DESC")
		context={
			'target_move':self.target_move,
			'date_from':self.date_from,
			'date_to':self.date_to,
			'initial_balance':self.initial_balance,
			'journal_ids':self.journal_ids.ids if self.journal_ids else None,
			'account_ids':self.account_ids.ids if self.account_ids else None,
			'partner_ids':self.partner_ids.ids if self.partner_ids else None,
			'account_tag_ids':self.account_tag_ids.ids if self.account_tag_ids else None,
			'partner_tag_ids':self.partner_tag_ids.ids if self.partner_tag_ids else None,
		}
		records = self.with_context(context).get_data_partner_ledger()
		return {
			'type': 'ir.actions.client',
			'tag': 'partner_ledger_report_tag',
			'name': "Partner Ledger",
			'params': {
				'filtered_records': records if records else [],
				'action_name': "Partner Ledger",
			},
			'target':'current',
		}


	@api.model
	def get_data_partner_ledger(self):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		domain = []
		total_balance=0.0
		total_credit=0.0
		total_debit=0.0
		target_move = context.get("target_move") or existing_record.target_move
		date_from =context.get("date_from") or existing_record.date_from
		date_to = context.get("date_to") or existing_record.date_to
		initial_balance =context.get("initial_balance") or existing_record.initial_balance
		journal_ids = context.get("journal_ids", existing_record.journal_ids.ids if existing_record.journal_ids else [])
		account_ids = context.get("account_ids", existing_record.account_ids.ids if existing_record.account_ids else [])
		partner_ids = context.get("partner_ids", existing_record.partner_ids.ids if existing_record.partner_ids else [])
		account_tag_ids = context.get("account_tag_ids", existing_record.account_tag_ids.ids if existing_record.account_tag_ids else [])
		partner_tag_ids = context.get("partner_tag_ids", existing_record.partner_tag_ids.ids if existing_record.partner_tag_ids else [])
		
		if target_move == 'posted':
			domain.append(('parent_state', '=', 'posted'))
		elif target_move == 'all':
			domain.append(('parent_state', 'in', ['draft', 'posted']))

		if date_from:
			domain.append(('date', '>=', date_from))

		if date_to:
			domain.append(('date', '<=', date_to))

		if journal_ids:
			domain.append(('journal_id', 'in', journal_ids))

		if context.get('account_tag_ids'):
			domain.append(('account_id.tag_ids', 'in', context['account_tag_ids']))
		
		if context.get('partner_tag_ids'):
			domain.append(('partner_id.category_id', 'in', context['partner_tag_ids']))

		if account_ids:
			domain.append(('account_id', 'in', account_ids))
		else:
			domain.append(('account_type', 'in', ['liability_payable', 'asset_receivable']))

		partner_data = []
		search_domain = [('id','in',partner_ids)] if partner_ids else []
		partners = self.env["res.partner"].search(search_domain)

		total_credit=0.0
		total_debit=0.0
		total_balance=0.0

		for partner in partners:
			account_currency = partner.currency_id or self.env.company.currency_id
			currency_symbol = account_currency.symbol if account_currency else ""

			partner_domain = domain + [("partner_id", "=", partner.id)]
			journal_items = self.env["account.move.line"].search(partner_domain)
			
			def format_amount(amount):
				return f"{currency_symbol} {amount:.2f}"

			partner_debit= 0.0
			partner_credit= 0.0
			partner_balance= 0.0
			journal_item_data=[]

			for item in journal_items:
				journal_item_data.append({
					'id': item['id'],
					'partner_id': item['partner_id'],
					'currency_id': item['currency_id'],
					'debit': format_amount(item['debit']),
					'credit': format_amount(item['credit']),
					'balance': format_amount(item['balance']),
					'move_name': item['move_name'],
					'name': item['name'],
					'due_date': item['date_maturity'] or None,
					'journal_id': item['journal_id']['name'],
					'account_code': item['account_id']['code'],
					'matching':item['matching_number'] or '',
					'amount_currency':format_amount(item['discount_amount_currency']),
				})
				partner_debit+=item['debit']
				partner_credit+=item['credit']
				partner_balance+=item['balance']

			partner_data.append({
				'id': partner.id,
				'name': partner.name,
				'debit': format_amount(partner_debit),
				'credit': format_amount(partner_credit),
				'balance': format_amount(partner_balance),
				'journal_items': journal_item_data,
			})

			total_credit += partner_credit
			total_debit += partner_debit
			total_balance += partner_balance
		return partner_data,format_amount(total_balance),format_amount(total_credit),format_amount(total_debit)


	@api.model
	def partner_ledger_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Partner Ledger")

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
		)

		col_widths = [30, 25, 20, 20, 20, 20, 20, 30, 20]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 2, 5, "Partner Ledger", title_style)
		today = datetime.now().strftime("%d-%m-%Y")

		headers = ["", "Journal", "Due Date", "Account", "Matching", "Debit", "Credit", "Amount Currency", "Balance"]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		partners = data.get('partners', [])
		expanded_partners = data.get('expanded_partners', {})
		partnertotalDebit = data.get('partnertotalDebit', 0.00)
		partnertotalCredit = data.get('partnertotalCredit', 0.00)
		partnertotalBalance = data.get('partnertotalBalance', 0.00)

		for partner in partners:
			worksheet.write(row, 0, partner['name'], account_header_style)
			worksheet.write(row, 1, "", account_header_style)
			worksheet.write(row, 2, "", account_header_style)
			worksheet.write(row, 3, "", account_header_style)
			worksheet.write(row, 4, "", account_header_style)
			worksheet.write(row, 5, partner['debit'], account_header_style)
			worksheet.write(row, 6, partner['credit'], account_header_style)
			worksheet.write(row, 7, "", account_header_style)
			worksheet.write(row, 8, partner['balance'], account_header_style)

			worksheet.row(row).height = 360
			row += 1

			if partner['name'] in expanded_partners:
				for item in partner.get('journal_items', []):
					worksheet.write(row, 0, item.get('move_name', ''), line_style)
					worksheet.write(row, 1, item.get('journal_id', ''), line_style)
					worksheet.write(row, 2, item.get('due_date', ''), line_style)
					worksheet.write(row, 3, item.get('account_code', ''), line_style)
					worksheet.write(row, 4, item.get('matching', ''), line_style)
					worksheet.write(row, 5, item.get('debit', ''), line_style)
					worksheet.write(row, 6, item.get('credit', ''), line_style)
					worksheet.write(row, 7, item.get('amount_currency', ''), line_style)
					worksheet.write(row, 8, item.get('balance', ''), line_style)
					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 0, "Total", total_style)
		worksheet.write(row, 1, "", total_style)
		worksheet.write(row, 2, "", total_style)
		worksheet.write(row, 3, "", total_style)
		worksheet.write(row, 4, "", total_style)
		worksheet.write(row, 5, partnertotalDebit, total_style)
		worksheet.write(row, 6, partnertotalCredit, total_style)
		worksheet.write(row, 7, "", total_style)
		worksheet.write(row, 8, partnertotalBalance, total_style)

		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Partner Ledger.xls',
		}
