# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationSaleOrderInherit(models.Model):
    _inherit = 'sale.order'
    
    cust_po_ref = fields.Char('Customer PO Reference')
    x_attention = fields.Char('Client Attn')

class XATIIntegrationSaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'

    project_id = fields.Many2one('project.project', string="Project")