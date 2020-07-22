# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/21 19:03'

Usage:

"""
import time
from functools import wraps

from redis import RedisError


def try_times(repeat_times, sleep_time):
    """
    针对 redis相关错误,重试给定次数(并且重试之间睡眠给定时间)
    :param repeat_times: 重试次数
    :param sleep_time: 间隔时间
    :return:
    """

    def wrap(f):
        """

        :param f:
        :return:

        Usage:
        >>> @try_times(2, 0.1)
        >>> def execute():
        >>>     try:
        >>>         4 / 0
        >>>     except Exception as _:
        >>>         raise
        >>> execute()
        """

        @wraps(f)
        def decorator(*args, **kwargs):
            """
            内部装饰器
            :param args:
            :param kwargs:
            :return:
            """
            for _ in range(repeat_times):
                try:
                    func_return = f(*args, **kwargs)
                    return func_return
                except RedisError as __:
                    if _ + 1 != repeat_times:
                        print(f'重试{_ + 1}次')
                        time.sleep(sleep_time)
                    else:
                        print(f'重试{_ + 1}次,然后报错')
                        raise
                except Exception as __:
                    raise

        return decorator

    return wrap


# 默认参数,不想在使用时加括号
try_times_default = try_times(3, 5)
