# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""

from tests import TestBase


class TestGetMany(TestBase):

    def test_params(self, client):
        """
        测试参数 格式错误
        :param client:
        :return:
        """
        try:
            client.get('api/get_many?keys=1&use_prefix=0')
            assert False
        except Exception as _:
            assert True
