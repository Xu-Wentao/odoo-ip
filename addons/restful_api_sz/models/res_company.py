# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class Company(models.Model):
    _inherit = "res.company"

    # 自动创建科目表
    @api.one
    def create_chart_of_accounts(self):
        chart_template_id = self.env.user.company_id.chart_template_id
        tax_templ_obj = self.env['account.tax.template']
        sale_tax = tax_templ_obj.search(
                    [('chart_template_id', 'parent_of', chart_template_id.id), ('type_tax_use', '=', 'sale')], limit=1,
                    order="sequence, id desc")
        purchase_tax = tax_templ_obj.search(
                    [('chart_template_id', 'parent_of', chart_template_id.id), ('type_tax_use', '=', 'purchase')], limit=1,
                    order="sequence, id desc")
        wizard = self.env['wizard.multi.charts.accounts'].create({
                'company_id': self.id,
                'chart_template_id': chart_template_id.id,
                'transfer_account_id': chart_template_id.transfer_account_id.id,
                'code_digits': chart_template_id.code_digits,
                'sale_tax_id': sale_tax.id,
                'purchase_tax_id': purchase_tax.id,
                'currency_id': chart_template_id.currency_id.id,
                'bank_account_code_prefix': chart_template_id.bank_account_code_prefix,
                'cash_account_code_prefix': chart_template_id.cash_account_code_prefix,
            })
        wizard.execute()
        self.write({'chart_template_id': chart_template_id.id})



    @api.model
    def create(self, vals):
        company = super(Company, self).create(vals)

        # 新建公司自动增加一个线上仓库
        self.env['stock.warehouse'].check_access_rights('create')
        self.env['stock.warehouse'].sudo().create({'name': company.name+u'线上仓库', 'code':'线上', 'company_id': company.id,'online_sale':True})

        locations = self.env['stock.location'].search([('complete_name','like','线上/库存'),('usage','=','internal'),('company_id','=',company.id)])

        locations[0].write({'online_sale':True})

        # 新建公司自动创建科目模板
        company.create_chart_of_accounts()

        return company
