# -*- coding: utf-8 -*-
# (C) Rgc, 2020
# All rights reserved
# @Author: 'Rgc <2020956572@qq.com>'
"""
提供根据key获取分布式redis节点 对象的功能
"""
import base64
import functools
import hashlib
import inspect
from collections import OrderedDict

import redis
from flask import request, url_for
from redis import Redis, ConnectionPool

from .exception import InvalidConfigException
from .log_obj import log
from .utils import iteritems_wrapper, memoize_make_version_hash, memvname, function_namespace, get_arg_names, get_id, \
    wants_args, get_arg_default, dump_object, load_object, normalize_timeout
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
        self.key_prefix = k_prefix or ""
        self.default_timeout = k_default_timeout or 300

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
        self.key_prefix = config.get(k_prefix)
        self.default_timeout = config.get(k_default_timeout)  # 缓存默认过期时间

        self.manager_redis_obj = Redis(self.k_redis_host, self.k_redis_port, self.k_redis_db, self.k_redis_password)

        # 检查redis节点集群是否有 节点
        if not get_hash_ring_map(self.manager_redis_obj):
            raise Exception('redis节点集群 没有节点,请添加!')

        self.app = app

        # 扩展原始Flask功能
        self.extend_flask_middleware()

        app.extensions["distributed_redis_sdk"] = self

    def extend_flask_middleware(self):
        """ 扩展Flask中间件
        """
        # 在init_app时，为flask app注册权限中间件
        log.info("成功注册 分布式缓存 中间件")

    def get_redis_node_obj(self, key):
        """
        通过key生成hashkey,获取对应 节点的redis obj
        :param key:
        :return:
        """
        hash_map = get_hash_ring_map(self.manager_redis_obj)
        node_url = ConsistencyHash(hash_map).get_node(key)
        return redis.from_url(node_url)

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

    # -------通过装饰器 缓存函数 部分 start---------

    def _get_prefix(self):
        """
        获取缓存前缀
        :return:
        """
        return (
            self.key_prefix
            if isinstance(self.key_prefix, str)
            else self.key_prefix()
        )

    def set_many(self, mapping, timeout=None):
        # Use transaction=False to batch without calling redis MULTI
        # which is not supported by twemproxy

        result = None
        for key, value in iteritems_wrapper(mapping):
            new_key = self._get_prefix() + key
            result = self.cache_set(new_key, value, timeout)

        return result

    def cache_set(self, name, value, timeout=None):
        """
        cache_set
        :param name:
        :param value:
        :param timeout:
        :return:
        """
        dump = dump_object(value)
        cache = self.get_redis_node_obj(name)
        timeout = normalize_timeout(timeout, self.default_timeout)

        if timeout == -1:
            result = cache.set(name=name, value=dump)
        else:
            result = cache.setex(name=name, time=timeout, value=dump)
        return result

    def get_many(self, *keys):
        if self.key_prefix:
            keys = [self._get_prefix() + key for key in keys]

        result_list = []
        for key in keys:
            cache = self.get_redis_node_obj(key)
            cache_result = cache.get(key)
            result_list.append(load_object(cache_result))
        return result_list

    def delete_many(self, *keys):
        if not keys:
            return
        if self.key_prefix:
            keys = [self._get_prefix() + key for key in keys]
        result = None
        for key in keys:
            cache = self.get_redis_node_obj(key)
            result = cache.delete(key)
        return result

    def cached(
            self,
            timeout=None,
            key_prefix="view/%s",
            unless=None,
            forced_update=None,
            response_filter=None,
            query_string=False,
            hash_method=hashlib.md5,
            cache_none=False,
    ):
        """Decorator. Use this to cache a function. By default the cache key
        is `view/request.path`. You are able to use this decorator with any
        function by changing the `key_prefix`. If the token `%s` is located
        within the `key_prefix` then it will replace that with `request.path`

        Example::

            # An example view function
            @cache.cached(timeout=50)
            def big_foo():
                return big_bar_calc()

            # An example misc function to cache.
            @cache.cached(key_prefix='MyCachedList')
            def get_list():
                return [random.randrange(0, 1) for i in range(50000)]

            my_list = get_list()

        .. note::

            You MUST have a request context to actually called any functions
            that are cached.

        .. versionadded:: 0.4
            The returned decorated function now has three function attributes
            assigned to it. These attributes are readable/writable.

                **uncached**
                    The original undecorated function

                **cache_timeout**
                    The cache timeout value for this function. For a
                    custom value to take affect, this must be set before the
                    function is called.

                **make_cache_key**
                    A function used in generating the cache_key used.

        :param timeout: Default None. If set to an integer, will cache for that
                        amount of time. Unit of time is in seconds.

        :param key_prefix: Default 'view/%(request.path)s'. Beginning key to .
                           use for the cache key. `request.path` will be the
                           actual request path, or in cases where the
                           `make_cache_key`-function is called from other
                           views it will be the expected URL for the view
                           as generated by Flask's `url_for()`.

                           .. versionadded:: 0.3.4
                               Can optionally be a callable which takes
                               no arguments but returns a string that will
                               be used as the cache_key.

        :param unless: Default None. Cache will *always* execute the caching
                       facilities unless this callable is true.
                       This will bypass the caching entirely.

        :param forced_update: Default None. If this callable is true,
                              cache value will be updated regardless cache
                              is expired or not. Useful for background
                              renewal of cached functions.

        :param response_filter: Default None. If not None, the callable is
                                invoked after the cached funtion evaluation,
                                and is given one arguement, the response
                                content. If the callable returns False, the
                                content will not be cached. Useful to prevent
                                caching of code 500 responses.

        :param query_string: Default False. When True, the cache key
                             used will be the result of hashing the
                             ordered query string parameters. This
                             avoids creating different caches for
                             the same query just because the parameters
                             were passed in a different order. See
                             _make_cache_key_query_string() for more
                             details.

        :param hash_method: Default hashlib.md5. The hash method used to
                            generate the keys for cached results.
        :param cache_none: Default False. If set to True, add a key exists
                           check when cache.get returns None. This will likely
                           lead to wrongly returned None values in concurrent
                           situations and is not recommended to use.

        """

        def decorator(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                #: Bypass the cache entirely.
                if self._bypass_cache(unless, f, *args, **kwargs):
                    return f(*args, **kwargs)

                try:
                    if query_string:
                        cache_key = _make_cache_key_query_string()
                    else:
                        cache_key = _make_cache_key(
                            args, kwargs, use_request=True
                        )

                    cache = self.get_redis_node_obj(cache_key)
                    if (
                            callable(forced_update)
                            and (
                            forced_update(*args, **kwargs)
                            if wants_args(forced_update)
                            else forced_update()
                    )
                            is True
                    ):
                        rv = None
                        found = False
                    else:
                        rv = cache.get(cache_key)
                        found = True

                        # If the value returned by cache.get() is None, it
                        # might be because the key is not found in the cache
                        # or because the cached value is actually None
                        if rv is None:
                            # If we're sure we don't need to cache None values
                            # (cache_none=False), don't bother checking for
                            # key existence, as it can lead to false positives
                            # if a concurrent call already cached the
                            # key between steps. This would cause us to
                            # return None when we shouldn't
                            if not cache_none:
                                found = False
                            else:
                                found = cache.has(cache_key)
                except Exception:
                    if self.app.debug:
                        raise
                    log.exception("Exception possibly due to cache backend.")
                    return f(*args, **kwargs)

                if not found:
                    rv = f(*args, **kwargs)

                    if response_filter is None or response_filter(rv):
                        try:
                            self.cache_set(cache_key, rv, decorated_function.cache_timeout)
                        except Exception:
                            if self.app.debug:
                                raise
                            log.exception(
                                "Exception possibly due to cache backend."
                            )
                return rv

            def make_cache_key(*args, **kwargs):
                # Convert non-keyword arguments (which is the way
                # `make_cache_key` expects them) to keyword arguments
                # (the way `url_for` expects them)
                argspec_args = inspect.getfullargspec(f).args

                for arg_name, arg in zip(argspec_args, args):
                    kwargs[arg_name] = arg

                return _make_cache_key(args, kwargs, use_request=False)

            def _make_cache_key_query_string():
                """Create consistent keys for query string arguments.

                Produces the same cache key regardless of argument order, e.g.,
                both `?limit=10&offset=20` and `?offset=20&limit=10` will
                always produce the same exact cache key.
                """

                # Create a tuple of (key, value) pairs, where the key is the
                # argument name and the value is its respective value. Order
                # this tuple by key. Doing this ensures the cache key created
                # is always the same for query string args whose keys/values
                # are the same, regardless of the order in which they are
                # provided.
                args_as_sorted_tuple = tuple(
                    sorted((pair for pair in request.args.items(multi=True)))
                )
                # ... now hash the sorted (key, value) tuple so it can be
                # used as a key for cache. Turn them into bytes so that the
                # hash function will accept them
                args_as_bytes = str(args_as_sorted_tuple).encode()
                hashed_args = str(hash_method(args_as_bytes).hexdigest())
                cache_key = request.path + hashed_args
                return cache_key

            def _make_cache_key(args, kwargs, use_request):
                if callable(key_prefix):
                    cache_key = key_prefix()
                elif "%s" in key_prefix:
                    if use_request:
                        cache_key = key_prefix % request.path
                    else:
                        cache_key = key_prefix % url_for(f.__name__, **kwargs)
                else:
                    cache_key = key_prefix

                return cache_key

            decorated_function.uncached = f
            decorated_function.cache_timeout = timeout
            decorated_function.make_cache_key = make_cache_key

            return decorated_function

        return decorator

    def _memoize_version(
            self,
            f,
            args=None,
            kwargs=None,
            reset=False,
            delete=False,
            timeout=None,
            forced_update=False,
    ):
        """Updates the hash version associated with a memoized function or
        method.
        """
        fname, instance_fname = function_namespace(f, args=args)
        version_key = memvname(fname)
        fetch_keys = [version_key]

        if instance_fname:
            instance_version_key = memvname(instance_fname)
            fetch_keys.append(instance_version_key)

        # Only delete the per-instance version key or per-function version
        # key but not both.
        if delete:
            key = fetch_keys[-1]
            cache = self.get_redis_node_obj(key)
            cache.delete(key)
            return fname, None

        version_data_list = list(self.get_many(*fetch_keys))
        dirty = False

        if (
                callable(forced_update)
                and (
                forced_update(*(args or ()), **(kwargs or {}))
                if wants_args(forced_update)
                else forced_update()
        )
                is True
        ):
            # Mark key as dirty to update its TTL
            dirty = True

        if version_data_list[0] is None:
            version_data_list[0] = memoize_make_version_hash()
            dirty = True

        if instance_fname and version_data_list[1] is None:
            version_data_list[1] = memoize_make_version_hash()
            dirty = True

        # Only reset the per-instance version or the per-function version
        # but not both.
        if reset:
            fetch_keys = fetch_keys[-1:]
            version_data_list = [memoize_make_version_hash()]
            dirty = True

        if dirty:
            self.set_many(
                dict(zip(fetch_keys, version_data_list)), timeout=timeout
            )

        return fname, "".join(version_data_list)

    def _memoize_make_cache_key(
            self,
            make_name=None,
            timeout=None,
            forced_update=False,
            hash_method=hashlib.md5,
    ):
        """Function used to create the cache_key for memoized functions."""

        def make_cache_key(f, *args, **kwargs):
            _timeout = getattr(timeout, "cache_timeout", timeout)
            fname, version_data = self._memoize_version(
                f, args=args, timeout=_timeout, forced_update=forced_update
            )

            #: this should have to be after version_data, so that it
            #: does not break the delete_memoized functionality.
            altfname = make_name(fname) if callable(make_name) else fname

            if callable(f):
                keyargs, keykwargs = self._memoize_kwargs_to_args(
                    f, *args, **kwargs
                )
            else:
                keyargs, keykwargs = args, kwargs

            updated = u"{0}{1}{2}".format(altfname, keyargs, keykwargs)

            cache_key = hash_method()
            cache_key.update(updated.encode("utf-8"))
            cache_key = base64.b64encode(cache_key.digest())[:16]
            cache_key = cache_key.decode("utf-8")
            cache_key += version_data

            return cache_key

        return make_cache_key

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

    def memoize(
            self,
            timeout=None,
            make_name=None,
            unless=None,
            forced_update=None,
            response_filter=None,
            hash_method=hashlib.md5,
            cache_none=False,
    ):
        """Use this to cache the result of a function, taking its arguments
        into account in the cache key.

        Information on
        `Memoization <http://en.wikipedia.org/wiki/Memoization>`_.

        Example::

            @cache.memoize(timeout=50)
            def big_foo(a, b):
                return a + b + random.randrange(0, 1000)

        .. code-block:: pycon

            >>> big_foo(5, 2)
            753
            >>> big_foo(5, 3)
            234
            >>> big_foo(5, 2)
            753

        .. versionadded:: 0.4
            The returned decorated function now has three function attributes
            assigned to it.

                **uncached**
                    The original undecorated function. readable only

                **cache_timeout**
                    The cache timeout value for this function.
                    For a custom value to take affect, this must be
                    set before the function is called.

                    readable and writable

                **make_cache_key**
                    A function used in generating the cache_key used.

                    readable and writable


        :param timeout: Default None. If set to an integer, will cache for that
                        amount of time. Unit of time is in seconds.
        :param make_name: Default None. If set this is a function that accepts
                          a single argument, the function name, and returns a
                          new string to be used as the function name.
                          If not set then the function name is used.
        :param unless: Default None. Cache will *always* execute the caching
                       facilities unless this callable is true.
                       This will bypass the caching entirely.
        :param forced_update: Default None. If this callable is true,
                              cache value will be updated regardless cache
                              is expired or not. Useful for background
                              renewal of cached functions.
        :param response_filter: Default None. If not None, the callable is
                                invoked after the cached funtion evaluation,
                                and is given one arguement, the response
                                content. If the callable returns False, the
                                content will not be cached. Useful to prevent
                                caching of code 500 responses.
        :param hash_method: Default hashlib.md5. The hash method used to
                            generate the keys for cached results.
        :param cache_none: Default False. If set to True, add a key exists
                           check when cache.get returns None. This will likely
                           lead to wrongly returned None values in concurrent
                           situations and is not recommended to use.

        .. versionadded:: 0.5
            params ``make_name``, ``unless``
        """

        def memoize(f):
            @functools.wraps(f)
            def decorated_function(*args, **kwargs):
                #: bypass cache
                if self._bypass_cache(unless, f, *args, **kwargs):
                    return f(*args, **kwargs)

                try:
                    cache_key = decorated_function.make_cache_key(
                        f, *args, **kwargs
                    )
                    cache_key = self._get_prefix() + cache_key
                    # 根据缓存key获取redis节点对象
                    cache = self.get_redis_node_obj(cache_key)
                    if (
                            callable(forced_update)
                            and (
                            forced_update(*args, **kwargs)
                            if wants_args(forced_update)
                            else forced_update()
                    )
                            is True
                    ):
                        rv = None
                        found = False
                    else:
                        rv = cache.get(cache_key)
                        found = True

                        # If the value returned by cache.get() is None, it
                        # might be because the key is not found in the cache
                        # or because the cached value is actually None
                        if rv is None:
                            # If we're sure we don't need to cache None values
                            # (cache_none=False), don't bother checking for
                            # key existence, as it can lead to false positives
                            # if a concurrent call already cached the
                            # key between steps. This would cause us to
                            # return None when we shouldn't
                            if not cache_none:
                                found = False
                            else:
                                found = cache.has(cache_key)
                except Exception:
                    if self.app.debug:
                        raise
                    log.exception("Exception possibly due to cache backend.")
                    return f(*args, **kwargs)

                if not found:
                    rv = f(*args, **kwargs)

                    if response_filter is None or response_filter(rv):
                        try:
                            result = self.cache_set(cache_key, rv, decorated_function.cache_timeout)
                        except Exception:
                            if self.app.debug:
                                raise
                            log.exception(
                                "Exception possibly due to cache backend."
                            )
                return rv

            decorated_function.uncached = f
            decorated_function.cache_timeout = timeout
            decorated_function.make_cache_key = self._memoize_make_cache_key(
                make_name=make_name,
                timeout=decorated_function,
                forced_update=forced_update,
                hash_method=hash_method,
            )
            decorated_function.delete_memoized = lambda: self.delete_memoized(f)

            return decorated_function

        return memoize

    def delete_memoized(self, f, *args, **kwargs):
        """Deletes the specified functions caches, based by given parameters.
        If parameters are given, only the functions that were memoized
        with them will be erased. Otherwise all versions of the caches
        will be forgotten.

        Example::

            @cache.memoize(50)
            def random_func():
                return random.randrange(1, 50)

            @cache.memoize()
            def param_func(a, b):
                return a+b+random.randrange(1, 50)

        .. code-block:: pycon

            >>> random_func()
            43
            >>> random_func()
            43
            >>> cache.delete_memoized(random_func)
            >>> random_func()
            16
            >>> param_func(1, 2)
            32
            >>> param_func(1, 2)
            32
            >>> param_func(2, 2)
            47
            >>> cache.delete_memoized(param_func, 1, 2)
            >>> param_func(1, 2)
            13
            >>> param_func(2, 2)
            47

        Delete memoized is also smart about instance methods vs class methods.

        When passing a instancemethod, it will only clear the cache related
        to that instance of that object. (object uniqueness can be overridden
        by defining the __repr__ method, such as user id).

        When passing a classmethod, it will clear all caches related across
        all instances of that class.

        Example::

            class Adder(object):
                @cache.memoize()
                def add(self, b):
                    return b + random.random()

        .. code-block:: pycon

            >>> adder1 = Adder()
            >>> adder2 = Adder()
            >>> adder1.add(3)
            3.23214234
            >>> adder2.add(3)
            3.60898509
            >>> cache.delete_memoized(adder1.add)
            >>> adder1.add(3)
            3.01348673
            >>> adder2.add(3)
            3.60898509
            >>> cache.delete_memoized(Adder.add)
            >>> adder1.add(3)
            3.53235667
            >>> adder2.add(3)
            3.72341788

        :param fname: The memoized function.
        :param \*args: A list of positional parameters used with
                       memoized function.
        :param \**kwargs: A dict of named parameters used with
                          memoized function.

        .. note::

            Flask-Caching uses inspect to order kwargs into positional args when
            the function is memoized. If you pass a function reference into
            ``fname``, Flask-Caching will be able to place the args/kwargs in
            the proper order, and delete the positional cache.

            However, if ``delete_memoized`` is just called with the name of the
            function, be sure to pass in potential arguments in the same order
            as defined in your function as args only, otherwise Flask-Caching
            will not be able to compute the same cache key and delete all
            memoized versions of it.

        .. note::

            Flask-Caching maintains an internal random version hash for
            the function. Using delete_memoized will only swap out
            the version hash, causing the memoize function to recompute
            results and put them into another key.

            This leaves any computed caches for this memoized function within
            the caching backend.

            It is recommended to use a very high timeout with memoize if using
            this function, so that when the version hash is swapped, the old
            cached results would eventually be reclaimed by the caching
            backend.
        """
        if not callable(f):
            raise TypeError(
                "Deleting messages by relative name is not supported, please "
                "use a function reference."
            )

        if not (args or kwargs):
            self._memoize_version(f, reset=True)
        else:
            cache_key = f.make_cache_key(f.uncached, *args, **kwargs)
            cache = self.get_redis_node_obj(cache_key)
            cache.delete(cache_key)

    def delete_memoized_verhash(self, f, *args):
        """Delete the version hash associated with the function.

        .. warning::

            Performing this operation could leave keys behind that have
            been created with this version hash. It is up to the application
            to make sure that all keys that may have been created with this
            version hash at least have timeouts so they will not sit orphaned
            in the cache backend.
        """
        if not callable(f):
            raise TypeError(
                "Deleting messages by relative name is not supported, please"
                "use a function reference."
            )

        self._memoize_version(f, delete=True)
