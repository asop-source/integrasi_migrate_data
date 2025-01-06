# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationPurchaseOrderInherit(models.Model):
    _inherit = 'purchase.order'

    x_attn = fields.Char(string="ATTN")
    sale_order_id = fields.Many2one('sale.order', string="SO Number")
    project_id = fields.Many2one('project.project', string="Project")
    employee_id = fields.Many2one('hr.employee', string="Information and Correspondence")
    finance_approval_id = fields.Many2one('res.users', string="Approval Finance Manager")
    finance_manager_approve_date = fields.Date(string="Finance Manager Approval Date")
    director_approval_id = fields.Many2one('res.users', string="Approval Director")
    director_approve_date = fields.Date(string="Director Approval Date")