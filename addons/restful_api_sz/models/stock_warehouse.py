# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Product(models.Model):
    _inherit = "product.template"

    xbrand = fields.Char('品牌',required=True)
    xmodel = fields.Char('制造商型号',required=True)
    ec_state = fields.Selection([('online','上架'),('offline','下架')],required=True,default='offline',string="电商状态")

class Location(models.Model):
    _inherit = "stock.location"

    online_sale = fields.Boolean('Online Location')

class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    online_sale = fields.Boolean('Online Warehouse')

class sale_order(models.Model):
    _inherit = "sale.order"

    # 线下订单，默认仓库设为线下
    @api.model
    def _default_warehouse_id(self):
        company = self.env.user.company_id.id
        warehouse_ids = self.env['stock.warehouse'].search([('company_id', '=', company),('online_sale','=',False)], limit=1)
        return warehouse_ids

    @api.multi
    def action_confirm(self):
        for order in self:
            order.state = 'sale'
            order.confirmation_date = fields.Datetime.now()
            if self.env.context.get('send_email'):
                self.force_quotation_send()
            order.order_line.sudo()._action_procurement_create()
        if self.env['ir.values'].get_default('sale.config.settings', 'auto_done_setting'):
            self.action_done()
        return True