# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/23 15:44'

Usage:

"""
import inspect
from collections import OrderedDict

import redis
from redis import ConnectionPool
from redis import Redis

from .log_obj import log
from .utils import get_arg_names, get_id, get_arg_default, try_times_default, k_prefix, get_hash_ring_map, get_func_name, \
    ConsistencyHash


class BaseRedis(Redis):
    """
    redis基类
    1.对 execute_command进行二次开发
    2.扩充些 供 子类或内部使用的 方法
    """

    def __init__(self, ):
        super(BaseRedis, self).__init__()
        self.key_prefix = k_prefix
        self.manager_redis_obj = None

    def _use_prefix(self, key: list or str or int, use_prefix):
        """
        是否使用前缀,使用则添加
        :param use_prefix:
        :return:
        """
        if not isinstance(key, (list, str, int)):
            raise TypeError
        if use_prefix:
            if isinstance(key, list):
                key = [self.key_prefix + str(item) for item in key]
            else:
                key = self.key_prefix + str(key)
        return key

    @classmethod
    def _redis_from_url(cls, node_url: str):
        """
        通过url获取redis对象
        注意:此处获取的redis对象是直接从redis包导入的,可以进行任何操作,不会对 execute_command进行修改
        :param node_url:
        :return:
        """
        return redis.from_url(node_url)

    def _get_all_node_url(self):
        """
        获取所有node redis的真实url
        :return:
        """
        hash_map = get_hash_ring_map(self.manager_redis_obj)
        return set(hash_map.values())

    def get_redis_node_obj(self, key: str or int, use_prefix=False):
        """
        通过key生成hashkey,获取对应 节点的redis obj
        注意:此处获取的redis对象是直接从redis包导入的,可以进行任何操作,不会对 execute_command进行修改
        :param key:
        :param use_prefix:默认不使用添加key的前缀
        :return:
        """
        if not isinstance(key, (str, int)):
            raise TypeError

        hash_map = get_hash_ring_map(self.manager_redis_obj)
        key = self._use_prefix(key, use_prefix)
        node_url = ConsistencyHash(hash_map).get_node(key)
        return self._redis_from_url(node_url)

    def _cache_obj(self, key, cache_obj):
        """
        是否生成 Redis对象
        :return:
        """
        if not cache_obj:
            cache_obj = self.get_redis_node_obj(key)
        elif not isinstance(cache_obj, Redis):
            raise LookupError('cache_obj必须是Redis对象')
        return cache_obj

    @try_times_default
    def execute_command(self, *args, **options):
        """
        Execute a command and return a parsed response
        继承自Redis对象的 执行具体命令的函数,对此函数进行修改
        修改内容为:
        通过key调用一致性hash算法获取对应redis节点的url
        通过url获取连接池,然后进行后续原来的操作
        优点:
        在调用此sdk时,可以像使用普通 redis sdk一样操作,如 DistributedRedisSdk().set() 等等方法进行操作

        警告:
        1.Redis的有些命令函数(如:client_id) 不需要 key,所以在调用此函数时会存在 参数不足2个的情况,针对此情况 直接Raise错误
        2.Redis的有些命令函数 的第一个参数不是 key,即使分配到了节点上也是错误的结果,这种也不能使用
        :param args:
        :param options:
        :return:
        """
        # 某些命令 不能分配到节点,此处进行校验
        # 判断参数长度不能小于2个(如果小于,说明肯定没有key)
        if len(args) < 2:
            raise Exception('此分布式redis对象不支持使用此方法,因为没有key,无法定位到具体redis节点,'
                            '请使用 get_redis_obj() 函数获取具体节点对象进行后续操作')

        # 通过 command_name 找到对应的函数名,然后找到对应参数
        command_name = args[0]
        func_name = get_func_name(command_name)
        command_func = getattr(Redis, func_name)
        func_params = command_func.__code__.co_varnames
        # 第二个参数 进行校验,command_name不在指定的list中
        allow_command_list = ['touch']
        if func_params[1] not in ['key', 'keys', 'name', 'names', 'src'] and func_name not in allow_command_list:
            raise Exception('此分布式redis对象不支持使用此方法,因为没有key或name,无法定位到具体redis节点,'
                            '请使用 get_redis_obj() 函数获取具体节点对象进行后续操作')

        # 某些命令不能找到对应节点
        not_allowed_command_list = ['config_set']
        if command_name in not_allowed_command_list:
            raise Exception('此分布式redis对象不支持使用此方法,无法定位到具体redis节点,'
                            '请使用 get_redis_obj() 函数获取具体节点对象进行后续操作')

        # 获取 执行的redis命令
        # 获取操作的 key
        key = args[1]
        if not isinstance(key, (int, str)):
            raise TypeError
        if isinstance(key, int):
            key = str(key)

        # 通过key获取对应的节点url
        hash_map = get_hash_ring_map(self.manager_redis_obj)
        node_url = ConsistencyHash(hash_map).get_node(key)
        log.info(f'node_url:{node_url},key:{key},command_name:{command_name}')

        # 通过节点url获取redis对象的 连接池
        pool = ConnectionPool.from_url(node_url)
        conn = self.connection or pool.get_connection(command_name, **options)
        try:
            conn.send_command(*args)
            return self.parse_response(conn, command_name, **options)
        except (ConnectionError, TimeoutError) as e:
            conn.disconnect()
            if not (conn.retry_on_timeout and isinstance(e, TimeoutError)):
                raise
            conn.send_command(*args)
            return self.parse_response(conn, command_name, **options)
        finally:
            if not self.connection:
                pool.release(conn)

    def _bypass_cache(self, unless, f, *args, **kwargs):
        """Determines whether or not to bypass the cache by calling unless().
        Supports both unless() that takes in arguments and unless()
        that doesn't.
        """
        bypass_cache = False

        if callable(unless):
            argspec = inspect.getfullargspec(unless)
            has_args = len(argspec.args) > 0 or argspec.varargs or argspec.varkw

            # If unless() takes args, pass them in.
            if has_args:
                if unless(f, *args, **kwargs) is True:
                    bypass_cache = True
            elif unless() is True:
                bypass_cache = True

        return bypass_cache

    def _memoize_kwargs_to_args(self, f, *args, **kwargs):
        #: Inspect the arguments to the function
        #: This allows the memoization to be the same
        #: whether the function was called with
        #: 1, b=2 is equivilant to a=1, b=2, etc.
        new_args = []
        arg_num = 0

        # If the function uses VAR_KEYWORD type of parameters,
        # we need to pass these further
        kw_keys_remaining = list(kwargs.keys())
        arg_names = get_arg_names(f)
        args_len = len(arg_names)

        for i in range(args_len):
            arg_default = get_arg_default(f, i)
            if i == 0 and arg_names[i] in ("self", "cls"):
                #: use the id func of the class instance
                #: this supports instance methods for
                #: the memoized functions, giving more
                #: flexibility to developers
                arg = get_id(args[0])
                arg_num += 1
            elif arg_names[i] in kwargs:
                arg = kwargs[arg_names[i]]
                kw_keys_remaining.pop(kw_keys_remaining.index(arg_names[i]))
            elif arg_num < len(args):
                arg = args[arg_num]
                arg_num += 1
            elif arg_default:
                arg = arg_default
                arg_num += 1
            else:
                arg = None
                arg_num += 1

            #: Attempt to convert all arguments to a
            #: hash/id or a representation?
            #: Not sure if this is necessary, since
            #: using objects as keys gets tricky quickly.
            # if hasattr(arg, '__class__'):
            #     try:
            #         arg = hash(arg)
            #     except:
            #         arg = get_id(arg)

            #: Or what about a special __cacherepr__ function
            #: on an object, this allows objects to act normal
            #: upon inspection, yet they can define a representation
            #: that can be used to make the object unique in the
            #: cache key. Given that a case comes across that
            #: an object "must" be used as a cache key
            # if hasattr(arg, '__cacherepr__'):
            #     arg = arg.__cacherepr__

            new_args.append(arg)

        new_args.extend(args[len(arg_names):])
        return (
            tuple(new_args),
            OrderedDict(
                sorted(
                    (k, v) for k, v in kwargs.items() if k in kw_keys_remaining
                )
            ),
        )
