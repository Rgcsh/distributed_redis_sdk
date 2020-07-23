# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/20 09:27'

Usage:
使用示例
此示例都是 GET请求
"""
import json
import random
from datetime import datetime

from flask import Flask, request, make_response, render_template_string

from distributed_redis_sdk import DistributedRedisSdk, byte2str
from examples.config import Config

app = Flask(__name__)

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
    return json_resp(redis.get(key))


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


if __name__ == "__main__":
    app.run()
