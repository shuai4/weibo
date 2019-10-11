import re, logging, utils
import time
import traceback
from datetime import datetime

from models.order import *
from models import SessionCustomer
from decimal import *

def run():
    logging.info('running...')
    session = SessionCustomer()
    try:
        refund(session, SinaWeiboCommentOrder)
        refund(session, SinaWeiboCommentOrder2)
        refund(session, SinaWeiboHeartOrder)
        refund(session, SinaWeiboHeartOrder2)
        refund(session, SinaWeiboPVOrder1)
        refund(session, SinaWeiboPVOrder5)
        refund(session, SinaWeiboRepostOrder)
        refund(session, SinaWeiboRepostOrder2)
    except:
        logging.error('err: %s' % traceback.format_exc())
    logging.info('end')
    session.commit()
    session.close()


def refund(session, model):
    orders = model.queryRefund(session)
    for order in orders:
        logging.info('found order {order} refund status {status}, flag {flag}'.format(order=order.order_id, status=order.status, flag=order.flag))
        if order.order_amount and order.finished_number < order.purchase_number:
            amount = order.order_amount/order.purchase_number * \
                (order.purchase_number-order.finished_number)
            amount = int(amount*100)/100
            name, balance = CapitalFlow.refund(session, order, Decimal.from_float(amount))
            logging.info(
                'refund {order} {user} amount:{amount}, new balance: {balance}'.
                format(order=order.order_id,
                    user=name,
                    amount=amount,
                    balance=balance))
        else:
            order.flag = ORDER_FLAG_VERIFY


if __name__ == "__main__":
    utils.initlog('refund')
    run()
