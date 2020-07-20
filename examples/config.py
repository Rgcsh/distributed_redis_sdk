# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/20 09:34'

Usage:

"""


class Config(object):
    """
    配置类
    """
    DEBUG = True
    DIS_MANAGER_REDIS_HOST = '127.0.0.1'
    DIS_MANAGER_REDIS_PORT = '6379'
    DIS_MANAGER_REDIS_PASSWORD = ''
    DIS_MANAGER_REDIS_DB = '13'
    DIS_CACHE_PREFIX = 'BEI:'
