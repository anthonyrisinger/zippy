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


try:
    import time
    import zipfile
except ImportError:
    pass
else:
    from . import __dict__ as ns
    ns['TSTAMP'] = int(time.time())
    #...patch older ZipFile to support 2.7 context manager
    if not hasattr(zipfile.ZipFile, '__exit__'):
        zipfile.ZipFile.__enter__ = lambda *s: s[0]
        zipfile.ZipFile.__exit__ = lambda *s: s[0].close()
    #...patch older ZipExtFile to support 2.7 context manager
    if not hasattr(zipfile.ZipExtFile, '__exit__'):
        zipfile.ZipExtFile.__enter__ = lambda *s: s[0]
        zipfile.ZipExtFile.__exit__ = lambda *s: s[0].close()


data = None
