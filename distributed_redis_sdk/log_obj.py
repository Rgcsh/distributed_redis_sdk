# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""

from __future__ import absolute_import

import logging
import sys


def has_level_handler(logger):
    """Check if there is a handler in the logging chain that will handle the
    given logger's :meth:`effective level <~logging.Logger.getEffectiveLevel>`.
    """
    level = logger.getEffectiveLevel()
    current = logger

    while current:
        if any(handler.level <= level for handler in current.handlers):
            return True

        if not current.propagate:
            break

        current = current.parent

    return False


default_handler = logging.StreamHandler(sys.stdout)
default_handler.setFormatter(logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s(%(filename)s:%(lineno)s) | %(message)s'
))


def create_logger():
    """ Get logger and configure it if needed
    """
    logger = logging.getLogger("DistributedRedisSdk")
    logger.setLevel(logging.INFO)

    if not has_level_handler(logger):
        logger.addHandler(default_handler)

    return logger


log = create_logger()

if __name__ == '__main__':
    log.info('dffd')
