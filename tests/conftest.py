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
from flask import Flask
from flask import jsonify, render_template_string
from flask import make_response

from distributed_redis_sdk import DistributedRedisSdk

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
    result = json.dumps(result)
    resp = make_response(result)
    resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route("/api/execute/<str:key>/<str:val>")
def api_execute(key, val):
    """
    通过 基础命令 测试 execute_command 函数
    :return:
    """
    redis.set(key, val)
    return redis.get(key)


@app.route("/api/set_many/<dict:mapping>/<int:timeout>/<bool:use_prefix>")
def api_set_many(mapping, timeout, use_prefix):
    """
    测试 set_many 函数
    :return:
    """
    redis.set_many(mapping, timeout, use_prefix)


@app.route("/api/cache_set/cache_get/<str:name>/<str:value>/<int:timeout>")
def api_cache_set(name, value, timeout):
    """
    测试 cache_set,cache_get 函数
    :return:
    """
    redis.cache_set(name, value, timeout)
    return redis.cache_get(name)


@app.route("/api/has/<str:key>")
def api_has(key):
    """
    测试 has 函数
    :return:
    """
    return redis.has(key)


@app.route("/api/get_many/<list:keys>")
def api_get_many(keys):
    """
    测试 get_many 函数
    :return:
    """
    return redis.get_many(keys)


@app.route("/api/cache_delete/<str:key>")
def api_cache_delete(key):
    """
    测试 cache_delete 函数
    :return:
    """
    return redis.cache_delete(key)


@app.route("/api/delete_many/<bool:use_prefix>/<list:keys>")
def api_delete_many(use_prefix, keys):
    """
    测试 delete_many 函数
    :return:
    """
    return redis.delete_many(use_prefix, keys)


@app.route("/api/clear/<bool:use_prefix>")
def api_clear(use_prefix):
    """
    测试 clear 函数
    :return:
    """
    return redis.clear(use_prefix)


@app.route("/api/cached")
@redis.cached(50)
def api_cached():
    """
    测试 cached 装饰器 缓存50s
    :return:
    """
    return str(datetime.now())


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
    return jsonify({"data": random_binary()})


@redis.memoize(60)
def _add(a, b):
    """
    测试函数缓存 的装饰器
    :param a:
    :param b:
    :return:
    """
    return a + b + random.randrange(0, 1000)


@app.route("/api/add/<int:a>/<int:b>")
def add(a, b):
    """
    测试函数缓存 的装饰器
    :param a:
    :param b:
    :return:
    """
    return str(_add(a, b))


@app.route("/api/cache/delete")
def delete_cache():
    """
    测试 清空 函数级别缓存
    :return:
    """
    # 调用 /api/add/1/2 api后
    redis.delete_memoized(_add, 1, 2)
    return "OK"


@app.route("/html")
@app.route("/html/<foo>")
def html(foo=None):
    if foo is not None:
        redis.set("set_foo", foo)
        redis.cache_set('cache_set_foo', foo)
    return render_template_string(
        """
        <html>
            <body>
                <h1>通过redis的set命令设置缓存,存的bytes类型数据,获取数据通过 redis get命令 获取bytes类型数据: {{set_foo}}</h1>
                <h1>通过 cache_set命令设置缓存(直接缓存的对象二进制数据,获取数据时通过 cache_get命令 转为原来数据类型): {{cache_set_foo}}</h1>
            </body>
        </html>
        """, set_foo=redis.get("set_foo"), cache_set_foo=redis.cache_get("cache_set_foo")
    )


@app.route("/keymap", methods=['get', 'post'])
@pre.catch(key_map_params)
def test_keymap_handler(params):
    """ 测试key映射校验
    """
    return json_resp(params)


@pytest.fixture
def client():
    """ 构建测试用例
    """
    app.config["TESTING"] = True
    return app.test_client()
