# -*- coding: utf-8 -*-
"""
(C) Guangcai Ren <rgc@bvrft.com>
All rights reserved
create time '2020/7/22 15:34'

Usage:

"""
from tests import TestBase


class TestExecute(TestBase):

    def test_normal(self, client):
        """ 通过 基础命令 测试 execute_command 函数
        """
        get_result = client.get('/api/execute/execute_test/1')
        self.check_result(get_result, b'"1"')
