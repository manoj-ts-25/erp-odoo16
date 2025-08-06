# -- coding: utf-8 --
from odoo import api, fields, models,_
from datetime import datetime, timedelta

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    sale_type = fields.Selection([
        ('new_customer','New Customer'),
        ('returning_customer','Returning Customer'),
        ('cross_sale', 'Cross-Sale'),
        ('upsale', 'Upsale')], string='Sale Type', compute='_compute_sale_type', store=True)


    @api.depends('order_id.partner_id', 'product_id', 'price_subtotal')
    def _compute_sale_type(self):
        six_months_ago = fields.Date.today() - timedelta(days=180)
        for line in self:
            partner = line.order_id.partner_id
            product = line.product_id

            if not partner or not product:
                line.sale_type = False
                continue

            domain = [
                ('order_id.partner_id', '=', partner.id),
                ('state', 'in', ['sale', 'done']),
                ('order_id.date_order', '>=', six_months_ago),
            ]
            if line.id:
                domain.append(('id', '!=', line.id))

            past_lines = self.search(domain).sorted(key=lambda l: l.order_id.date_order or fields.Date.today(),
                                                    reverse=True)

            if not past_lines:
                line.sale_type = 'new_customer'
                continue

            same_product_lines = past_lines.filtered(lambda l: l.product_id == product)
            if not same_product_lines:
                line.sale_type = 'cross_sale'
            else:
                latest_line = same_product_lines[0]
                if line.price_subtotal > latest_line.price_subtotal:
                    line.sale_type = 'upsale'
                else:
                    line.sale_type = 'returning_customer'


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    sale_type = fields.Selection([
        ('new_customer','New Customer'),
        ('returning_customer','Returning Customer'),
        ('cross_sale', 'Cross-Sale'),
        ('upsale', 'Upsale')], string='Sale Type', compute='_compute_sale_type', store=True)

    @api.depends('move_id.partner_id', 'product_id', 'price_subtotal')
    def _compute_sale_type(self):
        six_months_ago = fields.Date.today() - timedelta(days=180)
        for line in self:
            partner = line.move_id.partner_id
            product = line.product_id
            if not partner or not product:
                line.sale_type = False
                continue

            base_domain = [
                ('move_id.partner_id', '=', partner.id),
                ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
                ('move_id.invoice_date', '>=', six_months_ago),
                ('move_id.state', '=', 'posted'),
            ]
            if line.id:
                base_domain.append(('id', '!=', line.id))
            past_lines = self.search(base_domain).sorted(key=lambda l: l.move_id.invoice_date or fields.Date.today(),
                                                         reverse=True)
            if not past_lines:
                line.sale_type = 'new_customer'
                continue

            same_product_lines = past_lines.filtered(lambda l: l.product_id == product)
            if not same_product_lines:
                line.sale_type = 'cross_sale'
            else:
                latest_line = same_product_lines[0]
                if line.price_subtotal > latest_line.price_subtotal:
                    line.sale_type = 'upsale'
                else:
                    line.sale_type = 'returning_customer'

    # @api.depends('move_id.partner_id', 'product_id', 'price_subtotal')
    # def _compute_sale_type(self):
    #     six_months_ago = fields.Date.today() - timedelta(days=180)
    #
    #     for line in self:
    #         partner = line.move_id.partner_id
    #         product = line.product_id
    #
    #         if not partner or not product:
    #             line.sale_type = False
    #             continue
    #
    #         base_domain = [
    #             ('move_id.partner_id', '=', partner.id),
    #             ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
    #             ('move_id.invoice_date', '>=', six_months_ago),
    #             ('move_id.state', '=', 'posted'),
    #         ]
    #         if line.id:
    #             base_domain.append(('id', '!=', line.id))
    #
    #         past_lines = self.search(base_domain)
    #         if not past_lines:
    #             line.sale_type = 'new_customer'
    #             continue
    #
    #         same_product_lines = past_lines.filtered(lambda l: l.product_id == product)
    #         if not same_product_lines:
    #             line.sale_type = 'cross_sale'
    #         else:
    #             past_max_subtotal = max(same_product_lines.mapped('price_subtotal'), default=0.0)
    #             if line.price_subtotal > past_max_subtotal:
    #                 line.sale_type = 'upsale'
    #             else:
    #                 line.sale_type = 'returning_customer'