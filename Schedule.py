from utils import gen_redisClent
from models.order import *
from models import SessionCustomer
from datetime import date,datetime
from decimal import Decimal
import logging, utils, traceback,time, config

def run():
    session = SessionCustomer()
    redis = gen_redisClent()
    try:
        processInteract(session, redis)
    except:
        logging.error(traceback.format_exc())
    session.commit()
    session.close()



def processPV(session, redis):
    today = date.today()
    start = datetime.now()
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    orders = SinaWeiboPVOrderMonth.queryTodo(session, today)
    for order in orders:
        logging.info('process PV order: {id}'.format(id=order.order_id))
        if SinaWeiboPVOrder4.search(session, order.order_id, start):
            logging.warning('PV order has created')
            continue
        child = SinaWeiboPVOrder4()
        child.parent_order_id = order.order_id
        child.create_at = datetime.now()
        child.user_id = order.user_id
        child.sina_blog_info_id = order.sina_blog_info_id
        child.purchase_number = order.purchase_number
        child.order_id = '{ss}{us}22'.format(ss=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S'), us=str(Decimal.from_float(time.time()).quantize(Decimal('0.000')))[11:])
        child.status = ORDER_STATUS_DOING
        child.update_at = datetime.now()
        child.pay_at = order.pay_at
        child.order_amount = 0
        child.flag = ORDER_FLAG_CACHED
        session.add(child)
        session.commit()
        blog = SinaWeiboBlogInfo.query_by_id(session, child.sina_blog_info_id)
        key = config.REDIS_ORDER_WEIBO_HASH.format(orderType=ORDER_PV_HOME, id=child.order_id)
        info = {
            'order_id':child.order_id,
            'key': key, 
            'parent': child.parent_order_id,
            'purchase_number': child.purchase_number,
            'finished_number' : 0,
            'status': child.status,
            'target': blog.blog_url,
            'type': ORDER_PV_HOME,
            'priority': child.priority,
            'create_at': int(child.pay_at.timestamp()),
            'flag': ORDER_FLAG_CACHED,
            'todo': config.REDIS_TODO_WEIBO_PV_ZSET, 
            'table': child.__tablename__,
        }
        redis.hmset(key, info)
        redis.zadd(config.REDIS_ORDER_WEIBO_ZSET, {key: child.create_at.timestamp()})
        redis.zadd(config.REDIS_TODO_WEIBO_PV_ZSET, {key: child.create_at.timestamp()})


def processInteract(session, redis):
    today = date.today()
    start = datetime.now()
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    orders = SinaWeiboInteractOrder.queryTodo(session, today)
    for order in orders:
        logging.info('process Interact order: {id}'.format(id=order.order_id))
        if SinaWeiboInteractChildOrder.search(session, order.order_id, start):
            continue
        child = SinaWeiboInteractChildOrder()
        child.parent_order_id = order.order_id
        child.create_at = datetime.now()
        child.user_id = order.user_id
        child.sina_blog_info_id = order.sina_blog_info_id
        child.purchase_number = order.purchase_number
        child.order_id = '{ss}{us}24'.format(ss=datetime.strftime(datetime.now(), '%Y%m%d%H%M%S'), us=str(Decimal.from_float(time.time()).quantize(Decimal('0.000')))[11:])
        child.status = ORDER_STATUS_DOING
        child.update_at = datetime.now()
        child.pay_at = order.pay_at
        child.order_amount = 0
        child.center = order.center
        child.priority = 1
        child.flag = ORDER_FLAG_DEFAULT
        session.add(child)
        session.commit()

if __name__ == "__main__":
    utils.initlog('Schedule')

    run()