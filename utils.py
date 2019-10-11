import os,logging, redis, random
import time
import config

from logging.handlers import SysLogHandler

def timestamp(): return int(time.time())

def mkdir(d):
    if not os.path.exists(d):
        os.mkdir(d)


def initlog(tag, level=config.LOG_LEVEL):
    syslogHander = SysLogHandler(address='/dev/log')
    formatter = logging.Formatter(tag+'[%(process)d]: %(levelname)s %(filename)s[line:%(lineno)d] %(message)s')
    syslogHander.formatter = formatter
    streamHandler = logging.StreamHandler()
    logging.basicConfig(level=level,
        format='%(asctime)s '+tag+'[%(process)d]: %(levelname)s %(filename)s[line:%(lineno)d] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',handlers=[syslogHander,streamHandler]
    )

def gen_redisClent():
    pool=redis.ConnectionPool(**config.REDIS_DB, max_connections=100,decode_responses=True)
    return redis.Redis(connection_pool=pool)

def genDeviceInfo(info):
    if info is None:
        info = {}
    ua = info.get('ua')
    if ua is None:
        info['ua'] = random.choice(config.UA)
    return info
