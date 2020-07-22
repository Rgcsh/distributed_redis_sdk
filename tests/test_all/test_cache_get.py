# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""

from tests import TestBase


class TestCacheGet(TestBase):

    def test_normal(self, client):
        """ 测试 正常获取
        """
        get_result = client.get(f'api/cache_get/cache_get_a')
        self.check_result(get_result, b'null')
