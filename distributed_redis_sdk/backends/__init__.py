# -*- coding: utf-8 -*-
"""
    flask_caching.backends
    ~~~~~~~~~~~~~~~~~~~~~~

    Various caching backends.

    :copyright: (c) 2018 by Peter Justin.
    :copyright: (c) 2010 by Thadeus Burgess.
    :license: BSD, see LICENSE for more details.
"""

# TODO: Rename to "redis" when python2 support is removed
from .rediscache import RedisCache

__all__ = (
    "redis",
)


def redis(app, config, args, kwargs):
    try:
        from redis import from_url as redis_from_url
    except ImportError:
        raise RuntimeError("no redis module found")

    kwargs.update(
        dict(
            host=config.get("CACHE_REDIS_HOST", "localhost"),
            port=config.get("CACHE_REDIS_PORT", 6379),
        )
    )
    password = config.get("CACHE_REDIS_PASSWORD")
    if password:
        kwargs["password"] = password

    key_prefix = config.get("CACHE_KEY_PREFIX")
    if key_prefix:
        kwargs["key_prefix"] = key_prefix

    db_number = config.get("CACHE_REDIS_DB")
    if db_number:
        kwargs["db"] = db_number

    redis_url = config.get("CACHE_REDIS_URL")
    if redis_url:
        kwargs["host"] = redis_from_url(redis_url, db=kwargs.pop("db", None))

    return RedisCache(*args, **kwargs)
