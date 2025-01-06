# -*- coding: utf-8 -*-
import json
import logging
import requests
import datetime

from odoo import api, fields, models
from odoo import http, _, exceptions
from odoo.tests import Form
from odoo.http import request
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
import logging
import werkzeug.wrappers

logging.warning("waring")

_logger = logging.getLogger(__name__)

class XTestConnection(http.Controller):
    @http.route('/test_connection', type='json', auth='user', method=['POST'])
    def test_connection(self, **value):
        if value['id']:
            data = {'status': 200, 'response': 'Sukses', 'message': 'Conncetion Success'}
        return data