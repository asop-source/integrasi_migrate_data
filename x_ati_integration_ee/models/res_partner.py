# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    @api.model
    def create(self, values):
        record = super(XResPartnerInherit, self).create(values)
        record['x_cust_code'] = self.env['ir.sequence'].next_by_code('x.customer.code.seq') or 'New'
        return record

    x_cust_code = fields.Char('Master Code')
    # x_is_xapiens_business_unit = fields.Boolean('Is a Business Unit?')
    # x_bu_code = fields.Char('Code')
    # x_client_info = fields.Char('Client Info')
    # x_client_industry_id = fields.Many2one('client.industry', string="Client Industry")
    # x_client_type = fields.Selection([('internal','Internal'),
    #                                   ('external','External')], string="Client Type")

class XClientIndustry(models.Model):
    _name = 'client.industry'
    _description = 'Client Industry'

    name = fields.Char('Name')