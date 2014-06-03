# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

from waflib import Utils


def install(bld, add=True):
    tasks = list()
    zpy = bld.zpy
    tasks.append(bld.install_files(
        '${PREFIX}', zpy.ins, relative_trick=True,
        cwd=bld.o, chmod=Utils.O755, add=add,
        ))
    tasks.extend((
        bld.symlink_as('${PREFIX}/bin/${py_ver1}', zpy.py_ver2, add=add),
        bld.symlink_as('${PREFIX}/bin/python', zpy.py_ver1, add=add),
        ))
    return tasks
