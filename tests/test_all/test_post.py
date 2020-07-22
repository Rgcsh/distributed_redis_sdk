# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""


class TestPost:

    def test_post_filter(self, client):
        """ 测试POST提交参数
        """
        resp = client.post("/type", data={
            "int": "3",
            "str": 2,
        })

        assert resp.json == {"int": 3, "str": "2"}
