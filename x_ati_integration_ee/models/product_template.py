# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    project_id = fields.Many2one('project.project', string="Project")

class XATIIntegrationProductProductInherit(models.Model):
    _inherit = 'product.product'

    project_id = fields.Many2one('project.project', string="Project")