# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationAccountMoveInherit(models.Model):
    _inherit = 'account.move'

    x_refno = fields.Char('Old Reference')
    client_attn = fields.Char('Client Attn')
    pic_fo = fields.Many2one('hr.employee', string="Finance Officer")
    pic_fm = fields.Many2one('hr.employee', string="Finance Manager")
    pic_fa = fields.Many2one('hr.employee', string="Finance Admin")

class XATIIntegrationAccountMoveLineInherit(models.Model):
    _inherit = 'account.move.line'

    xproject_id = fields.Many2one('project.project', string="Project")