# -*- coding: utf-8 -*-
# (C) Rgc, 2020
# All rights reserved
# @Author: 'Rgc <2020956572@qq.com>'
"""
提供根据key获取分布式redis节点 对象的功能
"""
import redis
from redis import Redis, ConnectionPool

from .exception import InvalidConfigException
from .log_obj import log
from .utils.consistency_hash import ConsistencyHash
from .utils.constant import *
from .utils.redis_action import get_redis_obj, get_hash_ring_map, get_func_name


class DistributedRedisSdk(Redis):
    """分布式redis客户端类"""

    def __init__(self, app=None, config=None):
        super(DistributedRedisSdk, self).__init__()
        # Flask的config必须是dict或者None
        if not (config is None or isinstance(config, dict)):
            raise InvalidConfigException("`config`参数必须是dict的实例或者None")

        # 存储配置
        self.config = config

        self.k_redis_host = k_redis_host
        self.k_redis_port = k_redis_port
        self.k_redis_password = k_redis_password
        self.k_redis_db = k_redis_db
        self.manager_redis_obj = None
        # 加载时即配置
        if app is not None:
            self.app = app
            self.init_app(app, config)

    def init_app(self, app, config=None):
        """ Flask扩展懒加载实现 """

        # Flask的config必须是dict或者None
        if not (config is None or isinstance(config, dict)):
            raise InvalidConfigException("`config`参数必须是dict的实例或者None")

        # 更新所有的配置
        basic_config = app.config.copy()
        if self.config:
            basic_config.update(self.config)
        if config:
            basic_config.update(config)
        config = basic_config

        # 设置参数
        self.k_redis_host = config.get(k_redis_host)
        self.k_redis_port = config.get(k_redis_port)
        self.k_redis_password = config.get(k_redis_password)
        self.k_redis_db = config.get(k_redis_db)

        self.manager_redis_obj = Redis(self.k_redis_host, self.k_redis_port, self.k_redis_db, self.k_redis_password)

        # 检查redis节点集群是否有 节点
        if not get_hash_ring_map(self.manager_redis_obj):
            raise Exception('redis节点集群 没有节点,请添加!')

        self.app = app

        # 扩展原始Flask功能
        self.extend_flask_middleware(app)

        app.extensions["distributed_redis_sdk"] = self

    def get_redis_node_obj(self, key):
        """
        通过key生成hashkey,获取对应 节点的redis obj
        :param key:
        :return:
        """
        hash_map = get_hash_ring_map(self.manager_redis_obj)
        node_url = ConsistencyHash(hash_map).get_node(key)
        return redis.from_url(node_url)

    def extend_flask_middleware(self, app):
        """ 扩展Flask中间件
        """
        # 在init_app时，为flask app注册权限中间件
        log.info("成功注册标签系统中间件")

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
        command_func = getattr(Redis, get_func_name(command_name))
        func_params = command_func.__code__.co_varnames
        # 第二个参数 进行校验,command_name不在指定的list中
        allow_command_list = ['touch']
        if func_params[1] not in ['key', 'keys', 'name', 'names', 'src'] and command_name not in allow_command_list:
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
