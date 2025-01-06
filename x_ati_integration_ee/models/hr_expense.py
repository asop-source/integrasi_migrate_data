# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationHRExpenseInherit(models.Model):
    _inherit = 'hr.expense'

    project_id = fields.Many2one('project.project', string="Project")