#!/usr/bin/env python
# encoding: utf-8

from __future__ import division, absolute_import, print_function


#TODO: pull from __init__.py like setup.py
#TODO: should this be different? embedded vs builder
VERSION = '0.6.1'
APPNAME = 'zippy'

top = '.'
out = 'build'


def init(ctx):
    return


def shutdown(ctx):
    return


#TODO: replace with xacto
def waf_entry_point(directory=None):
    import os
    import sys
    import traceback

    import zippy
    import waflib
    from waflib import Logs
    from waflib import Errors
    from waflib import Options
    from waflib import Context
    from waflib import Scripting
    from waflib import Configure
    from waflib import Build

    Logs.init_log()

    directory = os.path.abspath(directory or os.getcwd())
    name = __package__.title()

    Context.WSCRIPT_FILE = 'zscript.py'
    Context.g_module = __import__(__name__)
    Context.g_module.root_path = __file__
    Context.cache_modules[Context.g_module.root_path] = Context.g_module

    Context.launch_dir = directory
    Context.run_dir = directory
    Context.top_dir = directory
    Context.out_dir = directory + os.sep + out
    Context.waf_dir = os.path.abspath(os.path.dirname(waflib.__path__[0]))
    for key in ('update', 'dist', 'distclean', 'distcheck'):
        attr = getattr(Scripting, key)
        if attr.__name__ not in Context.g_module.__dict__:
            setattr(Context.g_module, attr.__name__, attr)
        if key not in Context.g_module.__dict__:
            setattr(Context.g_module, key, attr)

    def pre_recurse(self, node, _pre_recurse=Context.Context.pre_recurse):
        _pre_recurse(self, node)
        if node.abspath() == Context.g_module.root_path:
            self.path = self.root.find_dir(Context.run_dir)
    def recurse(self, dirs, **kwds):
        if Context.run_dir in dirs:
            dirs[dirs.index(Context.run_dir)] = os.path.dirname(__file__)
        _recurse(self, dirs, **kwds)
    _pre_recurse = Context.Context.pre_recurse
    _recurse = Context.Context.recurse
    Context.Context.pre_recurse = pre_recurse
    Context.Context.recurse = recurse

    try:
        os.chdir(Context.run_dir)
    except OSError:
        Logs.error('%s: The directory %r is unreadable' % (name, Context.run_dir))
        return 1

    try:
        Scripting.parse_options()
        Scripting.run_command('init')
        try:
            os.stat(Context.out_dir + os.sep + Build.CACHE_DIR)
        except Exception:
            if 'configure' not in Options.commands:
                Options.commands.insert(0, 'configure')
        while Options.commands:
            cmd_name = Options.commands.pop(0)
            ctx = Scripting.run_command(cmd_name)
            Logs.info('%r finished successfully (%s)' % (
                cmd_name, str(ctx.log_timer),
                ))
        Scripting.run_command('shutdown')
    except Errors.WafError as e:
        if Logs.verbose > 1:
            Logs.pprint('RED', e.verbose_msg)
        Logs.error(e.msg)
        import traceback
        traceback.print_stack()
        return 1
    except SystemExit:
        raise
    except Exception as e:
        traceback.print_exc(file=sys.stdout)
        return 2
    except KeyboardInterrupt:
        Logs.pprint('RED', 'Interrupted')
        return 68

    return 0


if __name__ == '__main__':
    import sys
    sys.dont_write_bytecode = True

    import os
    from datetime import datetime
    os.environ['ZIPPY_BUILD'] = datetime.utcnow().strftime('%F-%s')

    from .util import init_builtins
    from .util import get_module
    init_builtins()

    sys.modules['waflib'] = get_module('waflib')
    from .setup import setup
    from .options import options
    from .configure import configure
    from .build import build
    from .test import test
    from .install import install
    sys.exit(waf_entry_point())
