# coding=utf-8
import tornado, sys, traceback, time, json, requests
import tornado.web
import tornado.httpclient
from tornado.options import define, options, parse_command_line

import config, utils, logging
from handlers import BaseHandler
from handlers.pvOrderHandler import PvOrderHandler
from models import SessionCustomer
from models.order import SinaWeiboBlogInfo, Authentication, SinaWeiboMonitorOrder
from datetime import datetime


headers = {
    "Content-Type": "application/json"
}


VERIFY = 'verify'
AUTH = 'auth'
MONITOR = 'monitor'

PROCESS_CODES=(0, 404, 302, 301)
ERROR_CODES = (404, 302, 301)


class MonitorOrderHandler(BaseHandler):

    session = SessionCustomer()
    

    async def post(self):
        try:
            body = self.request.body
            logging.info('receive {ip} report: {data}'.format(data=body, ip=self.reqsrcip))
            msg = None
            if len(body)> 10:
                self.processReport(json.loads(body))
                return
            order = self.getVerifyOrder()
            if order:
                self.send(order)
                return
            order = self.getAuthOrder()
            if order:
                self.send(order)
                return
            order = self.getMonitorOrders()
            if order:
                self.send(order)
                return
        except :
            msg = traceback.format_exc()
            logging.error(msg)
            self.send_error(status_code=500, reason=msg)


    def getMonitorOrders(self):
        keys = self.rediscli.zrangebyscore(config.REDIS_TODO_WEIBO_MONITOR_ZSET, 0, time.time())
        for key in keys:
            order = self.rediscli.hgetall(key)
            if order and int(order['status']) == 1:
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_MONITOR_ZSET, {key: (time.time()+30)})
                data={
                    'key': key,
                    'id': order['order_id'],
                    'target': order['target'],
                    'last_blog': order['last_blog'],
                    'type': 'home',
                    'model': MONITOR,
                }
                return data
            else:
                self.rediscli.zrem(config.REDIS_TODO_WEIBO_MONITOR_ZSET, key)
        return {}

    def getAuthOrder(self):
        keys = self.rediscli.zrangebyscore(config.REDIS_TODO_WEIBO_AUTH_ZSET, 0, time.time())
        for key in keys:
            order = self.rediscli.hgetall(key)
            if order and int(order['status']) == 5:
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_AUTH_ZSET, {key:time.time()+20})
                data={
                    'key': key,
                    'id': order['id'],
                    'target': order['target'],
                    'last_blog': '0',
                    'type': 'home',
                    'model': AUTH,
                }
                return data
            else:
                self.rediscli.zrem(config.REDIS_TODO_WEIBO_AUTH_ZSET, key)

        return {}

    def getVerifyOrder(self):
        keys = self.rediscli.zrange(config.REDIS_TODO_WEIBO_VERIFY_ZSET, 0, 5)
        for key in keys:
            order = self.rediscli.hgetall(key)
            if order and int(order['status']) == 2:
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_VERIFY_ZSET, {key:time.time()+20})
                data={
                    'key': key,
                    'id': order['id'],
                    'target': order['target'],
                    'type': 'art',
                    'model': VERIFY,
                }
                return data
            else:
                self.rediscli.zrem(config.REDIS_TODO_WEIBO_VERIFY_ZSET, key)

        return {}


            

    def processReport(self, data, key=None):
        try:
            if key is None:
                key = data['key']
            model = data['model']
            info = self.rediscli.hgetall(key)
            if not info:
                return
            self.rediscli.hset(key, 'update_at', str(datetime.now()))
            if model == AUTH:
                self.processAuth(data, info, key)
            elif model == VERIFY:
                self.processVerify(data, info, key)
            elif model == MONITOR:
                self.processMonitor(data, info, key)
        except:
            logging.error(traceback.format_exc())

    def processMonitor(self, data, order, key):
        code = data.get('code')
        if not code in PROCESS_CODES:
            return
        sorder = SinaWeiboMonitorOrder.query_order_by_id(self.session, data['id'])
        if code:
            # sorder.status = 4
            # self.session.commit()
            # self.rediscli.delete(key)
            return
        last_blog = data['last_blog']
        if int(last_blog) <= int(order['last_blog']):
            return
        self.rediscli.hset(key, 'last_blog', data['last_blog'])
        self.rediscli.zadd(config.REDIS_TODO_WEIBO_MONITOR_ZSET, {key: time.time()+120})
        self.rediscli.hset(key, 'update_at', int(time.time()))
        # sorder = SinaWeiboMonitorOrder(sorder)

        sorder.last_blog = last_blog
        sorder.update_at = datetime.now()
        sorder.blog_update_at = datetime.now()
        if not sorder.nick:
            sorder.nick = data['screen_name']
        self.session.commit()
        weibo_list = data.get('weibo_list')
        logging.info('{order} {list}'.format(order=order['order_id'], list=weibo_list))
        if weibo_list:
            screen_name = data['screen_name']
            avatar = data['avatar']
            account_id = order['target']
            order_id = order['order_id']
            url = order['report']
            repost_blog_info(url, order_id, weibo_list, account_id=account_id, account_name=screen_name, account_avatar=avatar)
        return

    def processVerify(self, data, info, key):
        code = data.get('code')
        if not code in PROCESS_CODES:
            return
        self.rediscli.delete(key)
        sorder = SinaWeiboBlogInfo.query_by_id(self.session, data['id'])
        # sorder = SinaWeiboBlogInfo(sorder)
        sorder.status_v2 = 3
        sorder.update_at = datetime.now()
        if code:
            if code == 404:
                sorder.blog_summary = '抓取失败'
            else:
                # sorder.status_v2 = 4
                sorder.blog_summary = '抓取失败'
        else:
            sorder.account_id = data['uid']
            sorder.account_name = data['screen_name']
            sorder.blog_summary = data['text']
            sorder.account_avatar = data['avatar']
        self.session.commit()


    def processAuth(self, data, info, key):
        code = data.get('code')
        if not code in PROCESS_CODES:
            return
        self.rediscli.delete(key)
        sorder = Authentication.query_by_id(self.session, data['id'])
        # sorder = Authentication(sorder)
        sorder.update_at = datetime.now()
        if code:
            sorder.status = 4
            self.session.commit()
            return
        sorder.nick = data['screen_name']
        sorder.avatar = data['avatar']
        sorder.status = 1
        self.session.commit()

def repost_blog_info(url, order_id, weibo_list, account_id=None,
                     account_name=None, account_avatar=None):
    data = {
        "order_id": order_id,
        "account_id": account_id,
        "account_name": account_name,
        "account_avatar": account_avatar,
        "weibo_list": weibo_list,
    }
    url='http://127.0.0.1:1053/api/customer/weibo/info/report'
    logging.info('report blog info {info}'.format(info=json.dumps(data)))
    try:
        resp = requests.post(url, headers=headers, json=data)
        logging.info('report blog resp {resp}'.format(resp=resp.text))
    except:
        logging.info('report blog error {resp}'.format(
            resp=traceback.format_exc()))
    return True

                


def run_service(port=config.APP_PORT):
    #  任务数据接口
    task_app = tornado.web.Application([
        (r'/api/monitor', MonitorOrderHandler),
        (r'/api/pvsync', PvOrderHandler),
    ], debug=(config.LOG_LEVEL == logging.DEBUG))

    router = tornado.routing.RuleRouter([
        (r'/api.*', task_app),
    ])

    http_server = tornado.httpserver.HTTPServer(router)
    http_server.bind(port)
    http_server.start()
    tornado.ioloop.IOLoop.current().start()

if __name__ == "__main__":
    utils.initlog('MonitorService')
    action = sys.argv[1:]
    if action:
        port = action[0]
    else:
        port = '11001'
    logging.info('start monitor service {port}'.format(port=port))
    run_service(port)
