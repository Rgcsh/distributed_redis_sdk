# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""
import time

from tests import TestBase


class TestCached(TestBase):

    def test_normal(self, client):
        """ 测试 正常获取
        """
        get_result = client.get('api/cached')
        self.check_result(get_result, client.get('api/cached').data)
        # 睡眠1.3s后 缓存消失
        time.sleep(1.3)
        self.check_un_equal(get_result, client.get('api/cached').data)
