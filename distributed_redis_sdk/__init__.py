# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:
提供根据key获取分布式redis节点 对象的功能
"""

import base64
import functools
import hashlib
import inspect

from flask import request, url_for
from redis import Redis

from .base_redis import BaseRedis
from .exception import InvalidConfigException
from .log_obj import log
from .utils import iteritems_wrapper, memoize_make_version_hash, memvname, function_namespace, get_arg_names, get_id, \
    wants_args, get_arg_default, dump_object, load_object, normalize_timeout, try_times, try_times_default, byte2str
from .utils.consistency_hash import ConsistencyHash
from .utils.constant import *
from .utils.redis_action import get_redis_obj, get_hash_ring_map, get_func_name


class DistributedRedisSdk(BaseRedis):
    """分布式redis客户端类"""

    def __init__(self, app=None, config=None):
        """
        对象初始化
        :param app:
        :param config:
        """
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
        self.default_timeout = k_default_timeout

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
        if not self.key_prefix or not isinstance(self.key_prefix, str):
            raise Exception('分布式缓存前缀配置DIS_CACHE_PREFIX必须设置,并且不同项目不能重复')
        self.default_timeout = config.get(k_default_timeout) or 300  # 缓存默认过期时间

        self.manager_redis_obj = Redis(self.k_redis_host, self.k_redis_port, self.k_redis_db, self.k_redis_password)

        # 检查redis节点集群是否有 节点
        if not get_hash_ring_map(self.manager_redis_obj):
            raise Exception('redis节点集群 没有节点,请添加!')

        self.app = app

        # 扩展原始Flask功能
        self.extend_flask_middleware()

        app.extensions["distributed_redis_sdk"] = self

    @classmethod
    def extend_flask_middleware(cls):
        """ 扩展Flask中间件
        """
        # 在init_app时，为flask app注册权限中间件
        log.info("成功注册 分布式缓存 中间件")

    # -------通过装饰器 缓存函数 部分 start---------
    def set_many(self, mapping: dict, timeout=None, use_prefix=False):
        """
        设置多个值
        :param mapping:
        :param timeout:
        :param use_prefix: 默认不在key添加 前缀
        :return:
        """
        if not isinstance(mapping, dict):
            raise TypeError

        result = None
        for key, value in iteritems_wrapper(mapping):
            key = self._use_prefix(key, use_prefix)
            result = self.cache_set(key, value, timeout)

        return result

    def get_many(self, keys: list, use_prefix=False):
        """
        获取多条数据
        :param use_prefix:默认不使用添加key的前缀
        :param keys:
        :return:

        Usage:
        >>>self.get_many(['a','b']) # 默认 use_prefix=False
        >>>self.get_many(['a','b'],True)

        """
        if not isinstance(keys, list):
            raise TypeError
        keys = self._use_prefix(keys, use_prefix)

        result_list = []
        for key in keys:
            cache_result = self.cache_get(key)
            result_list.append(cache_result)
        return result_list

    @try_times_default
    def cache_set(self, name: str or int, value, timeout=None, use_prefix=False):
        """
        设置缓存,直接存储value的二进制数据(不会转为bytes),timeout值不填写,则过期时间为 设置的过期时间或者300s
        :param name:
        :param value:
        :param timeout:值为<=0时,永久缓存;值为None时,缓存设置的过期时间或300s;值为其他>0时,则缓存给定的时间
        :param use_prefix:是否添加前缀,默认不添加

        :return:

        Usage:
        >>> self.cache_set(1,'test') # 缓存 设置的过期时间或者300s
        >>> self.cache_set(1,'test',-1) # 缓存永久
        >>> self.cache_set(1,'test',0) # 缓存永久
        >>> self.cache_set(1,'test',-2) # 缓存永久
        >>> self.cache_set(1,'test',10) # 缓存10s
        """
        if timeout and not isinstance(timeout, int):
            raise TypeError
        dump = dump_object(value)
        name = self._use_prefix(name, use_prefix)
        cache = self.get_redis_node_obj(name)
        timeout = normalize_timeout(timeout, self.default_timeout)

        if timeout == -1:
            result = cache.set(name=name, value=dump)
        else:
            result = cache.setex(name=name, time=timeout, value=dump)
        return result

    @try_times_default
    def cache_get(self, key, cache_obj=None, use_prefix=False):
        """
        获取缓存的二进制数据,并还原为原来的对象
        :param key:
        :param cache_obj:缓存对象,不传此值时,则 通过key 生成缓存对象
        :param use_prefix:默认不使用添加key的前缀
        :return:
        """
        key = self._use_prefix(key, use_prefix)
        cache_obj = self._cache_obj(key, cache_obj)
        return load_object(cache_obj.get(key))

    def cache_delete(self, key, use_prefix=False):
        """
        删除数据
        :param key:
        :param use_prefix:是否添加前缀,默认不添加
        :return:
        """
        key = self._use_prefix(key, use_prefix)
        cache = self.get_redis_node_obj(key)
        return cache.delete(key)

    @try_times_default
    def has(self, key, cache_obj=None, use_prefix=False):
        """
        判断是否存在此key
        :param key: 已经添加过 key_prefix前缀的 key
        :param cache_obj:
        :param use_prefix:是否添加前缀,默认不添加
        :return:
        """
        key = self._use_prefix(key, use_prefix)
        cache_obj = self._cache_obj(key, cache_obj)
        return cache_obj.exists(key)

    def delete_many(self, keys: list, use_prefix=False):
        """
        删除多条数据
        :param use_prefix:默认不使用添加key的前缀
        :param keys:
        :return:

        Usage:
        >>>self.delete_many(['a','b']) # 默认 use_prefix=False
        >>>self.delete_many(['a','b'],Ture)

        """
        result = None
        if not isinstance(keys, list):
            raise TypeError
        keys = self._use_prefix(keys, use_prefix)

        for key in keys:
            result = self.cache_delete(key)
        return result

    def clear(self, use_prefix=False):
        """
        按照条件 清空 所有节点给定db的 数据

        警告:此方法谨慎使用!!!
        :param use_prefix:默认删除所有的key,值为True时删除给定前缀的所有数据
        :return:
        """
        status = False
        node_url_list = self._get_all_node_url()
        for node_url in node_url_list:
            cache = self._redis_from_url(node_url)
            if use_prefix:
                keys = cache.keys(self.key_prefix + "*")
            else:
                keys = cache.keys("*")

            if keys:
                status = cache.delete(*keys)
        return status

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
        视图级别的缓存,不能用在 内部函数中,因为缓存名 根据 请求路径生成的
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
                    cache_key = self._use_prefix(cache_key, True)
                    cache = self.get_redis_node_obj(cache_key)
                    if (callable(forced_update) and
                            (forced_update(*args, **kwargs) if wants_args(forced_update) else forced_update())
                            is True):
                        rv = None
                        found = False
                    else:
                        rv = self.cache_get(cache_key, cache)
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
                                found = self.has(cache_key, cache)
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

            def _make_cache_key(args, kwargs, use_request):  # pylint:disable=unused-argument
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
            self.cache_delete(key)
            return fname, None

        version_data_list = list(self.get_many(fetch_keys, True))
        dirty = False

        if (callable(forced_update) and
                (forced_update(*(args or ()), **(kwargs or {})) if wants_args(forced_update) else forced_update()) is True):
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
            self.set_many(dict(zip(fetch_keys, version_data_list)), timeout=timeout, use_prefix=True)

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
        函数级别的缓存
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
                    cache_key = self._use_prefix(cache_key, True)
                    # 根据缓存key获取redis节点对象
                    cache = self.get_redis_node_obj(cache_key)
                    if (callable(forced_update) and
                            (forced_update(*args, **kwargs) if wants_args(forced_update) else forced_update()) is True):
                        rv = None
                        found = False
                    else:
                        rv = self.cache_get(cache_key, cache)
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
                                found = self.has(cache_key, cache)
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
        :param *args: A list of positional parameters used with
                       memoized function.
        :param **kwargs: A dict of named parameters used with
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
            return self._memoize_version(f, reset=True)
        else:
            cache_key = f.make_cache_key(f.uncached, *args, **kwargs)
            return self.cache_delete(cache_key, True)

    def delete_memoized_verhash(self, f, *args):  # pylint:disable=unused-argument
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
