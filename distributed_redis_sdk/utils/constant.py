# -*- coding: utf-8 -*-
"""

All rights reserved
create time '2020/7/6 09:09'

Usage:

"""
# key:虚拟节点的hash值 到 val:真实节点的映射 dict;redis数据结构为:hash
HASH_RING_MAP = 'HASH_RING_MAP'

# manager redis配置信息
k_redis_host = 'REDIS_HOST'
k_redis_port = 'REDIS_PORT'
k_redis_password = 'REDIS_PASSWORD'
k_redis_db = 'REDIS_DB'
# 缓存前缀,区分项目
k_prefix = 'REDIS_PREFIX'
# 缓存默认过期时间,没传则为300s
k_default_timeout = 'REDIS_DEFAULT_TIMEOUT'
