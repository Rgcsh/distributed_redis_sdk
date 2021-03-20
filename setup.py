# -*- coding: utf-8 -*-
"""
(C) Rgc <2020956572@qq.com>
All rights reserved
create time '2020/7/22 14:31'

Usage:

"""

import os
from codecs import open

from setuptools import setup

here = os.path.abspath(os.path.dirname(__file__))

packages = ['distributed_redis_sdk']
file_data = [
]

package_data = {
}

requires = [
    'redis==3.5.3',
    'click==7.1.2',
    'Flask==1.1.2',
    'itsdangerous==1.1.0',
    'Jinja2==2.11.3',
    'MarkupSafe==1.1.1',
    'redis==3.5.3',
    'Werkzeug==1.0.1',
]

about = {}
with open(os.path.join(here, 'distributed_redis_sdk', '__version__.py'), 'r', 'utf-8') as f:
    exec(f.read(), about)

with open('README.md', 'r', 'utf-8') as f:
    readme = f.read()

setup(
    name=about['__title__'],
    version=about['__version__'],
    description=about['__description__'],
    long_description=readme,
    author=about['__author__'],
    author_email=about['__author_email__'],
    url=about['__url__'],
    packages=packages,
    data_files=file_data,
    include_package_data=True,
    package_data=package_data,
    python_requires=">=3.0, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*",
    install_requires=requires,
    zip_safe=False,
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy'
    ],
)
