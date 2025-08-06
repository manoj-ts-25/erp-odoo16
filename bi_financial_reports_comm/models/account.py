# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

import datetime
from odoo import fields, models, api, _

class AccountAccount(models.Model):
    _inherit = 'account.account'

    current_debit_balance = fields.Float(compute='_compute_debit_credit_balance',string="Current Debit",store=True)
    current_credit_balance = fields.Float(compute='_compute_debit_credit_balance',string="Current Credit",store=True)
    move_line_ids = fields.Many2many('account.move.line')

    @api.depends('move_line_ids.debit', 'move_line_ids.credit')
    def _compute_debit_credit_balance(self):
        credit_balances = {
            read['account_id'][0]: read['credit']
            for read in self.env['account.move.line']._read_group(
                domain=[('account_id', 'in', self.ids), ('parent_state', '=', 'posted')],
                fields=['credit', 'account_id'],
                groupby=['account_id'],
            )
        }

        debit_balances = {
            read['account_id'][0]: read['debit']
            for read in self.env['account.move.line']._read_group(
                domain=[('account_id', 'in', self.ids), ('parent_state', '=', 'posted')],
                fields=['debit', 'account_id'],
                groupby=['account_id'],
            )
        }
        for record in self:
            record.current_credit_balance = credit_balances.get(record.id, 0)
            record.current_debit_balance = debit_balances.get(record.id, 0)

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    invoice_date = fields.Date(
        related='move_id.invoice_date', store=True,
        copy=False,
        aggregator='min',
    )