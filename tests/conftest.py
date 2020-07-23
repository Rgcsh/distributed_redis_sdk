# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""
import json
import random
from datetime import datetime

import pytest
from flask import Flask, make_response, request

from distributed_redis_sdk import DistributedRedisSdk, byte2str

app = Flask(__name__)


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


app.config.from_object(Config)
redis = DistributedRedisSdk(app)


def json_resp(result):
    if isinstance(result, bytes):
        result = byte2str(result)
    result = json.dumps(result)
    resp = make_response(result)
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route("/api/execute/<string:key>/<string:val>")
def api_execute(key, val):
    """
    通过 基础命令 测试 execute_command 函数
    :return:
    """
    redis.set(key, val)
    result = redis.get(key)
    return json_resp(result)


@app.route("/api/set_many")
def api_set_many():
    """
    测试 set_many 函数
    :return:
    """
    parmas = request.values
    mapping = json.loads(parmas.get('mapping'))
    timeout = parmas.get('timeout')
    if timeout:
        timeout = int(timeout)
    use_prefix = bool(int(parmas.get('use_prefix')))

    result = redis.set_many(mapping, timeout, use_prefix)
    return json_resp(result)


@app.route("/api/get_many")
def api_get_many():
    """
    测试 get_many 函数
    :return:
    """
    keys = json.loads(request.values.get('keys'))
    use_prefix = bool(int(request.values.get('use_prefix')))
    return json_resp(redis.get_many(keys, use_prefix))


@app.route("/api/cache_set/<string:name>/<string:value>/<int:timeout>")
def api_cache_set(name, value, timeout):
    """
    测试 cache_set 函数
    :return:
    """
    result = redis.cache_set(name, value, timeout)
    return json_resp(result)


@app.route("/api/cache_get/<string:name>")
def api_cache_get(name):
    """
    测试 cache_get 函数
    :return:
    """
    result = redis.cache_get(name)
    return json_resp(result)


@app.route("/api/cache_delete/<string:key>")
def api_cache_delete(key):
    """
    测试 cache_delete 函数
    :return:
    """
    return json_resp(redis.cache_delete(key))


@app.route("/api/has/<string:key>")
def api_has(key):
    """
    测试 has 函数
    :return:
    """
    return json_resp(redis.has(key))


@app.route("/api/delete_many")
def api_delete_many():
    """
    测试 delete_many 函数
    :return:
    """
    parmas = request.values
    use_prefix = bool(int(parmas.get('use_prefix')))
    keys = json.loads(parmas.get('keys'))

    return json_resp(redis.delete_many(keys, use_prefix))


@app.route("/api/clear/<int:use_prefix>")
def api_clear(use_prefix):
    """
    测试 clear 函数
    :return:
    """
    use_prefix = bool(use_prefix)
    return json_resp(redis.clear(use_prefix))


@app.route("/api/cached")
@redis.cached(1)
def api_cached():
    """
    测试 cached 装饰器 缓存1s
    :return:
    """
    return json_resp(str(datetime.now()))


#: This is an example of a cached function
@redis.cached(key_prefix="binary")
def random_binary():
    """
    测试 cached 缓存视图的装饰器 设置 key
    :return:
    """
    return [random.randrange(0, 2) for i in range(500)]


@app.route("/api/get/binary")
def get_binary():
    """
    测试 cached 缓存视图的装饰器 设置 key
    :return:
    """
    return json_resp({"data": random_binary()})


@redis.memoize(1)
def _add(a, b):
    """
    测试函数缓存 的装饰器
    :param a:
    :param b:
    :return:
    """
    return a + b + random.randrange(0, 1000)


@app.route("/api/memoize/<int:a>/<int:b>")
def memoize(a, b):
    """
    测试函数缓存 的装饰器
    :param a:
    :param b:
    :return:
    """
    return json_resp(str(_add(a, b)))


@app.route("/api/memoize/delete")
def delete_cache():
    """
    测试 清空 函数级别缓存
    :return:
    """
    # 调用 /api/add/1/2 api后
    result = redis.delete_memoized(_add, 1, 2)
    return json_resp(result)


@pytest.fixture
def client():
    """ 构建测试用例
    """
    app.config["TESTING"] = True
    return app.test_client()


def check_result(resp, data):
    assert resp.data == data
