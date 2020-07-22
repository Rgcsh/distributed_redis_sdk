# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""


# key:虚拟节点的hash值 到 val:真实节点的映射 dict;redis数据结构为:hash
HASH_RING_MAP = 'HASH_RING_MAP'

# manager redis配置信息
# manager redis ip地址
k_redis_host = 'DIS_MANAGER_REDIS_HOST'
# manager redis 端口
k_redis_port = 'DIS_MANAGER_REDIS_PORT'
# manager redis 密码,可以不设置
k_redis_password = 'DIS_MANAGER_REDIS_PASSWORD'
# manager redis 数据库
k_redis_db = 'DIS_MANAGER_REDIS_DB'
# 缓存前缀,用来区分项目;注意只对 memoize,cached 2个函数起作用
k_prefix = 'DIS_CACHE_PREFIX'
# 缓存默认过期时间,可以不设置,默认300s
k_default_timeout = 'DIS_CACHE_DEFAULT_TIMEOUT'
