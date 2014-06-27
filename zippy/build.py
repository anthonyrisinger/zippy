#!/usr/bin/env python

#TODO: re-link in build order

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

from os import path as pth

from waflib import Logs

from .test import test
from .install import install
from . import configset
from . import context
from . import taskgen
from . import task
from . import logs


def build(bld):
    env = bld.env
    zpy = bld.zpy
    if not bld.logger:
        #...use default name until we actually need multiple builds
        _log_name = 'build'
        _log_file = '%s.log' % _log_name
        _log_path = pth.join(bld.bldnode.abspath(), '%s.log' % _log_name)
        bld.logger = Logs.make_logger(_log_path, _log_name)

    bld.o = bld.root.make_node(zpy.o)
    bld.py = bld.bldnode.find_node('python')
    dists = sorted(zpy.dist.keys())

    bld.add_group()
    bld(features='zpy-update', target=dists)

    bld.add_group()
    bld(features='zpy-profile')

    bld.add_group()
    bld(features='zpy-extension', target='setuptools')

    bld.add_group()
    bld(features='zpy-extension', target=dists,
            excl=('python', 'setuptools', 'versiontools'))

    bld.add_group()
    bld(features='zpy-replay')

    bld.add_group()
    bld(features='zpy-final')

    #if bld.cmd.endswith(('install', 'build')):
    #    bld.add_post_fun(test)

    if bld.cmd.endswith(('install'),) and zpy.ins:
        install(bld)
