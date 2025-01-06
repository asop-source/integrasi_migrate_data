# -*- coding: utf-8 -*-


import pytz
import json

from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import xmlrpc.client
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta, date

class Integration(models.Model):
    _name = 'integration.integration'
    _description = 'Integration'

    name            = fields.Char('Name')
    url_data        = fields.Char('URL')
    database        = fields.Char('Database')
    username        = fields.Char('Username')
    password        = fields.Char('Password')
    integration_ids = fields.One2many('integration.line', 'integration_id', string="Line")
    active          = fields.Boolean("Active", default=True)

    def test_connection(self):
        for rec in self:
            if not rec.url_data:
                raise UserError(_('URL Empty!!!'))

            if not rec.database:
                raise UserError(_('DATABASE Empty!!!'))

            if not rec.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not rec.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if rec.username and rec.password:
                today = fields.Datetime.now()
                server_url = rec.url_data
                db = rec.database
                username = rec.username
                password = rec.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                try:
                    res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                    res_auth_json = res_auth.json()
                    if res_auth_json:
                        response = res_auth_json['result']
                        if response['is_system'] == True:
                            title = _("Connection Test Succeeded!")
                            message = _("Everything seems properly set up!")
                            return {
                                'type': 'ir.actions.client',
                                'tag': 'display_notification',
                                'params': {
                                    'title': title,
                                    'message': message,
                                    'sticky': False,
                                }
                            }
                except Exception as exc:
                    title = _("Connection Failed!")
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': title,
                            'message': exc,
                            'sticky': False,
                        }
                    }


class IntegrationLine(models.Model):
    _name = 'integration.line'
    _description = 'Integration Line'

    integration_id  = fields.Many2one('integration.integration')
    model_table     = fields.Char('Model')
    end_point       = fields.Char('End Point')
    function        = fields.Char(string='Function', default='read_create_res_partner', help="Function Used in coding")
    headers         = fields.Char(string='Headers', default='{"Content-type": "application/json"}')
    domain_get      = fields.Char('Domain Get', default="('active', '=', True)", help="Domain to filter GET data from other Server")
    domain_post     = fields.Char('Domain Post', default="('email', '=', rp_data['email'])", help="Domain to filter Search data to Current Server")
    value_get       = fields.Text(string='Value Get', help="Value which field to GET data from other Server")
    value_post      = fields.Text(string='Value Post', help="Value POST data to Current Server. ex: rp_data['name'] --> for res.partner")
    is_used         = fields.Boolean(string='Is Used',default=True)

class IntegrationLog(models.Model):
    _name = 'integration.log'
    _description = 'Integration Log'

    name            = fields.Char('Name')
    status          = fields.Integer('Status')
    model_table     = fields.Char('Model')
    function        = fields.Char('Function')
    headers         = fields.Char(string='Headers', default='{"Content-type": "application/json"}')
    endpoint        = fields.Char('Endpoint')
    request         = fields.Text('Payload')
    response        = fields.Text('Response')
    sync_at         = fields.Datetime('Sync At')
    success_sync    = fields.Boolean('Sync?')
    message         = fields.Text('Message')
    
    def integration_log(self, name="", status=0, model_table="", function="", endpoint="", request="", exc=False, success_sync=False, message=""):
        integration_log = self.env['integration.log'].search([('name','=',name), ('model_table','=',model_table), ('function','=',function)])
        error_message = exc if exc else ""

        if integration_log:
            #Edit to log table
            integration_log.sudo().write({
                'name': name,
                'status': status,
                'model_table': model_table,
                'function': function,
                'endpoint': endpoint,
                'request': request,
                'response': error_message,
                'sync_at': datetime.now(),
                'success_sync': success_sync,
                'message': message,
            })
        else:
            #Create to log table
            self.env['integration.log'].sudo().create({
                'name': name,
                'status': status,
                'model_table': model_table,
                'function': function,
                'endpoint': endpoint,
                'request': request,
                'response': error_message,
                'sync_at': datetime.now(),
                'success_sync': success_sync,
                'message': message,
            })

        self.env.cr.commit()
        return True

    def _get_function(self,function=''):
        return self.env['integration.line'].sudo().search([('is_used','=',True),('function','=',function)],limit=1)

    def read_create_res_partner(self,interval=0):
        model_function = self._get_function(function='read_create_res_partner')
        datas = []
        if model_function:
            if len(model_function) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(model_function.mapped('function')))))
            
            if not model_function.integration_id and not model_function.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not model_function.integration_id and not model_function.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if model_function.integration_id and model_function.integration_id.username and model_function.integration_id.password:
                today = fields.Datetime.now()
                url = model_function.integration_id.url_data
                db = model_function.integration_id.database
                username = model_function.integration_id.username
                password = model_function.integration_id.password
                
                common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
                uid = common.authenticate(db, username, password, {})
                
                model = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
                vals = {'fields': ['name', 'company_type', 'type', 'email', 'street', 'street2', 'city', 'state_id']}

                if interval == 0:
                    get_res_partner = model.execute_kw(db, uid, password, 'res.partner', 
                                                      'search_read', [[('active', '=', True)]], 
                                                      vals)
                else:
                    start_date, end_date = self._set_timezone(date=today, interval=interval)
                    get_res_partner = model.execute_kw(db, uid, password, 'res.partner', 
                                                      'search_read', [[('active', '=', True), 
                                                                       ('create_date', '>=', start_date), 
                                                                       ('create_date', '<=', end_date)]], 
                                                      vals)

                print("GET Res Partner", get_res_partner)
                for rp_data in get_res_partner:
                    res_partner = self.env['res.partner'].sudo()
                    res_country_state = self.env['res.country.state'].sudo()

                    state_id = False
                    if rp_data['state_id']:
                        obj_search_state = res_country_state.search([('name', '=', rp_data['state_id'][1])], limit=1)
                        if obj_search_state:
                            state_id = obj_search_state.id
                        else:
                            state_create = res_country_state.sudo().create({'name': rp_data['state_id'][1]})
                            state_id = state_create.id
                            # self.integration_log("State Not Found!", 400, "res.country.state", "read_create_res_partner", today, rp_data['state_id'], "Warning!. State Not Found.")
                    else:
                        state_id = False

                    search_res_partner = res_partner.search([('email', '=', rp_data['email'])])
                    
                    res_partner_vals = {'name': rp_data['name'],
                                        'company_type': rp_data['company_type'],
                                        'type': rp_data['type'],
                                        'email': rp_data['email'],
                                        'street': rp_data['street'],
                                        'street2': rp_data['street2'],
                                        'city': rp_data['city'],
                                        'state_id': state_id,}
                    # try:
                    if search_res_partner:
                        try:
                            update = res_partner.sudo().write(res_partner_vals)
                        except Exception as exc:
                            self.integration_log("update res.partner", 400, "res.partner", "read_create_res_partner", today, "'fields': ['name', 'company_type', 'email']", exc)
                    else:
                        try:
                            create = res_partner.sudo().create(res_partner_vals)
                        except Exception as exc:
                            self.integration_log("create res.partner", 400, "res.partner", "read_create_res_partner", today, "'fields': ['name', 'company_type', 'email']", exc)

    def _cron_res_partner(self, **kwargs):
        data = self.get_res_partner(interval=kwargs.get('interval'))
    
    def _cron_product_template(self, **kwargs):
        data = self.get_product(interval=kwargs.get('interval'))

    def _cron_product_pricelist(self, **kwargs):
        data = self.get_pricelist(interval=kwargs.get('interval'))
        
    def _cron_unit_of_measure(self, **kwargs):
        data = self.get_uom(interval=kwargs.get('interval'))

    def _cron_payment_terms(self, **kwargs):
        data = self.get_payment_terms(interval=kwargs.get('interval'))

    def _cron_project_project(self, **kwargs):
        data = self.get_project(interval=kwargs.get('interval'))

    def _cron_sales_order(self, **kwargs):
        data = self.get_sale_order(interval=kwargs.get('interval'))

    def _cron_purchase_order(self, **kwargs):
        data = self.get_purchase_order(interval=kwargs.get('interval'))

    def _cron_journal_entries(self, **kwargs):
        data = self.get_journal_entries(interval=kwargs.get('interval'))

    def _set_timezone(self,date=fields.Datetime.now(), interval=2):
        # iso 8601
        ISO_8601 = "%Y-%m-%d %H:%M:%S"
        tz = pytz.timezone(self.env.user.tz) if self.env.user.tz else pytz.utc
        datetimezone = pytz.utc.localize(date).astimezone(tz)
        print("Datetimezone====", datetimezone)
        # strftime
        if interval > 0:
            start_date = datetimezone + relativedelta(hours=-interval)
            start_date = start_date.strftime(ISO_8601)
            end_date = datetimezone.strftime(ISO_8601)
        else:
            start_date = ""
            end_date = ""
        return start_date, end_date

    def _get_end_point(self,end_point=''):
        return self.env['integration.line'].sudo().search([('is_used','=',True),('end_point','=',end_point)],limit=1)
        
    def get_res_partner(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_res_partner/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_res_partner = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    if get_res_partner.json().get("result") and get_res_partner.json().get("result").get("status") == 200:
                        data = get_res_partner.json()
                        print("Data=====", data)
                        response = data['result']['response']
                        result_data = []
                        for res in response:
                            res_partner = self.env['res.partner'].sudo()
                            res_country_state = self.env['res.country.state'].sudo()
                            res_country_country = self.env['res.country'].sudo()
                            res_account_account = self.env['account.account'].sudo()
                            res_client_industry = self.env['client.industry'].sudo()

                            parent_id = False
                            obj_search_parent = res_partner.search([('name', '=', res['parent_name'])], limit=1)
                            if obj_search_parent:
                                parent_id = obj_search_parent.id
                            else:
                                parent_id = False

                            state_id = False
                            if res['state_id']:
                                obj_search_state = res_country_state.search([('name', '=', res['state_id'])], limit=1)
                                if obj_search_state:
                                    state_id = obj_search_state.id
                                else:
                                    state_id = False
                            else:
                                state_id = False

                            country_id = False
                            if res['country_id']:
                                obj_search_country = res_country_country.search([('name', '=', res['country_id'])], limit=1)
                                if obj_search_country:
                                    country_id = obj_search_country.id
                                else:
                                    country_id = False
                            else:
                                country_id = False

                            account_payable_id = False
                            # if res['property_account_payable_id']['code']:
                            obj_search_account_payable = res_account_account.search([('code', '=', res['property_account_payable_code'])], limit=1)
                            if obj_search_account_payable:
                                account_payable_id = obj_search_account_payable.id
                            else:
                                coa_payable = {'code': res['property_account_payable_code'],
                                            'name': res['property_account_payable_name'],
                                            #    'user_type_id': res['property_account_payable_user_type_id'],
                                            'reconcile': res['property_account_payable_reconcile']}
                                account_payable_id = res_account_account.sudo().create(coa_payable).id

                            account_receivable_id = False
                            # if res['property_account_receivable_id']['code']:
                            obj_search_account_receivable = res_account_account.search([('code', '=', res['property_account_receivable_code'])], limit=1)
                            if obj_search_account_receivable:
                                account_receivable_id = obj_search_account_receivable.id
                            else:
                                coa_receivable = {'code': res['property_account_receivable_code'],
                                                'name': res['property_account_receivable_name'],
                                                #   'user_type_id': res['property_account_receivable_user_type_id'],
                                                'reconcile': res['property_account_receivable_reconcile']}
                                account_receivable_id = res_account_account.sudo().create(coa_receivable).id
                            
                            client_industry_id = False
                            if res['client_industry_id']:
                                obj_search_client_industry = res_client_industry.search([('name', '=', res['client_industry_name'])], limit=1)
                                if obj_search_client_industry:
                                    client_industry_id = obj_search_client_industry.id
                                else:
                                    client_industry_id = res_client_industry.sudo().create({'name': res['client_industry_name']}).id
                            else:
                                client_industry_id = False
                            
                            search_res_partner = None
                            if res['x_cust_code']:
                                search_res_partner = res_partner.search([('x_cust_code', '=', res['x_cust_code'])])
                            else:
                                search_res_partner = res_partner.search([('name', '=', res['name'])])

                            res_partner_vals = {'x_cust_code': res['x_cust_code'],
                                                'name': res['name'],
                                                'parent_id': parent_id,
                                                'type': res['type'],
                                                'company_type': res['company_type'],
                                                'street': res['street'],
                                                'street2': res['street2'],
                                                'city': res['city'],
                                                'state_id': state_id,
                                                'zip': res['zip'],
                                                'country_id': country_id,
                                                # 'x_is_xapiens_business_unit': res['is_xapiens_business_unit'],
                                                # 'x_bu_code': res['bu_code'],
                                                # 'x_client_info': res['client_info'],
                                                # 'x_client_industry_id': client_industry_id,
                                                # 'x_client_type': res['client_type'],
                                                'phone': res['phone'],
                                                'mobile': res['mobile'],
                                                'email': res['email'],
                                                'property_account_payable_id': account_payable_id,
                                                'property_account_receivable_id': account_receivable_id,}                  
                            if search_res_partner:
                                update = search_res_partner.sudo().write(res_partner_vals)
                            else:
                                create = res_partner.sudo().create(res_partner_vals)
                    if get_res_partner.json().get('error'):
                        self.integration_log(str(res['name']), 404, "res.partner", "get_res_partner", "/get_res_partner/v1-api-ent", str(res), get_res_partner.json().get('error'), False, "Failed Sync")
                    elif get_res_partner.json().get("result") or get_res_partner.json().get("result").get('status') == 400:
                        self.integration_log(str(res['name']), 400, "res.partner", "get_res_partner", "/get_res_partner/v1-api-ent", str(res), get_res_partner.json().get("result").get('message'), False, "Failed Sync")
                except Exception as exc:
                    self.integration_log(str(res['name']), 500, "res.partner", "get_res_partner", "/get_res_partner/v1-api-ent", str(res), exc, False, "Failed Sync")

    def get_product(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_product_master/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_product = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    if get_product.json().get("result") and get_product.json().get("result").get("status") == 200:
                        data = get_product.json()
                        print("Data=====", data)
                        response = data['result']['response']
                        result_data = []
                        for res in response:
                            product_template = self.env['product.template'].sudo()
                            product_product = self.env['product.product'].sudo()
                            product_category = self.env['product.category'].sudo()
                            product_uom = self.env['uom.uom'].sudo()
                            product_project = self.env['project.project'].sudo()
                            
                            category_id = False
                            obj_search_prod_categ = product_category.search([('name', '=', res['categ_name'])], limit=1)
                            if obj_search_prod_categ:
                                category_id = obj_search_prod_categ.id
                            else:
                                category_id = product_category.sudo().create({'name': res['categ_name']}).id

                            uom_id = False
                            obj_search_uom = product_uom.search([('name', '=', res['uom_name'])], limit=1)
                            if obj_search_uom:
                                uom_id = obj_search_uom.id
                            else:
                                uom_id = product_uom.sudo().create({'name': res['uom_name']}).id    

                            uom_po_id = False
                            obj_search_uom_po = product_uom.search([('name', '=', res['uom_po_name'])], limit=1)
                            if obj_search_uom_po:
                                uom_po_id = obj_search_uom_po.id
                            else:
                                uom_po_id = product_uom.sudo().create({'name': res['uom_po_name']}).id  

                            project_id = False
                            if res['project_name']:
                                obj_search_project = product_project.search([('name', '=', res['project_name'])], limit=1)
                                if obj_search_project:
                                    project_id = obj_search_project.id
                                else:
                                    project_id = product_project.sudo().create({'name': res['project_name']}).id  
                            else:
                                project_id = False

                            taxes_id = []
                            for tax_id in res['taxes_name']:
                                account_tax_obj = self.env['account.tax'].sudo().search([
                                    ('name', '=', tax_id)
                                ], limit=1)
                                if account_tax_obj:
                                    taxes_id.append(account_tax_obj.id)             

                            search_product_template = product_template.search([('name', '=', res['name']), ('categ_id', '=', category_id)], limit = 1)
                            res_product_temp_vals = {'name': res['name'],
                                                    'sale_ok': res['sale_ok'],
                                                    'purchase_ok': res['purchase_ok'],
                                                    'can_be_expensed': res['can_be_expensed'],
                                                    'type': res['type'],
                                                    'default_code': res['default_code'],
                                                    'categ_id': category_id,
                                                    'list_price': res['list_price'],
                                                    'uom_id': uom_id,
                                                    'uom_po_id': uom_po_id,
                                                    'tracking': res['tracking'],
                                                    'project_id': project_id,
                                                    'barcode': res['barcode'],
                                                    'taxes_id': taxes_id}
                            
                            
                            # if create:
                            #     self.env.cr.execute("""insert into product_product(product_tmpl_id,default_code,barcode) 
                            #                         VALUES('"""+ str(create.id) +"""','"""+ str(vals.get('default_code')) +"""','"""+ str(vals.get('barcode')) +"""') returning id;""")
                            
                            if search_product_template:
                                update = search_product_template.sudo().write(res_product_temp_vals)
                                search_product_product = product_product.search([('product_tmpl_id', '=', search_product_template.id)])
                                if search_product_product:
                                    update_prod_prod = search_product_product.sudo().write({'product_tmpl_id': search_product_template.id, 
                                                                                            'default_code': res['default_code'] or "",
                                                                                            'barcode': res['barcode'] or ""})
                            else:
                                create_tmpl_id = product_template.sudo().create(res_product_temp_vals)
                                if create_tmpl_id:
                                    self.env.cr.execute("""insert into product_product(product_tmpl_id,default_code,barcode) 
                                                        VALUES('"""+ str(create_tmpl_id.id) +"""','"""+ str(res['default_code']) +"""','"""+ str(res['barcode']) +"""') returning id;""")
                                    result = self.env.cr.dictfetchone()
                                    print("Result", result)
                                    product_id = int(result['id'])
                                    
                    if get_product.json().get('error'):
                        self.integration_log(str(res['name']), 404, "product.template", "get_product", "/get_product_master/v1-api-ent", str(res), get_product.json().get('error'), False, "Failed Sync")
                    elif get_product.json().get("result") or get_product.json().get("result").get('status') == 400:
                        self.integration_log(str(res['name']), 400, "product.template", "get_product", "/get_product_master/v1-api-ent", str(res), get_product.json().get("result").get('message'), False, "Failed Sync")
                except Exception as exc:
                    self.integration_log(str(res['name']), 500, "product.template", "get_product", "/get_product_master/v1-api-ent", str(res), exc, False, "Failed Sync")
    
    def get_pricelist(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_pricelist_master/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_pricelist = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    data = get_pricelist.json()
                    print("Data=====", data)
                    response = data['result']['response']
                    result_data = []
                    for res in response:
                        pricelist = self.env['product.pricelist'].sudo()
                        res_currency = self.env['res.currency'].sudo()
                        
                        currency_id = False
                        obj_search_currency = res_currency.search([('name', '=', res['currency_name'])], limit=1)
                        if obj_search_currency:
                            currency_id = obj_search_currency.id
                        else:
                            currency_id = False

                        lines = [(5, 0, 0)]
                        line_ids = res['item_ids']
                        for item_ids in line_ids:
                            currency_line_id = False
                            obj_search_currency_line = res_currency.search([('name', '=', item_ids['currency_name'])], limit=1)
                            if obj_search_currency_line:
                                currency_line_id = obj_search_currency_line.id
                            else:
                                currency_line_id = False
                            vals_line = {'applied_on': item_ids['applied_on'],
                                         'currency_id': currency_line_id,
                                         'compute_price': item_ids['compute_price'],
                                         'min_quantity': item_ids['min_quantity'],
                                         'date_start': item_ids['date_start'],
                                         'date_end': item_ids['date_end'],
                                         'fixed_price': item_ids['fixed_price']}
                            lines.append((0, 0, vals_line))

                        country_group_ids = []
                        for country_group in res['country_group_name']:
                            country_group_obj = self.env['res.country.group'].sudo().search([
                                ('name', '=', country_group)
                            ], limit=1)
                            if country_group_obj:
                                country_group_ids.append(country_group_obj.id)

                        search_pricelist = pricelist.search([('name', '=', res['name'])])
                        res_pricelist_vals = {'name': res['name'],
                                              'currency_id': currency_id,
                                              'country_group_ids': country_group_ids,
                                              'discount_policy': res['discount_policy'],
                                              'item_ids': lines}
                        
                        if search_pricelist:
                            update = search_pricelist.sudo().write(res_pricelist_vals)
                        else:
                            create = pricelist.sudo().create(res_pricelist_vals)
                except Exception as exc:
                    self.integration_log("/get_pricelist_master/v1-api-ent", 400, "product.pricelist", "get_pricelist", today, "", exc)
    
    def get_uom(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_uom_master/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_uom = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    data = get_uom.json()
                    print("Data=====", data)
                    response = data['result']['response']
                    result_data = []
                    for res in response:
                        obj_uom = self.env['uom.uom'].sudo()
                        obj_uom_category = self.env['uom.category'].sudo()
                        
                        category_id = False
                        obj_search_currency = obj_uom_category.search([('name', '=', res['category_name'])], limit=1)
                        if obj_search_currency:
                            category_id = obj_search_currency.id
                        else:
                            category_id = obj_uom_category.sudo().create({'name': res['category_name']}).id

                        search_uom = obj_uom.search([('name', '=', res['name'])])
                        res_uom_vals = {'name': res['name'],
                                        'category_id': category_id,
                                        'uom_type': res['uom_type'],
                                        'factor': res['factor_inv'],
                                        'rounding': res['rounding']}
                        
                        if search_uom:
                            update = search_uom.sudo().write(res_uom_vals)
                        else:
                            create = obj_uom.sudo().create(res_uom_vals)
                except Exception as exc:
                    self.integration_log("/get_uom_master/v1-api-ent", 400, "uom.uom", "get_uom", today, "", exc)
    
    def get_payment_terms(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_payment_terms_master/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_payment_terms = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    data = get_payment_terms.json()
                    print("Data=====", data)
                    response = data['result']['response']
                    result_data = []
                    for res in response:
                        payment_term = self.env['account.payment.term'].sudo()
                        payment_term_line = self.env['account.payment.term.line'].sudo()
                        lines = [(5, 0, 0)]
                        line_ids = res['line_ids']
                        for term_line in line_ids:
                            vals_line = {'value': term_line['value'],
                                        'value_amount': term_line['value_amount'],
                                        'days': term_line['days'],
                                        # 'option': term_line['option'],
                                        'days_after': term_line['day_of_the_month']}
                            lines.append((0, 0, vals_line))

                        search_payment_term = payment_term.search([('name', '=', res['name'])])
                        payment_term_vals = {'name': res['name'],
                                            'note': res['note'],
                                            'line_ids': lines}
                        
                        if search_payment_term:
                            update = search_payment_term.sudo().write(payment_term_vals)
                        else:
                            create = payment_term.sudo().create(payment_term_vals)
                except Exception as exc:
                    self.integration_log("/get_payment_terms_master/v1-api-ent", 400, "account.payment.term", "get_payment_terms", today, payment_term_vals, exc)
    
    def get_project(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_project_data/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_project = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    if get_project.json().get("result") and get_project.json().get("result").get("status") == 200:
                        data = get_project.json()
                        print("Data=====", data)
                        response = data['result']['response']
                        result_data = []
                        for res in response:
                            print("Masuk Sini")
                            project = self.env['project.project'].sudo()
                            res_users = self.env['res.users'].sudo()
                            res_partner = self.env['res.partner'].sudo()
                            analytic_plan = self.env['account.analytic.plan'].sudo()
                            partner_department = self.env['xpmo_partner.department'].sudo()
                            project_status = self.env['xpmo_project.status'].sudo()
                            project_type = self.env['xpmo_project.type'].sudo()
                            project_engagement = self.env['xpmo_project.engagement'].sudo()
                            project_client_type = self.env['xpmo_project.client_type'].sudo()
                            analytic_account = self.env['account.analytic.account'].sudo()

                            user_id = False
                            obj_search_user = res_users.search([('name', '=', res['user_name'])], limit=1)
                            if obj_search_user:
                                user_id = obj_search_user.id
                            else:
                                message = _('User Login for [%s] not registered in system' %(res['user_name']))
                                self.integration_log(str(res['name']), 404, "project.project", "get_project", "/get_project_data/v1-api-ent", str(res), message, False, "Project Manager Not Found")

                            partner_id = False
                            if res['partner_name']:
                                if res['x_cust_code']:
                                    obj_search_partner = res_partner.search([('x_cust_code', '=ilike', res['x_cust_code'])], limit=1)
                                    if obj_search_partner:
                                        partner_id = obj_search_partner.id
                                else:
                                    obj_search_partner_code = res_partner.search([('name', '=ilike', res['partner_name'])], limit=1)
                                    if obj_search_partner_code:
                                        partner_id = obj_search_partner_code.write({'x_cust_code': res['x_cust_code']}).id
                                    else:
                                        partner_id = res_partner.create({'name': res['partner_name'], 'x_cust_code': res['x_cust_code']}).id
                            else:
                                partner_id = False

                            department_id = False
                            if res['department_name']:
                                obj_search_department = partner_department.search([('name', '=ilike', res['department_name'])], limit=1)
                                if obj_search_department:
                                    department_id = obj_search_department.id
                                else:
                                    # department_partner_id = False
                                    search_department_partner_id = res_partner.search([('name', '=ilike', res['department_partner_name'])], limit=1)
                                    if search_department_partner_id:
                                        department_partner_id = search_department_partner_id.id
                                    else:
                                        department_partner_id = False

                                    department_vals = {'name': res['department_name'],
                                                        'code': res['department_code'] or "",
                                                        'partner_id': department_partner_id or False}
                                    department_id = partner_department.sudo().create(department_vals).id
                            else:
                                department_id = False

                            pic_id = False
                            if res['pic_name']:
                                if res['pic_code']:
                                    obj_search_pic = res_partner.search([('x_cust_code', 'ilike', res['pic_code'])], limit=1)
                                    if obj_search_pic:
                                        pic_id = obj_search_pic.id
                                else:
                                    obj_search_pic_name = res_partner.search([('name', '=ilike', res['pic_name'])], limit=1)
                                    if obj_search_pic_name:
                                        pic_id = obj_search_pic_name.write({'x_cust_code': res['pic_code']}).id
                                    else:
                                        pic_id = res_partner.create({'name': res['pic_name'], 'x_cust_code': res['pic_code']}).id
                            else:
                                pic_id = False

                            status_id = False
                            if res['status_name']:
                                obj_search_status = project_status.search([('name', 'ilike', res['status_name'])], limit=1)
                                if obj_search_status:
                                    status_id = obj_search_status.id
                                else:
                                    status_id = project_status.sudo().create({'name': res['status_name'], 
                                                                              'seqeunce': res['status_sequence']}).id
                            else:
                                status_id = False

                            project_type_id = False
                            if res['project_type_name']:
                                obj_search_project_type = project_type.search([('name', 'ilike', res['project_type_name'])], limit=1)
                                if obj_search_project_type:
                                    project_type_id = obj_search_project_type.id
                                else:
                                    project_type_id = project_type.sudo().create({'name': res['project_type_name'], 
                                                                                  'short_code': res['project_type_short_code'], 
                                                                                  'description': res['project_type_description']}).id
                            else:
                                project_type_id = False

                            client_type_id = False
                            if res['client_type_name']:
                                obj_search_client_type = project_client_type.search([('name', 'ilike', res['client_type_name'])], limit=1)
                                if obj_search_client_type:
                                    client_type_id = obj_search_client_type.id
                                else:
                                    client_type_id = project_client_type.sudo().create({'name': res['client_type_name'], 
                                                                                        'short_code': res['client_type_short_code'], 
                                                                                        'description': res['client_type_description']}).id
                            else:
                                client_type_id = False

                            engagement_id = False
                            if res['engagement_name']:
                                obj_search_engagement = project_engagement.search([('name', 'ilike', res['engagement_name'])], limit=1)
                                if obj_search_engagement:
                                    engagement_id = obj_search_engagement.id
                                else:
                                    engagement_id = project_engagement.sudo().create({'name': res['engagement_name'], 
                                                                                      'short_code': res['engagement_short_code'], 
                                                                                      'description': res['engagement_description']}).id
                            else:
                                engagement_id = False


                            analytic_account_id = False
                            if res['analytic_account_name']:
                                obj_search_analytic_account = analytic_account.search([('name', 'ilike', res['analytic_account_name'])], limit=1)
                                if obj_search_analytic_account:
                                    analytic_account_id = obj_search_analytic_account.id
                                else:
                                    search_analytic_partner = res_partner.search([('name', 'ilike', 'analytic_account_partner_name')], limit = 1)
                                    if search_analytic_partner:
                                        analytic_partner_id = search_analytic_partner.id
                                    else:
                                        analytic_partner_id = res_partner.search([('name', '=ilike', res['analytic_account_partner_name'])], limit=1).id
                                        # analytic_partner_id = False
                                    search_account_analytic_plan = analytic_plan.search([('name', 'ilike', 'Default')], limit = 1)
                                    analytic_account_vals = {'name': res['analytic_account_name'],
                                                            'partner_id': analytic_partner_id,
                                                            'plan_id': search_account_analytic_plan.id}
                                    analytic_account_id = analytic_account.sudo().create(analytic_account_vals).id
                            else:
                                analytic_account_id = False

                            subtask_project_id = False
                            if res['subtask_project_name']:
                                obj_search_subtask_project = project.search([('name', 'ilike', res['subtask_project_name'])], limit=1)
                                if obj_search_subtask_project:
                                    subtask_project_id = obj_search_subtask_project.id
                                else:
                                    subtask_project_id = project.sudo().create({'name': res['subtask_project_name']}).id
                            else:
                                subtask_project_id = False

                            search_project = project.search([('name', '=', res['name']),('project_no', '=', res['project_no'])])
                            print("Project===", search_project)
                            project_vals = {'project_no': res['project_no'] or "",
                                            'name': res['name'] or "",
                                            'label_tasks': res['label_tasks'] or "",
                                            'user_id': user_id or False,
                                            'partner_id': partner_id or False,
                                            'department_id': department_id or False,
                                            'pic_id': pic_id or False,
                                            'status_id': status_id or False,
                                            'project_type_id': project_type_id or False,
                                            'engagement_id': engagement_id or False,
                                            'sequence_no': res['sequence_no'] or "",
                                            'client_type_id': client_type_id or False,
                                            'target_date': res['target_date'] or False,
                                            'recent_date': res['recent_date'] or False,
                                            'date_start': res['date_start'] or False,
                                            'date': res['date'] or False,
                                            'analytic_account_id': analytic_account_id or False,
                                            'privacy_visibility': res['privacy_visibility'] or "",
                                            'subtasks_project_id': subtask_project_id or False}
                            
                            if search_project:
                                update = search_project.sudo().write(project_vals)
                            else:
                                create = project.sudo().create(project_vals)
                    if get_project.json().get('error'):
                        self.integration_log(str(res['name']), 404, "project.project", "get_project", "/get_project_data/v1-api-ent", str(res), get_project.json().get('error'), False, "Failed Sync")
                    elif get_project.json().get("result") or get_project.json().get("result").get('status') == 400:
                        self.integration_log(str(res['name']), 400, "project.project", "get_project", "/get_project_data/v1-api-ent", str(res), get_project.json().get("result").get('message'), False, "Failed Sync")
                except Exception as exc:
                    self.integration_log(str(res['name']), 500, "project.project", "get_project", "/get_project_data/v1-api-ent", str(res), exc, False, "Failed Sync")

    def hit_create_product(self):
        vals = {
            "id": 5715,
            "name": "Data Created from XBase",
            "sale_ok": True,
            "purchase_ok": True,
            "can_be_expensed": False,
            "type": "service",
            "default_code": "",
            "categ_id": 14,
            "categ_name": "Consumable",
            "list_price": 1,
            "uom_id": 147,
            "uom_name": "User",
            "uom_po_id": 147,
            "uom_po_name": "User",
            "tracking": "none",
            "project_id": False,
            "project_name": "",
            "barcode": "",
            "taxes_id": False,
            "taxes_name": "",
            "active": True
        }
        self.create_product(vals)
    
    def create_product(self, vals):
        data = 0
        if vals:
            product_template = self.env['product.template'].sudo()
            product_product = self.env['product.product'].sudo()
            product_category = self.env['product.category'].sudo()
            product_uom = self.env['uom.uom'].sudo()
            product_project = self.env['project.project'].sudo()
            
            category_id = False
            obj_search_prod_categ = product_category.search([('name', '=', vals.get('categ_name'))], limit=1)
            if obj_search_prod_categ:
                category_id = obj_search_prod_categ.id
            else:
                category_id = product_category.sudo().create({'name': vals.get('categ_name')}).id

            uom_id = False
            obj_search_uom = product_uom.search([('name', '=', vals.get('uom_name'))], limit=1)
            if obj_search_uom:
                uom_id = obj_search_uom.id
            else:
                uom_id = product_uom.sudo().create({'name': vals.get('uom_name')}).id    

            uom_po_id = False
            obj_search_uom_po = product_uom.search([('name', '=', vals.get('uom_po_name'))], limit=1)
            if obj_search_uom_po:
                uom_po_id = obj_search_uom_po.id
            else:
                uom_po_id = product_uom.sudo().create({'name': vals.get('uom_po_name')}).id  

            project_id = False
            if vals.get('project_name'):
                obj_search_project = product_project.search([('name', '=', vals.get('project_name'))], limit=1)
                if obj_search_project:
                    project_id = obj_search_project.id
                else:
                    project_id = product_project.sudo().create({'name': vals.get('project_name')}).id
            else:
                project_id = False

            taxes_id = []
            for tax_id in vals.get('taxes_name'):
                account_tax_obj = self.env['account.tax'].sudo().search([
                    ('name', '=', tax_id)
                ], limit=1)
                if account_tax_obj:
                    taxes_id.append(account_tax_obj.id)             

            # search_product_template = product_template.search([('name', '=', vals.get('name')), ('categ_id', '=', category_id)], limit = 1)
            res_product_temp_vals = {'name': vals.get('name'),
                                    'sale_ok': vals.get('sale_ok'),
                                    'purchase_ok': vals.get('purchase_ok'),
                                    'can_be_expensed': vals.get('can_be_expensed'),
                                    'type': vals.get('type'),
                                    'default_code': vals.get('default_code'),
                                    'categ_id': category_id,
                                    'list_price': vals.get('list_price'),
                                    'uom_id': uom_id,
                                    'uom_po_id': uom_po_id,
                                    'tracking': vals.get('tracking'),
                                    'project_id': project_id,
                                    'barcode': vals.get('barcode'),
                                    'taxes_id': taxes_id}
            
            create = product_template.sudo().create(res_product_temp_vals)
            print("Sukses Create Product Template", create)
            if create:
                self.env.cr.execute("""insert into product_product(product_tmpl_id,default_code,barcode) 
                                    VALUES('"""+ str(create.id) +"""','"""+ str(vals.get('default_code')) +"""','"""+ str(vals.get('barcode')) +"""') returning id;""")
                #result = self.env.cr.fetchone()
                result = self.env.cr.dictfetchone()
                print("Result", result)
                product_id = int(result['id'])
                # prod_prod_vals = {'product_tmpl_id': create.id,
                #                     'default_code': vals.get('default_code'),
                #                     'barcode': vals.get('barcode'),
                #                     'project_id': project_id}
                # create_prod_prod = product_product.sudo().create(prod_prod_vals)
                print("New Product", product_id)
                data = product_id
                print("Data", data)
        return data


    def get_sale_order(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_sale_orders/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_sale_order = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    if get_sale_order.json().get("result") and get_sale_order.json().get("result").get("status") == 200:
                        data = get_sale_order.json()
                        print("Data=====", data)
                        response = data['result']['response']
                        result_data = []
                        for res in response:
                            lines = [(5, 0, 0)]
                            order_line = res['order_line']
                            for so_line in order_line:
                                products = so_line['products']
                                print("Products====", products)
                                rec_product = self.env['product.product'].sudo()
                                rec_project = self.env['project.project'].sudo()
                                rec_uom_uom = self.env['uom.uom'].sudo()
                                
                                product_id = False
                                obj_search_product = rec_product.search([('name', '=', so_line['product_name'])], limit=1)
                                # obj_search_product = rec_product.search([('name', '=', so_line['product_name']), ('categ_id.name', '=', so_line['product_categ_name'])], limit=1)
                                if obj_search_product:
                                    product_id = obj_search_product.id
                                    print("Product Ada=======", product_id)
                                else:
                                    created_product = self.create_product(products)
                                    print("created_product=====", created_product)
                                    product_id = created_product

                                project_id = False
                                if so_line['project_name']:
                                    obj_search_project = rec_project.search([('name', '=', so_line['project_name'])], limit=1)
                                    if obj_search_project:
                                        project_id = obj_search_project.id
                                    else:
                                        project_id = rec_project.sudo().create({'name': so_line['project_name']}).id
                                else:
                                    project_id = False

                                product_uom_id = False
                                obj_search_uom = rec_uom_uom.search([('name', '=', so_line['uom_name'])], limit=1)
                                if obj_search_uom:
                                    product_uom_id = obj_search_uom.id
                                else:
                                    product_uom_id = False

                                tax_ids = []
                                for tax_id in so_line['tax_name']:
                                    account_tax_obj = self.env['account.tax'].sudo().search([
                                        ('name', '=', tax_id)
                                    ], limit=1)
                                    if account_tax_obj:
                                        tax_ids.append(account_tax_obj.id)


                                vals_line = {
                                            'product_id': product_id,
                                            'sequence': so_line['sequence'],
                                            'display_type': so_line['display_type'],
                                            'name': so_line['name'],
                                            'project_id': project_id,
                                            'product_uom_qty': so_line['product_uom_qty'],
                                            'product_uom': product_uom_id,
                                            'price_unit': so_line['price_unit'],
                                            'tax_id': tax_ids,
                                            'discount': so_line['discount'],
                                            'customer_lead': so_line['customer_lead'],
                                            'price_subtotal': so_line['price_subtotal']}
                                lines.append((0, 0, vals_line))

                            sale_order = self.env['sale.order'].sudo()
                            res_partner = self.env['res.partner'].sudo()
                            pricelist = self.env['product.pricelist'].sudo()
                            stock_warehouse = self.env['stock.warehouse'].sudo()
                            payment_term = self.env['account.payment.term'].sudo()
                            res_currency = self.env['res.currency'].sudo()
                            res_company = self.env['res.company'].sudo()
                            res_users = self.env['res.users'].sudo()
                            crm_team = self.env['crm.team'].sudo()

                            partner_id = False
                            if res['partner_name']:
                                if res['x_cust_code']:
                                    obj_search_partner_code = res_partner.search([('x_cust_code', '=ilike', res['x_cust_code'])], limit=1)
                                    if obj_search_partner_code:
                                        partner_id = obj_search_partner_code.id
                                else:
                                    obj_search_partner_name = res_partner.search([('name', '=ilike', res['partner_name'])], limit=1)
                                    if obj_search_partner_name:
                                        partner_id = obj_search_partner_name.write({'x_cust_code': res['x_cust_code']}).id
                                    else:
                                        partner_id = res_partner.create({'name': res['partner_name'], 'x_cust_code': res['x_cust_code']}).id
                            else:
                                partner_id = False
                                    
                            partner_invoice_id = False
                            if res['partner_invoice_id_name']:
                                if res['partner_invoice_id_code']:
                                    obj_search_partner_invoice_code = res_partner.search([('x_cust_code', '=ilike', res['partner_invoice_id_code'])], limit=1)
                                    if obj_search_partner_invoice_code:
                                        partner_invoice_id = obj_search_partner_invoice_code.id
                                else:
                                    obj_search_partner_invoice_name = res_partner.search([('name', '=ilike', res['partner_invoice_id_name'])], limit=1)
                                    if obj_search_partner_invoice_name:
                                        partner_invoice_id = obj_search_partner_invoice_name.write({'x_cust_code': res['partner_invoice_id_code']}).id
                                    else:
                                        partner_invoice_id = res_partner.create({'name': res['partner_invoice_id_name'], 'x_cust_code': res['partner_invoice_id_code']}).id
                            else:
                                partner_invoice_id = False
                                    

                            partner_shipping_id = False
                            if res['partner_shipping_id_name']:
                                if res['partner_shipping_id_code']:
                                    obj_search_partner_shipping_code = res_partner.search([('x_cust_code', '=ilike', res['partner_shipping_id_code'])], limit=1)
                                    if obj_search_partner_shipping_code:
                                        partner_shipping_id = obj_search_partner_shipping_code.id
                                else:
                                    obj_search_partner_shipping_name = res_partner.search([('name', '=ilike', res['partner_shipping_id_name'])], limit=1)
                                    if obj_search_partner_shipping_name:
                                        partner_shipping_id = obj_search_partner_shipping_name.write({'x_cust_code': res['partner_shipping_id_code']}).id
                                    else:
                                        partner_shipping_id = res_partner.create({'name': res['partner_shipping_id_name'], 'x_cust_code': res['partner_shipping_id_code']}).id
                            else:
                                partner_shipping_id = False

                            pricelist_id = False
                            if res['pricelist_name']:
                                obj_search_pricelist = pricelist.search([('name', '=', res['pricelist_name'])], limit=1)
                                if obj_search_pricelist:
                                    pricelist_id = obj_search_pricelist.id
                                else:
                                    pricelist_id = pricelist.create({'name': res['pricelist_name']}).id
                            else:
                                pricelist_id = False

                            warehouse_id = False
                            if res['warehouse_name']:
                                obj_search_warehouse = stock_warehouse.search([('name', '=', res['warehouse_name'])], limit=1)
                                if obj_search_warehouse:
                                    warehouse_id = obj_search_warehouse.id
                                else:
                                    warehouse_id = False
                            else:
                                warehouse_id = False

                            payment_term_id = False
                            if res['payment_term_name']:
                                obj_search_payment_term = payment_term.search([('name', '=', res['payment_term_name'])], limit=1)
                                if obj_search_payment_term:
                                    payment_term_id = obj_search_payment_term.id
                                else:
                                    payment_term_id = payment_term.create({'name': res['payment_term_name']}).id
                            else:
                                payment_term_id = False

                            currency_id = False
                            obj_search_currency = res_currency.search([('name', '=', res['currency_name'])], limit=1)
                            if obj_search_currency:
                                currency_id = obj_search_currency.id
                            else:
                                currency_id = False

                            company_id = False
                            obj_search_company = res_company.search([('name', '=', res['company_name'])], limit=1)
                            if obj_search_company:
                                company_id = obj_search_company.id
                            else:
                                company_id = False

                            user_id = False
                            obj_search_users = res_users.search([('name', '=', res['user_name'])], limit=1)
                            if obj_search_users:
                                user_id = obj_search_users.id
                            else:
                                user_id = False

                            team_id = False
                            if res['team_name']:
                                obj_search_team = crm_team.search([('name', '=', res['team_name'])], limit=1)
                                if obj_search_team:
                                    team_id = obj_search_team.id
                                else:
                                    team_id = crm_team.create({'name': res['team_name']}).id
                            else:
                                team_id = False

                            search_sale_order = sale_order.search([('name', '=', res['name'])])
                            so_vals = {'name': res['name'],
                                    'partner_id': partner_id,
                                    'partner_invoice_id': partner_invoice_id,
                                    'partner_shipping_id': partner_shipping_id,
                                    'validity_date': res['validity_date'],
                                    'date_order': res['date_order'],
                                    'picking_policy': res['picking_policy'],
                                    'pricelist_id': pricelist_id,
                                    'warehouse_id': warehouse_id,
                                    'payment_term_id': payment_term_id,
                                    'currency_id': currency_id,
                                    'company_id': company_id,
                                    'cust_po_ref': res['cust_po_ref'],
                                    'x_attention': res['x_attention'],
                                    'user_id': user_id,
                                    'team_id': team_id,
                                    'note': res['note'],
                                    'order_line': lines
                                    }
                            
                            if search_sale_order:
                                update = search_sale_order.sudo().write(so_vals)
                                print("Update Sukses")
                            else:
                                create = sale_order.sudo().create(so_vals)
                                print("Create Sukses")
                    if get_sale_order.json().get('error'):
                        self.integration_log(str(res['name']), 404, "sale.order", "get_sale_order", "/get_sale_orders/v1-api-ent", str(res), get_sale_order.json().get('error'), False, "Failed Sync")
                    elif get_sale_order.json().get("result") or get_sale_order.json().get("result").get('status') == 400:
                        self.integration_log(str(res['name']), 400, "sale.order", "get_sale_order", "/get_sale_orders/v1-api-ent", str(res), get_sale_order.json().get("result").get('message'), False, "Failed Sync")
                except Exception as exc:
                    self.integration_log(str(res['name']), 500, "sale.order", "get_sale_order", "/get_sale_orders/v1-api-ent", str(res), exc, False, "Failed Sync")
    

    def get_purchase_order(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_purchase_orders/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                try:
                    get_purchase_order = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                    data = get_purchase_order.json()
                    print("Data=====", data)
                    response = data['result']['response']
                    result_data = []
                    for res in response:
                        lines = [(5, 0, 0)]
                        order_line = res['order_line']
                        for po_line in order_line:
                            products = po_line['products']
                            rec_product = self.env['product.product'].sudo()
                            rec_uom_uom = self.env['uom.uom'].sudo()
                            
                            product_id = False
                            obj_search_product = rec_product.search([('name', '=ilike', po_line['product_name'])], limit=1)
                            # obj_search_product = rec_product.search([('name', '=ilike', po_line['product_name']), ('categ_id.name', '=ilike', po_line['product_categ_name'])], limit=1)
                            if obj_search_product:
                                product_id = obj_search_product.id
                            else:
                                created_product = self.create_product(products)
                                print("created_product=====", created_product)
                                product_id = created_product


                            product_uom_id = False
                            obj_search_uom = rec_uom_uom.search([('name', '=', po_line['product_uom_name'])], limit=1)
                            if obj_search_uom:
                                product_uom_id = obj_search_uom.id
                            else:
                                product_uom_id = False

                            tax_ids = []
                            for tax_id in po_line['taxes_name']:
                                account_tax_obj = self.env['account.tax'].sudo().search([
                                    ('name', '=', tax_id)
                                ], limit=1)
                                if account_tax_obj:
                                    tax_ids.append(account_tax_obj.id)


                            vals_line = {'product_id': product_id,
                                        'sequence': po_line['sequence'],
                                        'display_type': po_line['display_type'],
                                        'name': po_line['name'],
                                        'date_planned': po_line['date_planned'],
                                        'product_qty': po_line['product_qty'],
                                        'product_uom': product_uom_id,
                                        'price_unit': po_line['price_unit'],
                                        'taxes_id': tax_ids,
                                        'price_subtotal': po_line['price_subtotal']}
                            lines.append((0, 0, vals_line))

                        purchase_order = self.env['purchase.order'].sudo()
                        rec_project = self.env['project.project'].sudo()
                        res_partner = self.env['res.partner'].sudo()
                        sale_order = self.env['sale.order'].sudo()
                        picking_type = self.env['stock.picking.type'].sudo()
                        payment_term = self.env['account.payment.term'].sudo()
                        hr_employee = self.env['hr.employee'].sudo()
                        res_currency = self.env['res.currency'].sudo()
                        res_company = self.env['res.company'].sudo()
                        res_users = self.env['res.users'].sudo()

                        project_id = False
                        if res['project_name']:
                            obj_search_project = rec_project.search([('name', '=ilike', res['project_name'])], limit=1)
                            if obj_search_project:
                                project_id = obj_search_project.id
                            else:
                                project_id = rec_project.sudo().create({'name': res['project_name']}).id
                        else:
                            project_id = False

                        partner_id = False
                        if res['partner_name']:
                            obj_search_partner_code = res_partner.search([('x_cust_code', '=ilike', res['x_cust_code'])], limit=1)
                            if obj_search_partner_code:
                                partner_id = obj_search_partner_code.id
                            else:
                                obj_search_partner_name = res_partner.search([('name', '=ilike', res['partner_name'])], limit=1)
                                if obj_search_partner_name:
                                    partner_id = obj_search_partner_name.write({'x_cust_code': res['x_cust_code']}).id
                                else:
                                    partner_id = res_partner.create({'name': res['partner_name'], 'x_cust_code': res['x_cust_code']}).id
                        else:
                            partner_id = False

                        sale_order_id = False
                        obj_search_sale_order = sale_order.search([('name', '=ilike', res['sale_order_name'])], limit=1)
                        if obj_search_sale_order:
                            sale_order_id = obj_search_sale_order.id
                        else:
                            sale_order_id = False

                        currency_id = False
                        obj_search_currency = res_currency.search([('name', '=ilike', res['currency_name'])], limit=1)
                        if obj_search_currency:
                            currency_id = obj_search_currency.id
                        else:
                            currency_id = False

                        company_id = False
                        obj_search_company = res_company.search([('name', '=ilike', res['company_name'])], limit=1)
                        if obj_search_company:
                            company_id = obj_search_company.id
                        else:
                            company_id = False

                        picking_type_id = False
                        obj_search_picking_type = picking_type.search([('name', '=ilike', res['picking_type_name'])], limit=1)
                        if obj_search_picking_type:
                            picking_type_id = obj_search_picking_type.id
                        else:
                            picking_type_id = False

                        user_id = False
                        obj_search_users = res_users.search([('name', '=ilike', res['user_name'])], limit=1)
                        if obj_search_users:
                            user_id = obj_search_users.id
                        else:
                            user_id = False
                        
                        finance_approval_id = False
                        obj_search_users = res_users.search([('name', '=ilike', res['finance_approval_name'])], limit=1)
                        if obj_search_users:
                            finance_approval_id = obj_search_users.id
                        else:
                            finance_approval_id = False

                        director_approval_id = False
                        obj_search_users = res_users.search([('name', '=ilike', res['director_approval_name'])], limit=1)
                        if obj_search_users:
                            director_approval_id = obj_search_users.id
                        else:
                            director_approval_id = False

                        payment_term_id = False
                        if res['payment_term_name']:
                            obj_search_payment_term = payment_term.search([('name', '=ilike', res['payment_term_name'])], limit=1)
                            if obj_search_payment_term:
                                payment_term_id = obj_search_payment_term.id
                            else:
                                payment_term_id = payment_term.create({'name': res['payment_term_name']}).id
                        else:
                            payment_term_id = False

                        employee_id = False
                        obj_search_employee = hr_employee.search([('name', '=ilike', res['employee_name'])], limit=1)
                        if obj_search_employee:
                            employee_id = obj_search_employee.id
                        else:
                            employee_id = False

                        search_purchase_order = purchase_order.search([('name', '=', res['name'])])
                        po_vals = {'name': res['name'],
                                   'project_id': project_id,
                                   'partner_id': partner_id,
                                   'x_attn': res['x_attn'],
                                   'partner_ref': res['partner_ref'],
                                   'currency_id': currency_id,
                                   'date_order': res['date_order'],
                                   'date_approve': res['date_approve'],
                                   'sale_order_id': sale_order_id,
                                   'company_id': company_id,
                                   'picking_type_id': picking_type_id,
                                   'date_planned': res['date_planned'],
                                   'user_id': user_id,
                                   'payment_term_id': payment_term_id,
                                   'employee_id': employee_id,
                                   'finance_approval_id': finance_approval_id,
                                   'finance_manager_approve_date': res['finance_manager_approve_date'],
                                   'director_approval_id': director_approval_id,
                                   'director_approve_date': res['director_approve_date'],
                                   'notes': res['notes'],
                                   'order_line': lines
                                }
                        
                        if search_purchase_order:
                            update = search_purchase_order.sudo().write(po_vals)
                        else:
                            create = purchase_order.sudo().create(po_vals)
                except Exception as exc:
                    self.integration_log("/get_purchase_orders/v1-api-ent", 400, "purchase.order", "get_purchase_order", today, "", exc)
    

    def get_journal_entries(self,interval=2):
        get_end_point = self._get_end_point(end_point='/get_journal_entries/v1-api-ent')
        data = []
        if get_end_point:
            if len(get_end_point) > 1:
                raise UserError(_('Warning, the same key: %s is not allowed.' % (','.join(get_end_point.mapped('end_point')))))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.username:
                raise UserError(_('USERNAME Empty!!!'))
            
            if not get_end_point.integration_id and not get_end_point.integration_id.password:
                raise UserError(_('PASSWORD Empty!!!'))
            
            if get_end_point.integration_id and get_end_point.integration_id.username and get_end_point.integration_id.password:
                today = fields.Datetime.now()
                server_url = get_end_point.integration_id.url_data
                url = str(get_end_point.integration_id.url_data) + str(get_end_point.end_point)
                db = get_end_point.integration_id.database
                username = get_end_point.integration_id.username
                password = get_end_point.integration_id.password

                headers = {'Content-type': 'application/json'}
                auth = {
                    'params': {
                        'login': username,
                        'password': password,
                        'db': db
                    }
                }
                res_auth = requests.post(server_url+'/web/session/authenticate', data=json.dumps(auth), headers=headers)
                print("AUTH====", res_auth)
                cookies = res_auth.cookies
                print("Cookies====", cookies)
                start_date, end_date = self._set_timezone(date=today, interval=interval)
                sync_data = {
                    "params": {"start_date": start_date,"end_date": end_date}
                }
                print("Start Date====", start_date)
                print("End Date====", end_date)
                get_journal_entries = requests.get(url, data=json.dumps(sync_data), headers=headers, cookies=cookies)
                data = get_journal_entries.json()
                response = data['result']['response']
                result_data = []
                for res in response:
                    inv_lines = [(5, 0, 0)]
                    invoice_line_ids = res['invoice_line_ids']
                    for inv_line in invoice_line_ids:
                        rec_product = self.env['product.product'].sudo()
                        rec_account_account = self.env['account.account'].sudo()
                        rec_project = self.env['project.project'].sudo()
                        rec_analytic_account = self.env['account.analytic.account'].sudo()
                        rec_uom_uom = self.env['uom.uom'].sudo()
                        res_company = self.env['res.company'].sudo()
                        
                        product_id = False
                        obj_search_product = rec_product.search([('name', '=ilike', inv_line['product_name']), ('categ_id.name', '=ilike', inv_line['product_categ_name'])], limit=1)
                        if obj_search_product:
                            product_id = obj_search_product.id
                        else:
                            product_id = False

                        account_id = False
                        obj_search_account_account = rec_account_account.search([('code', '=', inv_line['account_code'])], limit=1)
                        if obj_search_account_account:
                            account_id = obj_search_account_account.id
                        else:
                            account_id = False

                        project_id = False
                        if inv_line['xproject_name']:
                            obj_search_project = rec_project.search([('name', '=ilike', inv_line['xproject_name'])], limit=1)
                            if obj_search_project:
                                project_id = obj_search_project.id
                            else:
                                project_id = False
                        else:
                            project_id = False

                        analytic_account_id = False
                        obj_search_analytic_account = rec_analytic_account.search([('name', '=ilike', inv_line['analytic_account_name'])], limit=1)
                        if obj_search_analytic_account:
                            analytic_account_id = obj_search_analytic_account.id
                        else:
                            analytic_account_id = False

                        product_uom_id = False
                        obj_search_uom = rec_uom_uom.search([('name', '=ilike', inv_line['product_uom_name'])], limit=1)
                        if obj_search_uom:
                            product_uom_id = obj_search_uom.id
                        else:
                            product_uom_id = False

                        tax_ids = []
                        for tax_id in inv_line['taxes_name']:
                            account_tax_obj = self.env['account.tax'].sudo().search([
                                ('name', '=ilike', tax_id)
                            ], limit=1)
                            if account_tax_obj:
                                tax_ids.append(account_tax_obj.id)
                        
                        tag_ids = []
                        for tag_id in inv_line['analytic_tag_name']:
                            analytic_tag_obj = self.env['account.tax'].sudo().search([
                                ('name', '=ilike', tag_id)
                            ], limit=1)
                            if analytic_tag_obj:
                                tag_ids.append(analytic_tag_obj.id)


                        vals_line = {'product_id': product_id,
                                     'name': inv_line['name'],
                                     'account_id': account_id,
                                     'xproject_id': project_id,
                                     'analytic_account_id': analytic_account_id,
                                     'analytic_tag_ids': tag_ids,
                                     'quantity': inv_line['quantity'],
                                     'product_uom_id': product_uom_id,
                                     'price_unit': inv_line['price_unit'],
                                     'discount': inv_line['discount'],
                                     'tax_ids': tax_ids,
                                     'price_subtotal': inv_line['price_subtotal']
                                }
                        inv_lines.append((0, 0, vals_line))

                    journal_item = [(5, 0, 0)]
                    journal_item_ids = res['line_ids']
                    n = 0
                    for line_id in journal_item_ids:
                        rec_res_partner = self.env['res.partner'].sudo()
                        rec_analytic_account = self.env['account.analytic.account'].sudo()
                        rec_currency = self.env['res.currency'].sudo()
                        rec_account_account = self.env['account.account'].sudo()
                        try:
                            obj_search_account_account = rec_account_account.search([('code', '=', line_id['account_code'])], limit=1)
                            if obj_search_account_account:
                                journal_account_id = obj_search_account_account.id
                            else:
                                raise UserError(_("Code Account '%s %s' Not Registered") % (line_id['account_code'], line_id['account_name']))

                            obj_currency = rec_currency.search([('name', '=', res['currency_name'])], limit=1)
                            if obj_currency:
                                currency_id = obj_currency.id
                            else:
                                raise UserError(_("Currency IDR Not Registered"))

                            obj_search_analytic_account = rec_analytic_account.search([('name', '=ilike', line_id['analytic_account_name'])], limit=1)
                            if line_id['analytic_account_name'] and not obj_search_analytic_account:
                                raise UserError(_("Analytic Account '%s' Not Registered")%(line_id['analytic_account_name']))
                            elif obj_search_analytic_account:
                                journal_analytic_account_id = {str(obj_search_analytic_account.id) : 100}
                            else:
                                journal_analytic_account_id = False
                            obj_search_res_partner = rec_res_partner.search([('name', '=', line_id['partner_name'])], limit=1)
                            if line_id['partner_name'] and not obj_search_res_partner:
                                raise UserError(_("Partner Name '%s' Not Registered")%(line_id['partner_name']))
                            elif obj_search_res_partner:
                                journal_partner_id = obj_search_res_partner.id
                            else:
                                journal_partner_id = ' '
                        except Exception as e:
                            # Handle more specific exception types if possible
                            raise UserError(_("An error occurred while searching for the data: %s") % str(e))

                        

                        journal_tax_ids = []
                        for journal_tax_id in line_id['tax_name']:
                            journal_account_tax_obj = self.env['account.tax'].sudo().search([
                                ('name', '=ilike', journal_tax_id)
                            ], limit=1)
                            if journal_account_tax_obj:
                                journal_tax_ids.append(journal_account_tax_obj.id)

                        journal_tax_tag_ids = []
                        for journal_tax_tag_id in line_id['tag_name']:
                            journal_account_tax_tag_obj = self.env['account.tax'].sudo().search([
                                ('name', '=ilike', journal_tax_tag_id)
                            ], limit=1)
                            if journal_account_tax_tag_obj:
                                journal_tax_tag_ids.append(journal_account_tax_tag_obj.id)
                        if line_id['amount_currency'] != 0:
                            amount_currency = line_id['amount_currency']
                        elif abs(line_id['debit']) > 0:
                            amount_currency = line_id['debit']
                        else:
                            amount_currency = -line_id['credit']
                        journal_vals_line = {
                                'account_id': journal_account_id,
                                'partner_id': journal_partner_id or ' ',
                                'analytic_distribution': journal_analytic_account_id,
                                'name': line_id['name'],
                                'tax_ids': journal_tax_ids,
                                'debit': abs(line_id['debit']),
                                'credit': abs(line_id['credit']),  # Pastikan nilai positif untuk kredit
                                'tax_tag_ids': journal_tax_tag_ids,
                                'currency_id': currency_id,
                                'amount_currency': amount_currency,
                                'date_maturity': res['date']
                            }
                        journal_item.append((0, 0, journal_vals_line))
                    print(journal_item,'journal_item')
                    rec_account_move = self.env['account.move'].sudo()
                    rec_am_res_partner = self.env['res.partner'].sudo()
                    rec_am_payment_term = self.env['account.payment.term'].sudo()
                    rec_am_account_journal = self.env['account.journal'].sudo()
                    rec_am_res_currency = self.env['res.currency'].sudo()
                    rec_am_res_users = self.env['res.users'].sudo()
                    rec_am_crm_team = self.env['crm.team'].sudo()
                    rec_am_hr_employee = self.env['hr.employee'].sudo()
                    
                    am_partner_id = False
                    try:
                        obj_search_am_partner_id = rec_am_res_partner.search([('x_cust_code', '=ilike', res['x_cust_code'])], limit=1)
                        am_partner_id = obj_search_am_partner_id.id
                    except:
                        am_partner_id = False

                    am_partner_shipping_id = False
                    obj_search_am_shipping_id = rec_am_res_partner.search([('name', '=ilike', res['partner_shipping_name'])], limit=1)
                    if obj_search_am_shipping_id:
                        am_partner_shipping_id = obj_search_am_shipping_id.id
                    else:
                        am_partner_shipping_id = False

                    am_payment_term_id = False
                    obj_search_am_payment_term_id = rec_am_payment_term.search([('name', '=ilike', res['invoice_payment_term_name'])], limit=1)
                    if obj_search_am_payment_term_id:
                        am_payment_term_id = obj_search_am_payment_term_id.id
                    else:
                        am_payment_term_id = False

                    am_account_journal_id = False
                    obj_search_am_account_journal_id = rec_am_account_journal.search([('name', '=ilike', res['journal_name'])], limit=1)
                    if res['journal_name'] and not obj_search_am_account_journal_id:
                        raise UserError(_("Journal Name '%s' Not Registered")%(line_id['journal_name']))
                    elif obj_search_am_account_journal_id:
                        am_account_journal_id = obj_search_am_account_journal_id.id
                    else:
                        am_account_journal_id = False

                    am_currency_id = False
                    obj_search_am_currency_id = rec_am_res_currency.search([('name', '=ilike', res['currency_name'])], limit=1)
                    if obj_search_am_currency_id:
                        am_currency_id = obj_search_am_currency_id.id
                    else:
                        am_currency_id = False

                    am_invoice_user_id = False
                    obj_search_am_invoice_user_id = rec_am_res_users.search([('name', '=ilike', res['invoice_user_name'])], limit=1)
                    if obj_search_am_invoice_user_id:
                        am_invoice_user_id = obj_search_am_invoice_user_id.id
                    else:
                        am_invoice_user_id = False

                    am_team_id = False
                    obj_search_am_crm_team_id = rec_am_crm_team.search([('name', '=ilike', res['team_name'])], limit=1)
                    if obj_search_am_crm_team_id:
                        am_team_id = obj_search_am_crm_team_id.id
                    else:
                        am_team_id = False

                    am_pic_fo_id = False
                    obj_search_am_pic_fo_id = rec_am_hr_employee.search([('name', '=ilike', res['pic_fo_name'])], limit=1)
                    if obj_search_am_pic_fo_id:
                        am_pic_fo_id = obj_search_am_pic_fo_id.id
                    else:
                        am_pic_fo_id = False

                    am_pic_fm_id = False
                    obj_search_am_pic_fm_id = rec_am_hr_employee.search([('name', '=ilike', res['pic_fm_name'])], limit=1)
                    if obj_search_am_pic_fm_id:
                        am_pic_fm_id = obj_search_am_pic_fm_id.id
                    else:
                        am_pic_fm_id = False

                    am_pic_fa_id = False
                    obj_search_am_pic_fa_id = rec_am_hr_employee.search([('name', '=ilike', res['pic_fa_name'])], limit=1)
                    if obj_search_am_pic_fa_id:
                        am_pic_fa_id = obj_search_am_pic_fa_id.id
                    else:
                        am_pic_fa_id = False
                    search_journal_entries = rec_account_move.search([('name', '=', res['name'])])

                    journal_vals = {'name': res['name'],
                                    'partner_id': am_partner_id,
                                    'partner_shipping_id': am_partner_shipping_id,
                                    'ref': res['ref'],
                                    'x_refno': res['x_refno'],
                                    'date': res['date'],
                                    'invoice_date': res['invoice_date'],
                                    'invoice_payment_term_id': am_payment_term_id,
                                    'journal_id': am_account_journal_id,
                                    'currency_id': am_currency_id,
                                    'client_attn': res['client_attn'],
                                    'invoice_user_id': am_invoice_user_id,
                                    'team_id': am_team_id,
                                    'invoice_origin': res['invoice_origin'],
                                    # 'invoice_partner_bank_id': res['invoice_partner_bank_id'],
                                    'pic_fo': am_pic_fo_id,
                                    'pic_fm': am_pic_fm_id,
                                    'pic_fa': am_pic_fa_id,
                                    'state': res['state'],
                                    'move_type': res['type'],
                                    # 'invoice_line_ids': inv_lines,
                                    'line_ids': journal_item
                               }
                    print(journal_vals,'journal_vals')
                    if search_journal_entries:
                        update = search_journal_entries.sudo().write(journal_vals)
                    elif res['type'] == 'entry':
                        create = rec_account_move.sudo().create(journal_vals)
