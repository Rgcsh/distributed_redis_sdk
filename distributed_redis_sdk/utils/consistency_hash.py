# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""

from zlib import crc32


class ConsistencyHash(object):
    """一致性hash类"""
    def __init__(self, ring: dict):
        """

        :param ring: key:虚拟节点的hash值 val:真实节点
        """
        self.ring = ring or {}
        self.sorted_keys = list(ring.keys())  # 排序之后的虚拟节点的hash值list
        self.sorted_keys.sort()

    def get_node(self, key):
        """
        获取环形hash对应的node
        :param key:
        :return:
        """
        bkey = bytes(key, encoding="utf8")
        keyhash = abs(crc32(bkey))
        i = 0
        for nodehash in self.sorted_keys:
            nodehash = int(nodehash)
            i += 1
            if keyhash < nodehash:
                return self.ring[str(nodehash)]
            else:
                continue
        if i == len(self.sorted_keys):
            return self.ring[self.sorted_keys[0]]
