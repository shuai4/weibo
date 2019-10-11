from models.order import Center, SinaWeiboCommentOrder, SinaWeiboCommentOrder2, SinaWeiboHeartOrder, SinaWeiboHeartOrder2, SinaWeiboInteractOrder, SinaWeiboRepostOrder, SinaWeiboRepostOrder2, OnceOrder
from models import SessionCustomer
from datetime import datetime
import utils, logging, traceback, time



def run():
    session = SessionCustomer()
    try:
        calculate(session)
    except:
        logging.error(traceback.format_exc())
    session.commit()
    session.close()




def calculate(session):
    centers = Center.queryAll(session)
    start_at = datetime.fromtimestamp(time.time()-3600*24)
    for center in centers:
        # center = Center(center)
        speed = doCalculate(session, center.name, SinaWeiboCommentOrder, start_at)
        if speed:
            center.comment_1 = speed
        speed = doCalculate(session, center.name, SinaWeiboHeartOrder, start_at)
        if speed:
            center.heart_1 = speed
        speed = doCalculate(session, center.name, SinaWeiboRepostOrder, start_at)
        if speed:
            center.repost_1 = speed
        speed = doCalculate(session, center.name, SinaWeiboCommentOrder2, start_at)
        if speed:
            center.comment_2 = speed
        speed = doCalculate(session, center.name, SinaWeiboHeartOrder2, start_at)
        if speed:
            center.heart_2 = speed
        speed = doCalculate(session, center.name, SinaWeiboRepostOrder2, start_at)
        if speed:
            center.repost_2 = speed

def doCalculate(session, center, model, start_at):
    orders = model.query_by_start(session, center, start_at)
    # logging.info('found {model} {count} finished in {center}'.format(count=len(orders), model=model, center=center))
    if orders:
        consuming = 0
        count = 0
        for order in orders:
            # order = OnceOrder(order)
            finished_at = order.finished_at
            if finished_at:
                finished_at = finished_at.timestamp()
            else:
                finished_at = time.time()
            count += order.purchase_number
            consuming += (finished_at - order.start_at.timestamp())
        logging.info('{center} {order} finish {count} used {time}'.format(center=center, count=count, time=consuming, order=model))
        if consuming > 0:
            return count*3600/consuming
    return 0








if __name__ == "__main__":
    utils.initlog('Speeder')
    run()