# encoding: utf-8

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import


def py_v(_p_xyz=None, v=None, _cache=dict()):
    import platform

    v = v or platform.python_version_tuple()
    _p_xyz = str(_p_xyz).lower()
    _key = (_p_xyz, tuple(map(int, v)))
    if _key in _cache:
        return _cache.get(_key)

    _chars = frozenset(_p_xyz)
    _python = (
        ('py'       if set('p').issubset(_chars)    else '')
        + ('thon'    if set('t').issubset(_chars)    else '')
        + ('uwsgi'   if set('u').issubset(_chars)    else '')
        + ('-'       if set('-').issubset(_chars)    else '')
        + (str(v[0]) if set('x').issubset(_chars)    else '')
        + ('.'       if set('xy.').issubset(_chars)  else '')
        + (str(v[1]) if set('xy').issubset(_chars)   else '')
        + ('.'       if set('xyz.').issubset(_chars) else '')
        + (str(v[2]) if set('xyz').issubset(_chars)  else '')
        )
    return _cache.setdefault(_key, _python)


def sub_build(ctx, *args, **kwds):
    """self-contained internal builds for auto-config/tests/etc
    """
    from waflib import Build

    logger = kwds.pop('logger', None)
    variant = kwds.pop('variant', '')
    all_envs = kwds.pop('all_envs', ctx.all_envs)
    kwds.setdefault('top_dir', ctx.srcnode.abspath())
    kwds.setdefault('out_dir', ctx.bldnode.abspath())

    bld = Build.BuildContext(**kwds)
    bld.logger = logger
    bld.variant = variant
    bld.all_envs = all_envs
    bld.init_dirs()

    for gen_ctx in args:
        #...empty tgens still invoke '*' features; NO SKIP
        gen_ctx = gen_ctx or dict()
        g = gen_ctx.get('group')
        if g and g not in bld.group_names:
            bld.add_group(name=g, move=False)
        bld(**gen_ctx)

    #...caller should customize if necessary, then bld.compile()
    return bld


def update_syspath(paths, alternates=False):
    import sys
    import os

    if not paths:
        return sys.path

    prefixes = list()
    libpy = os.path.join('lib', 'python%s.%s' % sys.version_info[0:2])
    libpysite = os.path.join(libpy, 'site-packages')
    if paths[0:0] == '':
        paths = [paths]

    for path in paths:
        for prefix in (os.path.abspath(path), os.path.realpath(path)):
            if prefix not in prefixes:
                entries = [prefix]
                if alternates:
                    entries.append(
                        os.path.dirname(os.path.dirname(prefix)),
                        )
                for entry in entries:
                    prefixes.extend((
                        entry,
                        os.path.join(entry, libpy),
                        os.path.join(entry, libpysite),
                        ))

    if not prefixes:
        return sys.path

    # NOTE: only works properly if processed before site.py
    marker = ''
    syspath = sys.path[:]
    if marker not in syspath:
        syspath.insert(0, marker)
    if 'PYTHONPATH' in os.environ and not sys.flags.ignore_environment:
        marker = os.environ['PYTHONPATH'].rpartition(':')[-1]
    index = syspath.index(marker) + 1
    syspath[index:] = prefixes

    return syspath


def site(module, ident):
    init_builtins()

    import os
    import sys
    import zippy

    sys.zippy = zippy
    building = 'ZIPPY_BUILD' in os.environ

    #TODO: APP_BASE/__PATH__/__path__
    if not building and sys.prefix == sys.executable:
        sys.path[:] = update_syspath(sys.executable)

    name = 'site_' + ident
    sys.modules[name] = module
    module.__name__ = name
    reload(module)

    if building:
        import zippy.l4sh

    # HACKZILLA!
    # python will prepend the current directory to sys.path, from C code
    # (PySys_SetArgv), while setting sys.argv... but this happens AFTER
    # site.py is imported! uwsgi could avoid this by calling PySys_SetArgvEx,
    # but this wouldn't be consistent with vanilla python, and uwsgi has it's
    # own set of problems, eg. setting sys.executable to realpath(argv[0])
    # instead of using the original symlink path, like python... "arg"!!!
    def tracer(frame, event, args):
        if frame.f_globals.get('__name__') == '__main__':
            sys.settrace(tracer_orig)
            syspath = normalize_syspath(sys.path)
            sys.path[:] = syspath

    tracer_orig = sys.gettrace()
    sys.settrace(tracer)

    return module


def normalize_syspath(syspath, cwd=''):
    cwds = set(('', '.', cwd))
    if not cwd:
        import os
        cwds.add(os.getcwd())

    sysset = set(syspath)
    syspath = list(
        #   NO: pop(...) YES: pop() :(
        sysset.remove(x) or x
        for x in syspath if x in sysset
        )

    while syspath and syspath[0] in cwds:
        syspath.pop(0)
    syspath.insert(0, '')

    return syspath


def get_module(name, package=None):
    packages = [getattr(package, '__name__', package)]
    if not packages[0]:
        try:
            from . import vendor
        except ImportError:
            pass
        else:
            packages.insert(0, vendor.__name__)

    module = None
    keys = ('__name__', '__package__')
    for package in packages:
        ns = dict.fromkeys(keys, package or 'x')
        try:
            module = __import__(name, ns, ns, ['*'], bool(package))
        except ImportError:
            continue
        else:
            break

    return module


def init_builtins():
    try:
        import builtins
    except ImportError:
        import __builtin__ as builtins

    builtins.pp = deferred(pp, builtins)


def deferred(fun, *args0, **kwds0):
    def deferred(*args1, **kwds1):
        return fun(*args0, **kwds0)(*args1, **kwds1)
    deferred.__name__ = ':'.join((
        fun.__name__, deferred.__name__.upper(),
        ))
    return deferred


def pp(builtins):
    import sys

    try:
        from pprint import pprint
    except ImportError:
        print_ = print
        key = 'file'
    else:
        print_ = pprint
        key = 'stream'

    def pp(*args, **kwds):
        if len(args) == 1:
            (args,) = args

        err = kwds.pop('stream', None)
        err = kwds.pop('file', err)
        if err is None:
            err = sys.stderr
        kwds[key] = err

        return print_(args, **kwds)

    builtins.pp = pp
    return pp
