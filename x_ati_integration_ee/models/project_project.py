# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth

class XATIIntegrationProjectProjectInherit(models.Model):
    _inherit = 'project.project'

    project_no          = fields.Char('Project Number')
    department_id       = fields.Many2one('xpmo_partner.department', string="Department")
    pic_id              = fields.Many2one('res.partner', string="PIC")
    status_id           = fields.Many2one('xpmo_project.status', string="Status")
    project_type_id     = fields.Many2one('xpmo_project.type', string="Type")
    sequence_no         = fields.Char('Sequence')
    client_type_id      = fields.Many2one('xpmo_project.client_type', string="Client Type")
    engagement_id       = fields.Many2one('xpmo_project.engagement', string="Engagement")
    target_date         = fields.Datetime('Target Completed Date')
    recent_date         = fields.Datetime('Recent Date')
    subtasks_project_id = fields.Many2one('project.project', string="Sub-task Project")

class XATIIntegrationPartnerDepartment(models.Model):
    _name = 'xpmo_partner.department'
    _description = 'Partner Department'

    name                = fields.Char('Name')
    code                = fields.Char('Code')
    partner_id          = fields.Many2one('res.partner', string="Company")
    
class XATIIntegrationProjectStatus(models.Model):
    _name = 'xpmo_project.status'
    _description = 'Project Status'

    name                = fields.Char('Name')
    seqeunce            = fields.Integer('Sequence')

class XATIIntegrationProjectType(models.Model):
    _name = 'xpmo_project.type'
    _description = 'Project Type'

    name                = fields.Char('Name')
    short_code          = fields.Char('Short Code')
    description         = fields.Char('Description')

class XATIIntegrationProjectEngagement(models.Model):
    _name = 'xpmo_project.engagement'
    _description = 'Project Engagement'

    name                = fields.Char('Name')
    short_code          = fields.Char('Short Code')
    description         = fields.Char('Description')

class XATIIntegrationProjectClientType(models.Model):
    _name = 'xpmo_project.client_type'
    _description = 'Project Client Type'

    name                = fields.Char('Name')
    short_code          = fields.Char('Short Code')
    description         = fields.Char('Description')

