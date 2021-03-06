# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""

from tests import TestBase


class TestHas(TestBase):

    def test_normal(self, client):
        """ 测试 正常获取
        """
        get_result = client.get(f'api/has/has_a')
        self.check_result(get_result, b'0')

    def test_have_data(self, client):
        """ 测试 有数据的情况
        """
        client.get('api/cache_set/has_b/1/1/0/0')
        get_result = client.get(f'api/has/has_b')
        self.check_result(get_result, b'1')
