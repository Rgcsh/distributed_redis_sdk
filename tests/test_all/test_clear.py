# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""

from tests import TestBase


class TestClear(TestBase):

    def test_normal(self, client):
        """ 测试 正常获取
        """
        client.get('api/cache_set/clear_a/1/1')
        get_result = client.get(f'api/clear/0')
        self.check_un_equal(get_result, b'false')
