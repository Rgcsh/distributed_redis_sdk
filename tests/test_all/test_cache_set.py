# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""
import time

from tests import TestBase


class TestCacheSet(TestBase):

    def test_normal(self, client):
        """ 测试 缓存1s
        """
        resp = client.get('api/cache_set/cache_set_a/1/1/0/0')
        assert resp.data == b'true'
        get_result = client.get(f'api/cache_get/cache_set_a')
        self.check_result(get_result, b'"1"')
        # 睡眠后再获取
        time.sleep(1.2)
        get_result = client.get(f'api/cache_get/cache_set_a')
        self.check_result(get_result, b'null')

    def test_all_time(self, client):
        """ 测试 缓存永久
        """
        # time_out=0
        resp = client.get('api/cache_set/cache_set_b/1/0/0/0')
        assert resp.data == b'true'
        # 睡眠后再获取
        time.sleep(0.2)
        get_result = client.get(f'api/cache_get/cache_set_b')
        self.check_result(get_result, b'"1"')

        # time_out=-1
        resp = client.get('api/cache_set/cache_set_c/1/0/0/0')
        assert resp.data == b'true'
        # 睡眠后再获取
        time.sleep(0.2)
        get_result = client.get(f'api/cache_get/cache_set_c')
        self.check_result(get_result, b'"1"')

        # time_out=-2
        resp = client.get('api/cache_set/cache_set_d/1/0/0/0')
        assert resp.data == b'true'
        # 睡眠后再获取
        time.sleep(0.2)
        get_result = client.get(f'api/cache_get/cache_set_d')
        self.check_result(get_result, b'"1"')

    def test_params(self, client):
        """
        测试参数类型
        :param client:
        :return:
        """
        resp = client.get('api/cache_set/1/1/1/1/1')
        assert resp.data == b'true'
