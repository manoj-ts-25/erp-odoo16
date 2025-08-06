# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import xlwt
import base64
import xlsxwriter
import io
from io import BytesIO
from odoo.tools import format_amount
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class PartnerAgeing(models.Model):
	_name = 'partner.ageing'
	_description = 'Partner Ageing'

	on_date = fields.Date(string="As On Date", default=fields.Date.today)
	account_type = fields.Selection(
		string='Account Types',
		selection=[
			('both', "Payable and receivable"),
			('payable', "Payable"),
			('receivable', "Receivable")
		],
		default="both"
	)
	based_on = fields.Selection(
		string='Based On',
		selection=[
			('due', "Due Date"),
			('invoice', "Invoice Date")
		],
		default="due"
	)
	account_ids = fields.Many2many('account.account', string='Account')
	partner_tag_ids = fields.Many2many('res.partner.category', string="Partner Tags")
	partner_ids = fields.Many2many('res.partner', string="Partners")
	period_length = fields.Integer(string="Period Length (days)", default=30)
	bucket_1 = fields.Integer(compute='_compute_update_bucket')
	bucket_2 = fields.Integer(compute='_compute_update_bucket')
	bucket_3 = fields.Integer(compute='_compute_update_bucket')
	bucket_4 = fields.Integer(compute='_compute_update_bucket')
	bucket_5 = fields.Integer(compute='_compute_update_bucket')

	@api.onchange('period_length')
	def _onchange_period_length(self):
		if self.period_length < 1:
			self.period_length = 1
			raise ValidationError(_('Days Period cannot be smaller than 1'))

	def action_apply_filters_ageing(self):
		self.ensure_one()
		context = {
			'on_date': self.on_date,
			'period_length': self.period_length,
			'account_type': self.account_type,
			'account_ids': self.account_ids.ids,
			'partner_ids': self.partner_ids.ids,
			'partner_tag_ids': self.partner_tag_ids.ids,
			'based_on': self.based_on,
		}
		records = self.with_context(context).get_data_ageing_report()
		return {
			'type': 'ir.actions.client',
			'tag': 'partner_ageing_report_tag',
			'name': "Partner Ageing",
			'params': {
				'filtered_records': records if records else [],
			},
			'target': 'current',
		}

	@api.model
	def get_data_ageing_report(self):
		existing_record = self.search([], limit=1, order="id DESC")
		context = self.env.context
		domain = []
		
		on_date = context.get("on_date") or existing_record.on_date or fields.Date.today()
		period_length = context.get("period_length") or existing_record.period_length or 30
		account_type = context.get("account_type", existing_record.account_type if existing_record else "both")
		account_ids = context.get("account_ids", existing_record.account_ids.ids if existing_record else [])
		partner_ids = context.get("partner_ids", existing_record.partner_ids.ids if existing_record else [])
		partner_tag_ids = context.get("partner_tag_ids", existing_record.partner_tag_ids.ids if existing_record else [])
		based_on = context.get("based_on", existing_record.based_on if existing_record else "due")

		periods = {
			'0': {'name': 'At Date', 'days': 'Current'},
			'1': {'name': f'1-{period_length}', 'days': f'1-{period_length}'},
			'2': {'name': f'{period_length+1}-{2*period_length}', 'days': f'{period_length+1}-{2*period_length}'},
			'3': {'name': f'{2*period_length+1}-{3*period_length}', 'days': f'{2*period_length+1}-{3*period_length}'},
			'4': {'name': f'{3*period_length+1}-{4*period_length}', 'days': f'{3*period_length+1}-{4*period_length}'},
			'5': {'name': f'{4*period_length}+', 'days': f'{4*period_length}+'}
		}

		if account_type == 'payable':
			domain.append(('account_id.account_type', '=', 'liability_payable'))
		elif account_type == 'receivable':
			domain.append(('account_id.account_type', '=', 'asset_receivable'))
		elif account_type == 'both':
			domain.append(('account_id.account_type', 'in', ['liability_payable', 'asset_receivable']))

		if partner_tag_ids:
			domain.append(('partner_id.category_id', 'in', partner_tag_ids))
		
		if account_ids:
			domain.append(('account_id', 'in', account_ids))
		if on_date:
			domain.append(('invoice_date', '<=', on_date))

		partner_domain = []
		if partner_ids:
			partner_domain.append(('id', 'in', partner_ids))
		partners = self.env["res.partner"].search(partner_domain)

		partner_data = []
		currency = self.env.company.currency_id
		currency_data = {
			'symbol': currency.symbol,
			'position': currency.position,
			'decimal_places': currency.decimal_places,
		}
		def format_amount(amount):
			return f"{currency.symbol} {amount:,.2f}" if amount else f"{currency.symbol} 0.00"

		totals = {
				'period0': 0.0,
				'period1': 0.0,
				'period2': 0.0,
				'period3': 0.0,
				'period4': 0.0,
				'period5': 0.0,
				'total': 0.0,
			}

		for partner in partners:

			partner_domain = domain + [
				('partner_id', '=', partner.id),
				('parent_state', '=', 'posted'),
				('reconciled', '=', False)
			]
			journal_items = self.env["account.move.line"].search(partner_domain)
			
			period_amounts = {
				'period0': 0.0,
				'period1': 0.0,
				'period2': 0.0,
				'period3': 0.0,
				'period4': 0.0,
				'period5': 0.0,
				'total': 0.0
			}

			journal_item_data = []
			for item in journal_items:

				if based_on == 'due':
					date_to_use = item.date_maturity or self._calculate_due_date(item)
				else:
					date_to_use = item.move_id.invoice_date or item.date
				
				if not date_to_use:
					continue
				
				days_diff = (on_date - date_to_use).days
				
				if days_diff <= 0:
					period_key = 'period0'
				elif 0 < days_diff <= period_length:
					period_key = 'period1'
				elif period_length < days_diff <= 2 * period_length:
					period_key = 'period2'
				elif 2 * period_length < days_diff <= 3 * period_length:
					period_key = 'period3'
				elif 3 * period_length < days_diff <= 4 * period_length:
					period_key = 'period4'
				else:
					period_key = 'period5'
				
				amount = item.amount_currency if item.amount_currency else item.balance
				period_amounts[period_key] += amount
				period_amounts['total'] += amount
				
				journal_item_data.append({
					'id': item.id,
					'move_id': item.move_id.id,
					'move_name': item.move_id.name,
					'name': item.name,
					'account_code': item.account_id.code,
					'due_date': item.date_maturity.strftime("%m/%d/%Y") if item.date_maturity else None,
					'invoice_date': item.move_id.invoice_date.strftime("%m/%d/%Y") if item.move_id.invoice_date else None,
					'journal_id': item.journal_id.code,
					'currency_symbol': currency.symbol,
					'amount': format_amount(amount),
					'period': periods[period_key.replace('period', '')]['name'],
					'period_key': period_key,
					'raw_amount': amount,
				})
			if journal_item_data or any(period_amounts.values()):
				totals['period0'] += period_amounts['period0']
				totals['period1'] += period_amounts['period1']
				totals['period2'] += period_amounts['period2']
				totals['period3'] += period_amounts['period3']
				totals['period4'] += period_amounts['period4']
				totals['period5'] += period_amounts['period5']
				totals['total'] += period_amounts['total']
				partner_data.append({
					'id': partner.id,
					'name': partner.name,
					'period0': format_amount(period_amounts['period0']),
					'period1': format_amount(period_amounts['period1']),
					'period2': format_amount(period_amounts['period2']),
					'period3': format_amount(period_amounts['period3']),
					'period4': format_amount(period_amounts['period4']),
					'period5': format_amount(period_amounts['period5']),
					'total': format_amount(period_amounts['total']),
					'raw_amounts': period_amounts,
					'journal_items': journal_item_data,
					'account_type': account_type
				})
		formatted_total = {
			'period0': format_amount(totals['period0']),
			'period1': format_amount(totals['period1']),
			'period2': format_amount(totals['period2']),
			'period3': format_amount(totals['period3']),
			'period4': format_amount(totals['period4']),
			'period5': format_amount(totals['period5']),
			'total': format_amount(totals['total'])
		}
		return [partner_data, periods,currency_data,formatted_total]


	def _calculate_due_date(self, move_line):
		if move_line.move_id.invoice_payment_term_id and move_line.move_id.invoice_date:
			terms = move_line.move_id.invoice_payment_term_id.compute(
				move_line.move_id.amount_total, 
				move_line.move_id.invoice_date
			)
			if terms:
				return terms[-1][0]
		return move_line.move_id.invoice_date or move_line.date

	def _compute_update_bucket(self):
		for record in self:
			day_period = record.period_length
			record.bucket_1 = day_period
			record.bucket_2 = day_period * 2
			record.bucket_3 = day_period * 3
			record.bucket_4 = day_period * 4
			record.bucket_5 = day_period * 5

	@api.model
	def partner_ageing_excel_report(self, data):
		workbook = xlwt.Workbook(encoding="UTF-8")
		worksheet = workbook.add_sheet("Partner Ageing")

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

		col_widths = [30, 20, 20, 15, 15, 15, 15, 15,15, 15,15,15]
		for i, width in enumerate(col_widths):
			worksheet.col(i).width = 256 * width

		worksheet.write_merge(0, 2, 3, 7, "Partner Ageing", title_style)
		today = datetime.now().strftime("%d-%m-%Y")

		partners = data.get('partners', [])
		expandedPartners = data.get('expandedPartners', {})
		periods = data.get('periods',{})
		currency = data.get('currency','')
		currency_symbol = currency.get('symbol')
		PeriodTotal = data.get('PeriodTotal', 0.00)
		headers = ["Move","Invoice Date", "Due Date", "Journal", "Account",
				periods['0'].get("name"),periods['1'].get("name"), periods['2'].get("name"), periods['3'].get("name"),
				periods['4'].get("name"), periods['5'].get("name"),"Total"
		]
		row = 5
		for col, header in enumerate(headers):
			worksheet.write(row, col, header, header_style)
		worksheet.row(row).height = 400
		row += 1

		for partner in partners:
			worksheet.write(row, 0, partner['name'], account_header_style)
			worksheet.write(row, 1, "", account_header_style)
			worksheet.write(row, 2, "", account_header_style)
			worksheet.write(row, 3, "", account_header_style)
			worksheet.write(row, 4, "", account_header_style)
			worksheet.write(row, 5, partner['period0'], account_header_style)
			worksheet.write(row, 6, partner['period1'], account_header_style)
			worksheet.write(row, 7, partner['period2'], account_header_style)
			worksheet.write(row, 8, partner['period3'], account_header_style)
			worksheet.write(row, 9, partner['period4'], account_header_style)
			worksheet.write(row, 10, partner['period5'], account_header_style)
			worksheet.write(row, 11, partner['total'], account_header_style)

			worksheet.row(row).height = 360
			row += 1

			if partner['name'] in expandedPartners:
				for item in partner.get('journal_items', []):
					worksheet.write(row, 0, item.get('move_name', ''), line_style)

					worksheet.write(row, 1, item.get('invoice_date', ''), line_style)

					worksheet.write(row, 2, item.get('due_date', ''), line_style)
					worksheet.write(row, 3, item.get('journal_id', ''), line_style)
					worksheet.write(row, 4, item.get('account_code', ''), line_style)
					if item.get('period_key') == 'period0':
						worksheet.write(row, 5, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 5, f"{currency_symbol} 0.00", line_style)
					
					if item.get('period_key') == 'period1':
						worksheet.write(row, 6, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 6, f"{currency_symbol} 0.00", line_style)
					
					if item.get('period_key') == 'period2':
						worksheet.write(row, 7, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 7, f"{currency_symbol} 0.00", line_style)

					if item.get('period_key') == 'period3':
						worksheet.write(row, 8, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 8, f"{currency_symbol} 0.00", line_style)

					if item.get('period_key') == 'period4':
						worksheet.write(row, 9, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 9, f"{currency_symbol} 0.00", line_style)

					if item.get('period_key') == 'period5':
						worksheet.write(row, 10, item.get('amount', ''), line_style)
					else:
						worksheet.write(row, 10, f"{currency_symbol} 0.00", line_style)

					worksheet.write(row, 11, item.get('amount', ''), line_style)
					worksheet.row(row).height = 360
					row += 1

		worksheet.write(row, 0, "Total", total_style)
		worksheet.write(row, 1, "", total_style)
		worksheet.write(row, 2, "", total_style)
		worksheet.write(row, 3, "", total_style)
		worksheet.write(row, 4, "", total_style)
		worksheet.write(row, 5, PeriodTotal.get('period0'), total_style)
		worksheet.write(row, 6, PeriodTotal.get('period1'), total_style)
		worksheet.write(row, 7, PeriodTotal.get('period2'), total_style)
		worksheet.write(row, 8, PeriodTotal.get('period3'), total_style)
		worksheet.write(row, 9, PeriodTotal.get('period4'), total_style)
		worksheet.write(row, 10, PeriodTotal.get('period5'), total_style)
		worksheet.write(row, 11, PeriodTotal.get('total'), total_style)

		worksheet.row(row).height = 400

		file_data = BytesIO()
		workbook.save(file_data)
		file_data.seek(0)
		excel_file = base64.b64encode(file_data.read()).decode('utf-8')

		return {
			'excel_file': excel_file,
			'file_name': 'Partner Ageing.xls',
		}