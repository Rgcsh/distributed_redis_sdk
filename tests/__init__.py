# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""


class TestBase:

    @classmethod
    def check_result(cls, resp, data):
        """
        结果校验
        :param resp:
        :param data:
        :return:
        """
        print('返回值:', resp.data)
        assert resp.data == data

    @classmethod
    def check_un_equal(cls, resp, data):
        """
        结果校验
        :param resp:
        :param data:
        :return:
        """
        print('返回值:', resp.data)
        assert resp.data != data
