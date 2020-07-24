# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""
import time

from tests import TestBase


class TestSetMany(TestBase):

    def test_normal(self, client):
        """ 测试 添加超时时间,prefix
        """
        resp = client.get('api/set_many?mapping={"set_many_a":1}&timeout=1&use_prefix=1')
        assert resp.data == b'true'
        get_result = client.get(f'api/get_many?keys=["set_many_a"]&use_prefix=1')
        self.check_result(get_result, b'[1]')
        # 睡眠后再获取
        time.sleep(1.5)
        get_result = client.get(f'api/get_many?keys=["set_many_a"]&use_prefix=1')
        self.check_result(get_result, b'[null]')

    def test_not_use_prefix(self, client):
        """
        测试不 添加 prefix
        :param client:
        :return:
        """
        client.get('api/set_many?mapping={"set_many_b":1}&timeout=1&use_prefix=0')
        get_result = client.get(f'api/get_many?keys=["set_many_b"]&use_prefix=0')
        self.check_result(get_result, b'[1]')

    def test_time_out(self, client):
        """
        测试超时参数
        :param client:
        :return:
        """
        client.get('api/set_many?mapping={"set_many_c":1}&timeout=0&use_prefix=0')
        time.sleep(1)
        get_result = client.get(f'api/get_many?keys=["set_many_c"]&use_prefix=0')
        self.check_result(get_result, b'[1]')

    def test_params(self, client):
        """
        测试参数 格式错误
        :param client:
        :return:
        """
        try:
            client.get('api/set_many?mapping=1&timeout=0&use_prefix=0')
            assert False
        except Exception as _:
            assert True
