# coding=utf-8
import tornado, sys, traceback, time, json, requests
import tornado.web
import tornado.httpclient
from tornado.options import define, options, parse_command_line

import config, utils, logging
from handlers import BaseHandler
from handlers.pvOrderHandler import PvOrderHandler


headers = {
    "Content-Type": "application/json"
}


class MonitorOrderHandler(BaseHandler):
    

    async def post(self):
        try:
            body = self.request.body
            logging.info('receive {ip} report: {data}'.format(data=body, ip=self.reqsrcip))
            msg = None
            self.processReport(json.loads(body))
            order = self.getVerifyOrder()
            if order:
                self.send(order)
                return
            order = self.getMonitorOrders()
            if order:
                self.send(order)
                return
            order = self.getAuthOrder()
            if order:
                self.send(order)
        except :
            msg = traceback.format_exc()
            logging.error(msg)
            self.send_error(status_code=500, reason=msg)


    def getMonitorOrders(self):
        keys = self.rediscli.zrangebyscore(config.REDIS_TODO_WEIBO_MONITOR_ZSET, 0, time.time())
        for key in keys:
            order = self.rediscli.hgetall(key)
            if order and int(order['status']) == 1:
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_MONITOR_ZSET, {key: (time.time()+10)})
                data={
                    'key': key,
                    'target': order['target'],
                    'last_blog': order['last_blog'],
                    'type': 'monitor'
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
                    'key': keys,
                    'target': order['target'],
                    'last_blog': '0',
                    'type': 'auth',
                }
                return data
            else:
                self.rediscli.zrem(config.REDIS_TODO_WEIBO_AUTH_ZSET, key)

        return {}

    def getVerifyOrder(self):
        keys = self.rediscli.zrangebyscore(config.REDIS_TODO_WEIBO_VERIFY_ZSET, 0, time.time())
        for key in keys:
            order = self.rediscli.hgetall(key)
            if order and int(order['status']) == 2:
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_VERIFY_ZSET, {key:time.time()+20})
                data={
                    'key': key,
                    'target': order['target'],
                    'type': 'verify',
                }
                return data
            else:
                self.rediscli.zrem(config.REDIS_TODO_WEIBO_AUTH_ZSET, key)

        return {}


            

    def processReport(self, key, data):
        try:
            order = self.rediscli.hgetall(key)
            if order:
                if order.get('type') == 'auth':
                    order['nick'] = data['screen_name']
                    order['avatar'] = data['avatar']
                    order['status'] = 1
                    order['update_at'] = int(time.time())
                    if self.rediscli.zscore(config.REDIS_TODO_WEIBO_AUTH_ZSET, key):
                        self.rediscli.zrem(config.REDIS_TODO_WEIBO_AUTH_ZSET, key)
                        self.rediscli.hmset(key,order)

                elif order.get('type') == 'verify':
                    order['nick'] = data['screen_name']
                    order['avatar'] = data['avatar']
                    order['uid'] = data['uid']
                    order['text'] = data['text']
                    order['status'] = 3
                    order['update_at'] = int(time.time())
                    if self.rediscli.zscore(config.REDIS_TODO_WEIBO_AUTH_ZSET, key):
                        self.rediscli.zrem(config.REDIS_TODO_WEIBO_AUTH_ZSET, key)
                        self.rediscli.hmset(key,order)


                else:
                    self.rediscli.zadd(config.REDIS_TODO_WEIBO_MONITOR_ZSET, {key: time.time()+60})
                    if int(data['last_blog']) > int(order['last_blog']):
                        self.rediscli.hset(key, 'update_at', int(time.time()))
                        self.rediscli.hset(key, 'last_blog', data['last_blog'])
                        weibo_list = data.get('weibo_list')
                        logging.info('{order} {list}'.format(order=order['order_id'], list=weibo_list))
                        if weibo_list:
                            screen_name = data['screen_name']
                            avatar = data['avatar']
                            account_id = order['target']
                            order_id = order['order_id']
                            url = order['report']
                            repost_blog_info(url, order_id, weibo_list, account_id=account_id, account_name=screen_name, account_avatar=avatar)
        except:
            logging.error(traceback.format_exc())


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
    port = action[0]
    logging.info('start monitor service {port}'.format(port=port))
    run_service(port)
    logging.info('start monitor service {port}'.format(port=11000))
    run_service(10001)

