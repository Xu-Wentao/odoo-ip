# -*- coding: utf-8 -*-

from odoo import api, http, SUPERUSER_ID, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_compare
from odoo.modules.registry import RegistryManager
import werkzeug
import base64
import time
import json
import hashlib
import hmac
import datetime
from odoo.http import request

# 加密秘钥
SECRET = 'MTUxNTA1MDk0Mi4wMSxhZDNiMmZiZDRhOGU3ZDUzN2QyZDE1OTcwNWFmYWIyNTIzMTI3ZTg1LFNjcmVhdGl2ZTEwM'
NOTUID = 'you are unauthenticated'
EXPIRED = 'token has expired'
UNVALIDATE = 'token is unvalidated'
DBERROR = 'wrong database'
SYNTAXE = 'syntax error'
EXPIRE = 3600

def no_token(message):
    rp = {'result': '','success': False,'message':message}
    return json_response(rp)

def json_response(rp):
    """
    操作结果统一json格式返回
    :param rp:
    :return:
    """
    headers = {"Access-Control-Allow-Origin": "*"}
    return werkzeug.wrappers.Response(json.dumps(rp,ensure_ascii=False), mimetype='application/json',headers=headers) 

def authenticate(token):
    try:
        # 补齐位数
        token += '==' if 4 - len(token) % 4 == 2 else '='
        token_str  = base64.urlsafe_b64decode(str(token))

        ts,b64_ts,db,uid = token_str.split(',')

        #有效时间验证
        if float(ts) < time.time():
            return EXPIRED

        # 摘要对比
        validate_ts = hmac.new(SECRET, ts, hashlib.sha1).hexdigest()
        if b64_ts != validate_ts:
            return UNVALIDATE

        registry = RegistryManager.get(db)
        cr = registry.cursor()
        env = api.Environment(cr, int(uid), {})
    except Exception,e:
        return UNVALIDATE
    return env

def get_latest_stock(env,product,online_location):
    """
    查询最新库存
    """
    domain = []
    domain.append(('product_id','=',product.id))
    domain.append(('location_id','=',online_location.id))
    res = [item['qty'] if item['qty'] else 0  for item in env['stock.quant'].read_group(domain,['product_id','qty'],['product_id'])]
    res = res[0] if res else 0

    res_domain = [('state', 'not in', ('done', 'cancel', 'draft'))]
    res_domain.append(('product_id','=',product.id))
    res_domain.append(('location_id','=',online_location.id))
    out_res = [item['product_qty'] if item['product_qty'] else 0 for item in env['stock.move'].read_group(res_domain,['product_id','product_qty'],['product_id'])]
    out_res = out_res[0] if out_res else 0
    return res - out_res

def get_online_stock(env,product):
    """
    线上库存查询
    """
    online_location = env['stock.location'].search([('online_sale','=',True),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)
    offline_location = env['stock.location'].search([('online_sale','=',False),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)

    domain = []
    domain.append(('product_id','=',product.id))
    domain.append(('location_id','=',online_location.id))
    res = [item['qty'] if item['qty'] else 0  for item in env['stock.quant'].read_group(domain,['product_id','qty'],['product_id'])]
    res = res[0] if res else 0
    return online_location,offline_location,res

def get_offline_stock(env,product):
    """
    线下库存查询
    """
    online_location = env['stock.location'].search([('online_sale','=',True),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)
    offline_location = env['stock.location'].search([('online_sale','=',False),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)

    domain = []
    domain.append(('product_id','=',product.id))
    domain.append(('location_id','=',offline_location.id))
    res = [item['qty'] if item['qty'] else 0  for item in env['stock.quant'].read_group(domain,['product_id','qty'],['product_id'])]
    print domain
    print res
    res = res[0] if res else 0
    return online_location,offline_location,res

class RestfulAPI(http.Controller):

    @http.route([ '/api/get_token',], type='http', auth="none", methods=['GET'])
    def get_token(self,d='',u='a', p='a',**kw):
        """
        通过GET请求，获取TOKEN
        :param d: 账套名称
        :param u: 用户名
        :param p: 密码
        :param kw:
        :return:
        """
        try:
            uid = http.request.session.authenticate(d, u, p)
        except Exception,e:
            rp = {'token': '','success':False,'message':DBERROR}
            return json_response(rp)

        if not uid:
            rp = {'token': '','success':False,'message':NOTUID}
            return json_response(rp)

        ts = str(time.time() + EXPIRE)
        b64_ts = hmac.new(SECRET, ts, hashlib.sha1).hexdigest()
        token =','.join([ts,b64_ts,d,str(uid)])
        b64_token = base64.urlsafe_b64encode(token)
        rp = {'token': b64_token.replace('=',''),'success':True,'message':'you are authenticated'}
        return json_response(rp)

    @http.route([ '/api/stock.query',], csrf=False,auth='none', type='http', methods=['POST'])
    def stock_query(self,**kw):
        """
        库存查询
        :param kw:
        :return:
        """
        try:
            rp = {"success":True,"message":' ','lastest_stock':[]}
            kw = eval(request.httprequest.data)
            token = kw.pop('token','')

            # 验证token
            env = authenticate(token)
            if env in [NOTUID,EXPIRED,UNVALIDATE,SYNTAXE]:
                return no_token(env)

            products = kw.pop('products','')

            online_location = env['stock.location'].search([('online_sale','=',True),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)

            for item in products:
                product = env['product.product'].search([('xbrand','=',item[0]),('xmodel','=',item[1]),('company_id','=',env.user.company_id.id)],limit=1)

                if not product:
                    rp['lastest_stock'].append([[item[0],item[1]],'N%'])
                else:
                    qty = get_latest_stock(env,product,online_location)
                    rp['lastest_stock'].append([product.name,qty])


        except Exception,e:
            error = ''
            if "invalid syntax" in str(e):
                error = SYNTAXE
            else:
                error = str(e) + '参数有误，或者没指定，请检查'
            rp['success'] = False
            rp['message'] = error

        return json_response(rp)

    @http.route([ '/api/sale.order',], csrf=False,auth='none', type='http', methods=['POST'])
    def sale_order(self, **kw):
        """
        http必须设置headers : {Content-Type:text/plain}
        :param kw:
        :return:
        """
        def _create_order(env,value):
            """
            创建订单主体,根据业务需要传递订单相关信息参数进行订单创建
            本实例，仅使用联系人信息进行创建
            :param env:
            :param value:
            :return:
            """
            params = value.pop('partner_id')
            # 根据需要调整联系人唯一性查询
            partner = env['res.partner'].search([('name','=',params['name']),('mobile','=',params['mobile'])],limit=1)
            if not partner:
                country_id = env['res.country'].search([('name','=',params['country_name'])],limit=1)
                state_id = env['res.country.state'].search([('name','=',params['state_name'])],limit=1)

                vals = {
                    'name':params['name'],
                    'mobile':params['mobile'],
                    'country_id': country_id.id if country_id else None,
                    'state_id':state_id.id if state_id else None,
                    'city':params['city'],
                    'street':params['street']
                }
                partner = env['res.partner'].create(vals)

            return env['sale.order'].create({
                'warehouse_id':env['stock.warehouse'].search([('company_id', '=', env.user.company_id.id),('online_sale','=',True)], limit=1).id,
                'partner_id':partner.id,
                'date_order':datetime.datetime.now()
            })

        def _product_check_availability(env,product,product_uom,product_uom_qty,online_location,rp):
            """
            检查产品库存
            """

            qty_available = get_latest_stock(env,product,online_location)

            precision = env['decimal.precision'].precision_get('Product Unit of Measure')
            product_qty = product_uom._compute_quantity(product_uom_qty, product.uom_id)
            if float_compare(qty_available, product_qty, precision_digits=precision) == -1:
                rp["success"] = False
                rp["message"] += "%s upsell !!! ;" % (product.name)
            return rp

        def _tell_stock_update(env,order_line,online_location,rp):
            """
            无论是否超卖，告诉电商平台最新可用库存信息
            """
            for line in order_line:
                product = env['product.product'].search([('xbrand','=',line['product_id']['xbrand']),('xmodel','=',line['product_id']['xmodel']),('company_id','=',env.user.company_id.id)],limit=1)

                if not product:
                    rp['lastest_stock'].append(["Product %s not exist !!! ;" % (line['product_id']['xbrand']+line['product_id']['xmodel']),0])
                else:
                    qty = get_latest_stock(env,product,online_location)
                    rp['lastest_stock'].append([product.name,qty])
            return rp

        def _create_order_line(env,order_id,order_line,online_location,rp):
            """
            创建订单明细
            """

            for line in order_line:
                # 自行调整产品查询参数
                product = env['product.product'].search([('xbrand','=',line['product_id']['xbrand']),('xmodel','=',line['product_id']['xmodel']),('company_id','=',env.user.company_id.id)],limit=1)

                if not product:
                    rp["message"] += "Product %s not exist !!! ;" % (line['product_id']['xbrand']+line['product_id']['xmodel'])
                    continue


                rp = _product_check_availability(env,product,product.product_tmpl_id.uom_id,line['product_uom_qty'],online_location,rp)
                if rp["success"]:
                    vals = {
                        'order_id':order_id,
                        'name':product.name,
                        'product_id':product.id,
                        'price_unit':line['price_unit'],
                        'product_uom':product.product_tmpl_id.uom_id.id,
                        'product_uom_qty':line['product_uom_qty'],
                    }
                    env['sale.order.line'].create(vals)

            return rp

        try :

            rp = {"success":True,"message":' ','lastest_stock':[]}
            kw = eval(request.httprequest.data)
            token = kw.pop('token','')

            # 验证token
            env = authenticate(token)
            if env in [NOTUID,EXPIRED,UNVALIDATE,SYNTAXE]:
                return no_token(env)

            online_location = env['stock.location'].search([('online_sale','=',True),('usage','=','internal'),('company_id','=',env.user.company_id.id)],limit=1)

            # 创建订单主体
            order = _create_order(env,kw)
            # 创建订单明细
            rp = _create_order_line(env,order.id,kw['order_line'],online_location,rp)

            if rp["success"]:
                # 确认销售
                order.sudo().action_confirm()
                # 锁定库存
                order.mapped('picking_ids').sudo().action_assign()
                env.cr.commit()
            # 告诉电商平台更新库存
            rp = _tell_stock_update(env,kw['order_line'],online_location,rp)

        except Exception,e:
            error = ''
            if "invalid syntax" in str(e):
                error = SYNTAXE
            else:
                error = str(e) + '参数有误，或者没指定，请检查'
            rp['success'] = False
            rp['message'] = error

        return json_response(rp)

    @http.route([ '/api/online.action',], csrf=False,auth='none', type='http', methods=['GET'])
    def online_action(self,token='',xbrand='',xmodel='',num=1,**kw):
        try:
            rp = {"success":True,"message":'pull on shelves sccessfully  '}
            env = authenticate(token)
            if env in [NOTUID,EXPIRED,UNVALIDATE,SYNTAXE]:
                return no_token(env)

            product = env['product.product'].search([('xbrand','=',xbrand),('xmodel','=',xmodel),('company_id','=',env.user.company_id.id)],limit=1)

            if product:
                online_location,offline_location,res = get_offline_stock(env,product)

                if res >= float(num) :
                    move = env['stock.move'].create({
                        'product_id':product.id,
                        'product_uom_qty':num,
                        'product_uom':product.uom_id.id,
                        'name':'上架调拨',
                        'location_id':offline_location.id,
                        'location_dest_id':online_location.id
                    })
                    move.action_confirm()
                    move.action_done()
                    product.write({'ec_state':'online'})
                    env.cr.commit()
                else:
                    rp = {"success":False,"message":'not enough qty put on shelves,only %s'%str(res)}
            else:
                rp = {"success": False, "message": 'product[%s,%s] not exist' % (xbrand, xmodel)}
        except Exception,e:
            rp = {"success":False,"message":str(e)}

        return json_response(rp)

    @http.route([ '/api/offline.action',], csrf=False,auth='none', type='http', methods=['GET'])
    def offline(self,token='',xbrand='',xmodel='',**kw):
        try:
            rp = {"success":True,"message":'pull off shelves sccessfully '}
            env = authenticate(token)
            if env in [NOTUID,EXPIRED,UNVALIDATE,SYNTAXE]:
                return no_token(env)

            product = env['product.product'].search([('xbrand','=',xbrand),('xmodel','=',xmodel),('company_id','=',env.user.company_id.id)],limit=1)

            if product:

                online_location,offline_location,res = get_online_stock(env,product)

                if res > 0 :
                    move = env['stock.move'].create({
                        'product_id':product.id,
                        'product_uom_qty':res,
                        'product_uom':product.uom_id.id,
                        'name':'下架调拨',
                        'location_id':online_location.id,
                        'location_dest_id':offline_location.id
                    })
                    move.action_confirm()
                    move.action_done()

                product.write({'ec_state':'offline'})
                env.cr.commit()

            else:
                rp = {"success": False, "message": 'product[%s,%s] not exist'%(xbrand,xmodel)}
        except Exception,e:
            rp = {"success":False,"message":str(e)}

        return json_response(rp)