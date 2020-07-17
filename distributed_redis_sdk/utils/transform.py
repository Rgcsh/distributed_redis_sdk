# -*- coding: utf-8 -*-
"""

All rights reserved
create time '2020/7/6 09:09'

Usage:

"""


def str2byte(_str):
    """
    str to bytes
    :param _str:
    :return:
    """
    return bytes(_str, encoding='utf8')


def byte2str(_bytes):
    """
    bytes to str
    :param _bytes:
    :return:
    """
    return str(_bytes, encoding="utf-8")
