import time
import requests
import random
import traceback
import json
import logging
import re
from datetime import datetime
from models import SessionCustomer
from models.order import *

import config
import utils
import convertUrl
from convertUrl import *

PRIORITY = {ORDER_COMMENT_FAST, ORDER_HEART_FAST, ORDER_REPOST_FAST}
COMMENTS = {ORDER_COMMENT, ORDER_COMMENT_FAST, ORDER_REPOST, ORDER_REPOST_FAST}


def datetime2str(date): return date.strftime('%Y-%m-%d %H:%M:%S')


class OrderService(object):
    """ 向 redis 添加将要执行的订单
#         这里决定了同时会执行那些订单、订单优先级、以及订单的拆分
#     """

    def __init__(self):
        self.rediscli = utils.gen_redisClent()

def run(self):
    logging.info('start...')
    while True:
        session = SessionCustomer()
        session.rollback()
        try:
            logging.info('run...')
            self.queryMonitorOrders(session)
            self.sync(session)
            self.verifyOrders(session, SinaWeiboCommentOrder)
            self.verifyOrders(session, SinaWeiboCommentOrder2)
            self.verifyOrders(session, SinaWeiboHeartOrder)
            self.verifyOrders(session, SinaWeiboHeartOrder2)
            self.verifyOrders(session, SinaWeiboRepostOrder)
            self.verifyOrders(session, SinaWeiboRepostOrder2)
            self.verifyOrders(session, SinaWeiboPVOrder1)
            self.verifyPV1Orders(session)
            self.verifyPV5Orders(session)
            self.dispatchOrders(session)
            self.queryPVOrders(session, SinaWeiboPVOrder1, ORDER_PV_ART)
            self.queryPVOrders(session, SinaWeiboPVOrder5, ORDER_PV_HOME)
            self.queryAuths(session)
        except:
            logging.error('err: %s' % traceback.format_exc())
        session.commit()
        session.close()
        logging.info('end...')
        time.sleep(5)

def queryPVOrders(self, session, model, orderType):
    orders = model.query(session, ORDER_FLAG_DEFAULT, ORDER_STATUS_DOING)
    for order in orders:
        try:
            logging.info('found {orderType}:{orderid} task'.format(
                orderType=orderType, orderid=order.order_id))
            blog = SinaWeiboBlogInfo.query_by_id(
                session, order.sina_blog_info_id)
            timest = int(order.create_at.timestamp())
            orderKey = config.REDIS_ORDER_WEIBO_HASH.format(
                orderType=orderType, id=order.order_id)
            order.flag = ORDER_FLAG_DOING
            orderinfo = {
                'key': orderKey,
                'order_id': order.order_id,
                'target': blog.blog_url,
                'type': orderType,
                'purchase_number': order.purchase_number,
                'finished_number': order.finished_number,
                'status': order.status,
                'create_at': int(timest),
                'priority': order.priority*PRIORITY_RATE[orderType],
                'flag': order.flag,
                'todo': config.REDIS_TODO_WEIBO_PV_ZSET,
                'table': order.__tablename__,
            }
            self.rediscli.hmset(orderKey, orderinfo)
            self.rediscli.zadd(config.REDIS_ORDER_WEIBO_ZSET, {
                orderKey: timest})
            self.rediscli.zadd(config.REDIS_TODO_WEIBO_PV_ZSET, {
                orderKey: timest/(order.priority*PRIORITY_RATE[orderType])})
        except:
            logging.error(traceback.format_exc())

def dispatchOrders(self, session):
    comment_1 = {}
    comment_2 = {}
    heart_1 = {}
    heart_2 = {}
    repost_1 = {}
    repost_2 = {}
    follow_1 = {}
    follow_2 = {}
    for center in Center.queryAll(session):
        if center.comment_1:
            comment_1[center.name] = center.comment_1
        if center.comment_2:
            comment_2[center.name] = center.comment_2
        if center.heart_1:
            heart_1[center.name] = center.heart_1
        if center.heart_2:
            heart_2[center.name] = center.heart_2
        if center.repost_1:
            repost_1[center.name] = center.repost_1
        if center.repost_2:
            repost_2[center.name] = center.repost_2
        if center.follow_1:
            follow_1[center.name] = center.follow_1
        if center.follow_2:
            follow_2[center.name] = center.follow_2
    self.doDispatch(session, comment_1, SinaWeiboCommentOrder, [SinaWeiboHeartOrder, SinaWeiboRepostOrder])
    self.doDispatch(session, comment_2, SinaWeiboCommentOrder2, [SinaWeiboHeartOrder2, SinaWeiboRepostOrder2])
    self.doDispatch(session, heart_1, SinaWeiboHeartOrder, [SinaWeiboCommentOrder, SinaWeiboRepostOrder])
    self.doDispatch(session, heart_2, SinaWeiboHeartOrder2, [SinaWeiboCommentOrder2, SinaWeiboRepostOrder2])
    self.doDispatch(session, repost_1, SinaWeiboRepostOrder, [SinaWeiboCommentOrder, SinaWeiboHeartOrder])
    self.doDispatch(session, repost_2, SinaWeiboRepostOrder2, [SinaWeiboCommentOrder2, SinaWeiboHeartOrder2])
    self.doDispatch(session, follow_1, SinaWeiboInteractOrder, [])
    # self.doDispatch(session, comment_1, SinaWeiboCommentOrder)

def doDispatch(self, session, centers, model, includes):
    weights = []
    for center, speed in centers.items():
        todo = 0
        for order in model.queryAllDoing(session, center):
            todo += order.purchase_number
        weights.append(
            [center, todo/speed]
        )
    for order in model.query(session, ORDER_FLAG_VERIFY, ORDER_STATUS_DOING):
        # order = BaseOrder(order)
        logging.info('Dispatch {order} {id}'.format(order=order.__tablename__, id=order.order_id))
        abort = False
        for include in includes:
            other = include.querySameDoing(session, order.sina_blog_info_id)
            if other:
                order.center = other.center
                order.flag = ORDER_FLAG_DEFAULT
                session.commit()
                abort = True
                break
        if abort:
            continue
        weights =  sorted(weights, key=lambda e:e[1])
        name = weights[0][0]
        weight = weights[0][1]
        weights[0][1] = (weight+order.purchase_number/centers[name])/2
        logging.info('Dispatch {order} {id} to {center}'.format(order=order.__tablename__, id=order.order_id, center=name))
        order.center = name
        order.flag = ORDER_FLAG_DEFAULT
        session.commit()

def queryMonitorOrders(self, session):
    keys = set(self.rediscli.zrange(
        config.REDIS_TODO_WEIBO_MONITOR_ZSET, 0, -1))
    count=0
    for order in SinaWeiboMonitorOrder.query_task(session):
        count += 1
        try:
            logging.info('found monitor order: {orderid}, status: {status}'.format(
                orderid=order.order_id, status=order.status))
            key = config.REDIS_ORDER_WEIBO_MONITOR_HASH.format(
                id=order.order_id)
            logging.info(key)
            if key in keys:
                keys.discard(key)
            else:
                lastblog = order.last_blog
                if not lastblog:
                    lastblog = 0
                    order.last_blog=0
                uid = get_uid_from_homepage(order.homepage)
                if uid is None:
                    logging.error(
                        'error order {id} uid is None'.format(id=order.order_id))
                    order.status = 4
                    session.commit()
                    continue
                info = {
                    'key': key,
                    'last_blog': lastblog,
                    'target': uid,
                    'order_id': order.order_id,
                    'user_id': order.user_id,
                    'status': order.status,
                    'report': 'http://c.ab.ink/api/customer/weibo/info/report'
                }
                logging.info(info)
                self.rediscli.hmset(key, info)
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_MONITOR_ZSET, {
                                   key: time.time()})
                # order.flag = ORDER_FLAG_DOING
        except:
            logging.error(traceback.format_exc())
    if keys:
        logging.info('delete keys {keys}'.format(keys=keys))
        self.rediscli.delete(*keys)
    logging.info('sync {count} monitor order'.format(count=count))

def sync(self, session):
    for orderkey in self.rediscli.zrange(config.REDIS_ORDER_WEIBO_ZSET, 0, -1):
        try:
            orderinfo = self.rediscli.hgetall(orderkey)
            if orderinfo:
                logging.info('sync order {order}'.format(order=orderinfo))
                model = TABLES[orderinfo['table']]
                order_id = orderinfo['order_id']
                order = model.query_order_by_id(session, order_id)

                if order is None:
                    logging.error(
                        '{order} not found in db'.format(order=orderkey))
                    self.rediscli.zrem(
                        config.REDIS_ORDER_WEIBO_ZSET, orderkey)
                    self.rediscli.delete(orderkey)
                    continue
                status = int(orderinfo['status'])
                if order.status == ORDER_STATUS_STOPPING:
                    logging.info(
                        'stop order {order}'.format(order=orderkey))
                    order.status = ORDER_STATUS_STOPPED
                    session.commit()
                    status = ORDER_STATUS_STOPPED
                    self.rediscli.hset(
                        orderkey, 'status', ORDER_STATUS_STOPPED)

                finished_number = int(orderinfo['finished_number'])
                order.finished_number = finished_number
                if status >= ORDER_STATUS_DONE:
                    if order.status != status:
                        order.status = status
                        order.update_at = datetime.now()
                        order.finished_at = order.update_at
                    running_number = int(orderinfo.get('runing_number', 0))
                    if running_number <= 0:
                        order.flag = ORDER_FLAG_DONE
                        session.commit()
                        self.rediscli.zrem(
                            config.REDIS_ORDER_WEIBO_ZSET, orderkey)
                        comment = orderinfo.get('comment')
                        if comment:
                            self.rediscli.delete(comment)
                        self.rediscli.delete(orderkey)
                    continue
                if finished_number == 0:
                    continue

                if order.start_at is None:
                    order.flag = ORDER_FLAG_DOING
                    order.start_at = datetime.now()
                    self.rediscli.hset(orderkey, 'flag', ORDER_FLAG_DOING)
                order.update_at = datetime.now()

            else:
                logging.error(
                    'order {key} not found info'.format(key=orderkey))
                self.rediscli.zrem(config.REDIS_ORDER_WEIBO_ZSET, orderkey)
        except:
            logging.error(traceback.format_exc())

def verifyOrders(self, session, model):
    orders = model.query(session, ORDER_FLAG_DEFAULT, ORDER_STATUS_VERIFY)
    for order in orders:
        try:
            logging.info('found {orderid} to verify'.format(
                orderid=order.order_id))
            blog = SinaWeiboBlogInfo.query_by_id(
                session, order.sina_blog_info_id)
            user = User.query_by_id(session, order.user_id)
            if blog.status_v2 == 2:
                continue
            if blog.status_v2 == 1:
                mid = getMid(blog.blog_url)
                if mid is None:
                    mid = getMid(blog.m_blog_url)
                uid = get_uid_from_homepage(blog.blog_url)
                if uid is None:
                    uid = get_uid_from_homepage(blog.m_blog_url)
            elif blog.status_v2 == 3:
                if order.__tablename__ == 'sina_weibo_pv_1_order':
                    order.status = ORDER_STATUS_DOING
                    order.flag = ORDER_FLAG_DEFAULT
                    continue

                if isOutOfRange(session,model,user, blog.id, order):
                    continue
                order.status = ORDER_STATUS_DOING
                order.flag = ORDER_FLAG_VERIFY
                session.commit()
                continue
            elif blog.status_v2 == 4:
                order.status = ORDER_STATUS_ORDER_ERROR
                order.flag = ORDER_FLAG_DONE
                order.reason = '链接格式错误'
                session.commit()
                continue
            auth = None
            if uid:
                if mid:
                    blog.blog_url='https://weibo.com/{uid}/{mid}'.format(uid=uid, mid=convertUrl.mid_to_gid(mid))
                    blog.m_blog_url='https://m.weibo.cn/{uid}/{mid}'.format(uid=uid, mid=mid)
                    if order.__tablename__ == 'sina_weibo_pv_1_order':
                        order.status = ORDER_STATUS_DOING
                        order.flag = ORDER_FLAG_DEFAULT
                        continue
                blog.account_id = uid
                auth = checkAuthed(session,order, blog, user)
                # if auth is None:
                #     continue
                if auth and blog.status_v2 == 1:
                    blog.account_name=auth.nick
                    blog.account_id=uid
                    blog.account_avatar=auth.avatar

            if mid is None:
                logging.info('could found mid from {url}'.format(url=blog.blog_url))
                #blog.account_name = 'url解析异常, 请检查'
                blog.blog_summary = 'url无法解析出博文id'
                blog.status_v2 = 4
                order.status = ORDER_STATUS_ORDER_ERROR
                order.flag = ORDER_FLAG_DONE
                session.commit()
                continue
            try:
                int(mid)
            except :
                logging.error(traceback.format_exc())
                blog.blog_summary = 'url无法解析出博文id'
                order.status = ORDER_STATUS_ORDER_ERROR
                order.flag = ORDER_FLAG_DONE
                order.reason = traceback.format_exc()
                continue

            tmpBlog = SinaWeiboBlogInfo.query_by_mid(session, mid)
            if tmpBlog and tmpBlog.id != blog.id:
                order.sina_blog_info_id = tmpBlog.id
                session.commit()
                continue
            blog.blog_id = mid
            blog.status_v2=2
            # order.status = ORDER_STATUS_DOING
            # order.flag = ORDER_FLAG_VERIFY
            session.commit()
            key = config.REDIS_ORDER_WEIBO_VERIFY_HASH.format(id=blog.id)
            info = {
                'key': key,
                'target': mid,
                'id': blog.id,
                'status': 2,
                'type': 'verify'
            }
            self.rediscli.hmset(key, info)
            self.rediscli.zadd(config.REDIS_TODO_WEIBO_VERIFY_ZSET, {key:(order.create_at.timestamp()/order.priority)})
        except:
            order.status = ORDER_STATUS_ORDER_ERROR
            order.flag = ORDER_FLAG_DONE
            order.reason = traceback.format_exc()
            session.commit()
            logging.error(traceback.format_exc())

def verifyPV1Orders(self, session):
    pass

def verifyPV5Orders(self, session):
    pass

def verifyPVMonthOrders(self, session):
    pass

    def queryAuths(self, session):
        logging.info('query auths')
        for order in Authentication.query_by_status(session, 0):
            try:
                logging.info('found auth order: {orderid}'.format(
                    orderid=order.id))
                key = config.REDIS_ORDER_WEIBO_AUTH_HASH.format(id=order.id)
                uid = get_uid_from_homepage(order.blog_url)
                if uid is None:
                    order.status = 4
                    continue
                order.uid = uid
                order.status = 5
                info = {
                    'key': key,
                    'target': uid,
                    'id': order.id,
                    'status': order.status,
                    'type': 'auth'
                }
                # logging.info(info)
                self.rediscli.hmset(key, info)
                self.rediscli.zadd(config.REDIS_ORDER_WEIBO_AUTH_ZSET, {
                                   key: time.time()})
                self.rediscli.zadd(config.REDIS_TODO_WEIBO_AUTH_ZSET, {
                                   key: time.time()})
            except:
                logging.error(traceback.format_exc())


def isOutOfRange(session, model, user, blog_id, order):

    if model.__tablename__ == 'sina_weibo_pv_1_order':
        order.status = ORDER_STATUS_DOING
        order.flag = ORDER_FLAG_DEFAULT
        return True
    total = 0
    hiss = model.query_order_by_blog_info_id(session, blog_id)
    for his in hiss:
        if his.status >= ORDER_STATUS_DONE:
            total += his.finished_number
        elif his.status > ORDER_STATUS_PAY:
            total += his.purchase_number
    limit = 0
    if model.__tablename__ == 'sina_weibo_comment_1_order':
        limit = user.comment_1
    elif model.__tablename__ == 'sina_weibo_comment_2_order':
        limit = user.comment_2
    elif model.__tablename__ == 'sina_weibo_heart_1_order':
        limit = user.heart_1
    elif model.__tablename__ == 'sina_weibo_heart_2_order':
        limit = user.heart_2
    elif model.__tablename__ == 'sina_weibo_repost_1_order':
        limit = user.repost_1
    elif model.__tablename__ == 'sina_weibo_repost_2_order':
        limit = user.repost_2
    if total > limit:
        logging.info('订单超限{total}'.format(total=limit))
        order.status = ORDER_STATUS_REJECT
        order.flag = ORDER_FLAG_DONE
        order.reason = '订单数量超出限制{limit}'.format(limit=limit)
        session.commit()
        return True

def checkAuthed(session, order, blog, user):
    auth = Authentication.queryAuthed(session, blog.account_id)
    if auth is None:
        logging.error('微博尚未备案 {user} {type} {order} {url}'.format(
            user=user.account, type=order.__tablename__, order=order.order_id, url=blog.blog_url or blog.m_blog_url))
        # blog.status_v2 = 4
        # order.status = ORDER_STATUS_REJECT
        # order.flag = ORDER_FLAG_DONE
        # order.reason = '微博尚未备案，请备案后联系客服'
        session.commit()
    return auth


def get_uid_from_homepage(homepage):
    # https://m.weibo.cn/profile/5846555329
    # https://m.weibo.cn/5846555329/4381235709132415
    # https://weibo.com/u/5846555329
    # https://weibo.com/1178975384/HxGDNefrl
    # https://weibo.com/5846555329/profile
    uid = re.search(r'm.weibo.cn/(\d{8,11})/(\d{16,16})', homepage)
    if uid:
        return uid.groups()[0]
    uid = re.search(r'm.weibo.cn/profile/(\d{8,11})', homepage)
    if uid:
        return uid.groups()[0]
    uid = re.search(r'weibo\.com/u/(\d{8,11})', homepage)
    if uid:
        return uid.groups()[0]
    uid = re.search(r'weibo\.com/(\d{8,11})/(\w{7,9})', homepage)
    if uid:
        return uid.groups()[0]
    logging.error('could found uid from {url}'.format(url=homepage))


def getMid(url):
    mid = re.search(r'weibo.cn/(\d{8,11})/(\d{16,16})', url)
    if mid:
        return mid.groups()[1]
    mid = re.search(r'weibo.com/(\d{8,11})/(\w{9,9})', url)
    if mid:
        return convertUrl.gid_to_mid(mid.groups()[1])
    mid = re.search(r'weibo.cn/detail/(\d{16,16})', url)
    if mid:
        return mid.groups()[0]
    mid = re.search(r'weibo.cn/status/(\d{16,16})', url)
    if mid:
        return mid.groups()[0]
    logging.error('could found mid from {url}'.format(url=url))


def getWeiboInfo(mid):

    url = 'https://m.weibo.cn/statuses/show?id='+str(mid)
    headers = {
        'User-Agent': random.choice(config.UA),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
    }
    for _ in range(3):
        try:
            resp = requests.get(url, headers=headers, allow_redirects=False)
            if resp.status_code == 200:
                data = resp.json()
                if data['ok']:
                    data = data['data']
                    text = data['text']
                    if text == '转发微博' and 'retweeted_status' in data:
                        text = data['retweeted_status']['text']
                    uid = str(data['user']['id'])
                    name = data['user']['screen_name']
                    avatar = data['user']['avatar_hd']
                    time.sleep(1)
                    return uid, name, avatar, text
        except:
            logging.error(traceback.format_exc())
        time.sleep(1)
    return None, None, None, '博文抓取失败'


# if __name__ == "__main__":
#     utils.initlog('OrderService')
#     OrderService().run()
