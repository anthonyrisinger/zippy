# encoding: utf-8

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zippy
import sys
import os

#FIXME: need compat.py or...?
try:
    import time
    import zipfile
except ImportError:
    pass
else:
    #...patch older ZipFile to support 2.7 context manager
    if not hasattr(zipfile.ZipFile, '__exit__'):
        zipfile.ZipFile.__enter__ = lambda *s: s[0]
        zipfile.ZipFile.__exit__ = lambda *s: s[0].close()
    #...patch older ZipExtFile to support 2.7 context manager
    if not hasattr(zipfile.ZipExtFile, '__exit__'):
        zipfile.ZipExtFile.__enter__ = lambda *s: s[0]
        zipfile.ZipExtFile.__exit__ = lambda *s: s[0].close()


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


def is_zippy_build():
    return 'ZIPPY_BUILD' in os.environ


def site(module, ident):
    init_builtins()

    sys.zippy = zippy
    building = is_zippy_build()

    #TODO: APP_BASE/__PATH__/__path__
    if not building and sys.prefix == sys.executable:
        sys.path[:] = update_syspath(sys.executable)

    name = 'site_' + ident
    sys.modules[name] = module
    module.__name__ = name
    reload(module)

    if building:
        __import__('zippy.l4sh')

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
            if building:
                m_file = frame.f_globals.get('__file__') or str()
                if m_file.strip('co').endswith('compileall.py'):
                    raise SystemExit(0)

    tracer_orig = sys.gettrace()
    sys.settrace(tracer)

    return module


def normalize_syspath(syspath, cwd=''):
    cwds = set(('', '.', cwd))
    if not cwd:
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

    builtins.pp = deferred(builtin_pp, builtins)
    builtins.I = deferred(builtin_I, builtins)


def deferred(fun, *args0, **kwds0):
    def deferred(*args1, **kwds1):
        return fun(*args0, **kwds0)(*args1, **kwds1)
    deferred.__name__ = ':'.join((
        fun.__name__.split('_', 1)[-1],
        deferred.__name__,
        ))
    return deferred


def builtin_I(builtins):
    from IPython.frontend.terminal.embed import InteractiveShellEmbed
    from IPython.frontend.terminal.ipapp import load_default_config
    from IPython.frontend.terminal.interactiveshell import (
        TerminalInteractiveShell
        )

    def I(**kwds):
        sys.stdin = sys.stdout = open('/dev/tty', mode='r+b')
        config = kwds.get('config')
        header = kwds.pop('header', u'')
        if config is None:
            config = load_default_config()
            config.InteractiveShellEmbed = config.TerminalInteractiveShell
            kwds['config'] = config
        return InteractiveShellEmbed(**kwds)(header=header, stack_depth=2)

    builtins.I = I
    return I


def builtin_pp(builtins):
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


def normalize_pydist(info):
    from os import path as pth
    distlib = get_module('distlib')
    metadata = get_module('distlib.metadata')

    for k in ('license', 'description'):
        if k in info and len(info[k]) > 61:
            info[k] = info[k][0:61] + '...'

    ext_details = ('extensions', 'python.details')
    ext_project = ('extensions', 'python.project')
    ext_exports = ('extensions', 'python.exports')
    ext_commands = ('extensions', 'python.commands')
    keymap = {
        'metadata_version': None,
        'generator': None,
        'source_url': None,
        'source_label': None,
        'download-url': ('source_url',),
        'license': ext_details + ('license',),
        'keywords': ext_details + ('keywords',),
        'classifiers': ext_details + ('classifiers',),
        'document_names': ext_details + ('document_names',),
        'contacts': ext_project + ('contacts',),
        'contributors': ext_project + ('contributors',),
        'project_urls': ext_project + ('project_urls',),
        'modules': ext_exports + ('modules',),
        'namespaces': ext_exports + ('namespaces',),
        'exports': ext_exports + ('exports',),
        'commands': ext_commands,
        'author-email': ext_project + ('contacts', 0, 'email'),
        'maintainer-email': ext_project + ('contacts', 1, 'email'),
        'author': ext_project + ('contacts', 0, 'name'),
        'maintainer': ext_project + ('contacts', 1, 'name'),
        'license-file': ext_details + ('document_names', 'license'),
        'home-page': ext_project + ('project_urls', 'Home'),
        }
    keyset = set(
        keymap.keys()
        + metadata.Metadata.MANDATORY_KEYS.keys()
        + metadata.Metadata.DEPENDENCY_KEYS.split()
        + metadata.Metadata.INDEX_KEYS.split()
        ) - set((
            # great! DGAF
            'description',
            ))

    pydist = {
        'index-metadata': dict(),
        'metadata': dict(),
        }
    pydist.update(
        distlib.util.get_package_data(
            info['name'],
            info['version'],
            ) or tuple()
        )
    pydist['metadata'].update(info)
    index_meta = pydist.pop('index-metadata')
    local_meta = pydist.pop('metadata')
    pydist.clear()

    remaps = list()
    for key in keyset:
        local_value = local_meta.pop(key, None)
        index_value = index_meta.pop(key, None)

        if local_value is None and index_value is None:
            continue

        value = local_value
        if index_value and index_value != local_value:
            value = index_value

        if key not in keymap or keymap[key] is None:
            pydist[key] = value
            continue

        node = pydist
        attrs = keymap[key]
        for attr in attrs[:-1]:
            node[attr] = node.get(attr) or dict()
            if not hasattr(node[attr], 'get'):
                node[attr] = dict(enumerate(node[attr]))
                remaps.append((node, attr))
            node = node[attr]
        node[attrs[-1]] = value

    for node, attr in remaps:
        # only `contacts` in here ATM
        #TODO: avoid duplicates
        if attr == 'contacts':
            contacts = list()
            for offset, info in sorted(node[attr].items()):
                if 'role' not in info:
                    role = 'author'
                    if offset > 0:
                        role = 'maintainer'
                    info['role'] = role
                contacts.append(info)
            node[attr] = contacts

    return pydist
