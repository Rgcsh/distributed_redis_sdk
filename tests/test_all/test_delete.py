# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""
import time

from tests import TestBase


class TestMemoizeDelete(TestBase):

    def test_normal(self, client):
        """ 测试 正常获取
        """
        client.get('api/memoize/1/2')
        get_result = client.get('api/memoize/delete')
        self.check_result(get_result, b'1')
