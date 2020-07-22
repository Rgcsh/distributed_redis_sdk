# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""



from redis import Redis

from . import HASH_RING_MAP, byte2str, try_times_default


def url_format(*args, **kwargs):
    """
    生成redis url
    :param args:参数顺序必须为 host,port,db,password
    :param kwargs:
    :return:

    Usage:
    >>> redis_url_format('127.0.0.1', 6379, 1, 'xxx')
    >>> "redis://:xxx@127.0.0.1:6379/1"

    >>> redis_url_format(**{'host': '127.0.0.1', 'port': 6379,'db':1,'password':'xxx'})
    >>> "redis://:xxx@127.0.0.1:6379/1"
    """
    password = None
    if args:
        if len(args) == 3:
            host, port, db = args
        else:
            host, port, db, password = args
    else:
        host = kwargs.get('host')
        port = kwargs.get('port')
        db = kwargs.get('db')
        password = kwargs.get('password')

    if password:
        return f"redis://:{password}@{host}:{port}/{db}"
    else:
        return f"redis://{host}:{port}/{db}"


@try_times_default
def get_hash_ring_map(redis_obj):
    """
    获取manager redis中的map,并格式化
    :return:
    """
    _dict = redis_obj.hgetall(HASH_RING_MAP)
    new_dict = {}
    for k, v in _dict.items():
        new_dict[byte2str(k)] = byte2str(v)
    return new_dict


def get_redis_obj(*args, **kwargs):
    """
    获取 操作redis的对象
    :return:

    Usage:
    >>> get_redis_obj('127.0.0.1', 6379, 1, 'xxx')

    >>> get_redis_obj(**{'host': '127.0.0.1', 'port': 6379,'db':1,'password':'xxx'})
    """
    password = None
    if args:
        if len(args) == 1:
            return Redis.from_url(args[0])
        if len(args) == 3:
            host, port, db = args
        else:
            host, port, db, password = args
    else:
        host = kwargs.get('host')
        port = kwargs.get('port')
        db = kwargs.get('db')
        password = kwargs.get('password')

    # 获取redis对象
    return Redis(host, port, db, password)


def get_func_name(command_name):
    """
    根据输入的 字符串 redis命令 获取对应的 函数命令 名
    规则:
    1.空格 改为 下划线
    2.大写改为小写

    :param command_name:
    :return:
    Usage:
    >>> get_func_name('ACL LOAD')
    >>> 'acl_load'
    >>> get_func_name('BGSAVE')
    >>> 'bgsave'
    >>> get_func_name('SET')
    >>> 'set'
    """
    _dict = {'DEL': 'delete'}
    if command_name in _dict:
        return _dict.get(command_name)

    command_name = command_name.replace(' ', '_')
    return command_name.lower()
