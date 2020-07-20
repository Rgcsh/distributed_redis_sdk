# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/20 09:27'

Usage:

"""
import random
from datetime import datetime

from flask import Flask, jsonify, render_template_string

from distributed_redis_sdk import DistributedRedisSdk
from examples.config import Config

app = Flask(__name__)

app.config.from_object(Config)
redis = DistributedRedisSdk(app)


#: This is an example of a cached view
@app.route("/api/now")
@redis.cached(50)
def current_time():
    return str(datetime.now())


#: This is an example of a cached function
@redis.cached(key_prefix="binary")
def random_binary():
    return [random.randrange(0, 2) for i in range(500)]


@app.route("/api/get/binary")
def get_binary():
    return jsonify({"data": random_binary()})


#: This is an example of a memoized function
@redis.memoize(60)
def _add(a, b):
    return a + b + random.randrange(0, 1000)


@redis.memoize(60)
def _sub(a, b):
    return a - b - random.randrange(0, 1000)


@app.route("/api/add/<int:a>/<int:b>")
def add(a, b):
    return str(_add(a, b))


@app.route("/api/sub/<int:a>/<int:b>")
def sub(a, b):
    return str(_sub(a, b))


@app.route("/api/cache/delete")
def delete_cache():
    # 调用 /api/add/1/2 api后
    redis.delete_memoized(_add, 1, 2)
    return "OK"


@app.route("/api/cache/clear")
def clear_cache():
    redis.clear()
    return "OK"


@app.route("/html")
@app.route("/html/<foo>")
def html(foo=None):
    if foo is not None:
        redis.set("set_foo", foo)
        result = redis.cache_set('cache_set_foo', foo)
        print(result)
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
