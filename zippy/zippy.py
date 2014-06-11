#!/usr/bin/env python
# encoding: utf-8

from __future__ import division, absolute_import, print_function


#TODO: replace with xacto
def waf_entry_point(directory=None):
    import sys
    from os import path
    from os import getcwd

    from .util import get_module
    waflib = get_module('waflib')
    #TODO: update/vendorize waflib
    sys.modules.setdefault('waflib', waflib)
    from waflib import Context
    from waflib import Scripting

    Scripting.waf_entry_point(
        directory or getcwd(),
        Context.WAFVERSION,
        path.dirname(path.dirname(waflib.__file__)),
        )


if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True

    import os
    from datetime import datetime
    from zippy.util import init_builtins

    os.environ['ZIPPY_BUILD'] = datetime.utcnow().strftime('%F-%s')
    init_builtins()
    waf_entry_point()
