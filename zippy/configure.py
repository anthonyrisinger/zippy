# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import sys
import os
import glob
import operator
import distutils

import re
import pwd
import json
import platform
import tempfile
import urlparse, urllib
from distutils import sysconfig
from collections import defaultdict
from os import path as pth

from waflib import Utils, Logs
from waflib import Configure, Context, Build

from .util import get_module
from .util import sub_build
from .util import py_v

metadata = get_module('distlib.metadata')
database = get_module('distlib.database')
make_dist = get_module('distlib.database').make_dist
parse_requirement = get_module('distlib.util').parse_requirement


class ZPyCtx_Configure(Configure.ConfigurationContext):

    cmd = 'configure'

    def execute(self):
        rc = super(ZPyCtx_Configure, self).execute()
        zpy = self.zpy
        if not zpy.dist:
            #...user never called cnf.zpy_requirements()
            self.zpy_requirements(*zpy.opt['requirements'])
            #...save the config for `install`
            zpy.store(zpy.bld_cache_file)
            #...update JSON config
            zpy.store(zpy.bld_landmark)
        return rc


@Configure.conf
def zpy_egg_name(ctx, fqn):
    x = fqn.rfind('-')
    return (
        (fqn[0:x].replace('-', '_'))
        + (fqn[x:])
        + ('-%s.egg' % py_v('px.y', v=ctx.env.py_v))
        )


@Configure.conf
def zpy_requirements(cnf, *nodes, **ctx):
    env = cnf.env
    zpy = cnf.zpy
    opt = zpy.opt

    #FIXME: drop this once cnf.dependency_finder handles direct refs
    # current directory is zippy
    urls = ['.']
    reqts = dict()
    dists = set()

    for node in filter(None, nodes):
        for url in sorted(glob.glob(node)) or [node]:
            if url and url not in urls:
                urls.append(url)

    urls.reverse()
    bld_abspath = cnf.bldnode.abspath()
    while urls:
        url = urls.pop()
        urldata = None

        if pth.isdir(url):
            url = pth.relpath(url, zpy.top)
            path = pth.join(url, metadata.METADATA_FILENAME)
            if pth.exists(path):
                # url is a project dir
                dist = database.Distribution(
                    metadata=metadata.Metadata(path=path),
                    )
                dist.requested = True
                dists.add(dist)

                link = pth.relpath(url, bld_abspath)
                dest = pth.join(bld_abspath, dist.key)
                if not pth.exists(dest):
                    os.symlink(link, dest)

                #TODO: build_requires/test_requires/etc/?
                urldata = dist.run_requires

        if urldata is None:
            urldata = urllib.urlopen(url).read().splitlines()

        for spec in sorted(urldata):
            spec = spec.strip()
            if not spec or spec[0]=='#':
                continue

            req = parse_requirement(spec)
            if not req:
                continue

            key = req.name.lower()
            if key in reqts:
                #FIXME: handle extras/url
                # merge requirements
                constraints = reqts[key].constraints + req.constraints
                constraints = ', '.join(' '.join(c) for c in constraints)
                spec = '{0} ({1})'.format(req.name, constraints)
                req = parse_requirement(spec)
                req.origin = reqts[key].origins

            if not hasattr(req, 'origins'):
                req.origins = list()
            req.origins.append(url)
            reqts[key] = req

    #FIXME: get zippy here once cnf.dependency_finder finds local checkouts
    for special in ('Python (== 2.7.7, < 3.0)', 'setuptools'):
        req = parse_requirement(special)
        key = req.name.lower()
        if key not in reqts and key not in dists:
            req.origins = ['(internal)']
            reqts[key] = req

    origin = None
    node = cnf.bldnode.find_or_declare('config.requirements.txt')
    with open(node.abspath(), mode='w') as fp:
        for _,_,req in sorted(
            (req.origins, req.requirement.lower(), req)
            for req in reqts.values()
            ):
            if origin != req.origins:
                origin = req.origins
                fp.write('# {0}\n'.format(', '.join(req.origins)))
            fp.write('{0}\n'.format(req.requirement))

    Logs.pprint(None, 'Resolving distributions...')
    #FIXME: drop Anonymous once cnf.dependency_finder finds local checkouts
    anonymous = make_dist('Anonymous', '1.0')
    requirements = tuple(req.requirement for req in reqts.values())
    anonymous.metadata.add_requirements(requirements)
    hits, probs = cnf.dependency_finder.find(anonymous)
    hits.discard(anonymous)
    for prob in list(probs):
        if prob[0] != 'unsatisfied':
            probs.discard(prob)
            continue

        if prob[1].startswith('dateutil '):
            # bogus dist (should be python-dateutil) referenced by tastypie?
            probs.discard(prob)
            continue

    if probs:
        problems = list()
        for typ, spec in probs:
            req = parse_requirement(spec)
            req = reqts.get(req.name.lower(), req)
            if not hasattr(req, 'origins'):
                req.origins = list()
            for i, origin in enumerate(req.origins):
                constraint = None
                problem = '{0}: {1}'.format(origin, req.name)
                if req.url:
                    constraint = ('from', req.url)
                elif req.constraints and len(req.constraints) > i:
                    constraint = req.constraints[i]
                if constraint:
                    problem += ' ({0} {1})'.format(*constraint)
                problems.append(problem)
        problem_str = '\n    '.join([''] + problems)
        cnf.fatal('unsatisfied requirements: {0}'.format(problem_str))

    dists.update(hits)
    zpy.dist.update(
        (dist.key, dist.metadata.dictionary)
        for dist in dists
        )

    for dist in sorted(dists, key=operator.attrgetter('key')):
        #FIXME: .format()
        sys.stderr.write('%7s %s%s %s%s\n%s' % (
            '',
            Logs.colors.BOLD_BLUE,
            dist.name,
            Logs.colors.NORMAL + Logs.colors.BLUE,
            dist.version,
            Logs.colors.NORMAL,
            ))

    feats = Utils.to_list(ctx.get('features', ''))
    if 'zpy-requirements' not in feats:
        feats.append('zpy-requirements')
        ctx['features'] = feats
    inputs = ctx.setdefault('source', list())
    inputs.extend(dists)

    #FIXME:upstream:waf
    # workaround to clobbering .wafpickle-* cache
    dbfile_orig = Context.DBFILE
    Context.DBFILE = dbfile_orig + '-requirements'
    bld = sub_build(cnf, ctx, logger=cnf.logger)
    bld.compile()
    Context.DBFILE = dbfile_orig

    python = cnf.zippy_dist_get('python')
    py = cnf.bldnode.find_node('python')
    if py is None:
        cnf.fatal('%s does not exist' % python.name_and_version)

    zpy.PYTHON = pth.join(py.abspath(), py_v('pt'))
    zpy.py_v = tuple(map(int, python.version.split('.')))
    zpy.py_fqn = py_v('pt-x.y.z', v=zpy.py_v)
    zpy.py_v1 = py_v('x', v=zpy.py_v)
    zpy.py_v2 = py_v('x.y', v=zpy.py_v)
    zpy.py_v3 = py_v('x.y.z', v=zpy.py_v)
    zpy.py_ver1 = py_v('ptx', v=zpy.py_v)
    zpy.py_ver2 = py_v('ptx.y', v=zpy.py_v)
    zpy.py_ver3 = py_v('ptx.y.z', v=zpy.py_v)
    zpy.py_ver2_nodot = py_v('ptxy', v=zpy.py_v)
    zpy.o_stlib = 'lib%s.a' % zpy.py_ver2
    zpy.O_PYTHON = pth.join(zpy.o_bin, zpy.py_ver2)
    zpy.o_lib_py = pth.join(zpy.o_lib, zpy.py_ver2)
    zpy.o_lib_py_site = pth.join(zpy.o_lib_py, 'site-packages')
    zpy.o_inc_py = pth.join(zpy.o_inc, zpy.py_ver2)
    Utils.check_dir(zpy.o_lib_py_site)

    _pybuilddir = 'build/lib.%s-%s' % (
        distutils.util.get_platform(), zpy.py_v2,
        )
    zpy.pybuilddir = py.make_node(_pybuilddir).abspath()
    zpy.pylibdir = py.make_node('Lib').abspath()
    zpy.env['PYTHONHOME'] = zpy.o
    zpy.env['PYTHONPATH'] = ':'.join([
        'wheel-{0}/lib'.format(zpy.tstamp),
        zpy.pybuilddir,
        zpy.pylibdir,
        zpy.o_lib_py_site,
        ])

    # touch LANDMARK so PYTHONHOME doesn't need export afterwards
    open(pth.join(zpy.o_lib_py, zpy.landmark), mode='a').close()


def configure(cnf):
    """core configuration/checks
    """
    opt = cnf.options
    env = cnf.env
    zpy = cnf.zpy
    environ = cnf.environ

    zpy.tstamp = environ['ZIPPY_BUILD']
    zpy.api_pypi = 'https://pypi.python.org/simple/'

    zpy.top = cnf.path.abspath()
    zpy.opt = vars(opt).copy()

    _ident = zpy.opt['identifier']
    zpy.identifier = re.sub('[^-0-9A-Za-z_]', '', _ident)
    if zpy.identifier != _ident:
        cnf.fatal('ident MUST be alphanumeric: %r' % _ident)

    zpy.dist = dict()
    zpy.variant_name = cnf.variant
    zpy.variant_file = cnf.variant + Build.CACHE_SUFFIX
    zpy.landmark = '{0}.{1}.json'.format(__package__, _ident)

    zpy.bld_name = str(cnf.bldnode)
    zpy.bld_path = cnf.bldnode.path_from(cnf.path)
    zpy.bld_landmark = pth.join(zpy.bld_path, 'config.json')
    zpy.bld_cache_name = str(cnf.cachedir)
    zpy.bld_cache_path = cnf.cachedir.path_from(cnf.path)
    zpy.bld_cache_file = pth.join(zpy.bld_cache_path, zpy.variant_file)

    dirs = set((
        ('cache', None),
        ('xsrc', 'extern/sources'),
        ))
    for k, v in sorted(dirs):
        key = 'top_' + k
        zpy[key] = cnf.find_file(v or k, zpy.top)

    #...use default name until we actually need multiple builds
    _o = cnf.bldnode.make_node('--')
    zpy.o = _o.abspath()
    zpy.o_bin = _o.make_node('bin').abspath()
    zpy.o_lib = _o.make_node('lib').abspath()
    zpy.o_inc = _o.make_node('include').abspath()
    Utils.check_dir(zpy.o_bin)
    Utils.check_dir(zpy.o_lib)
    Utils.check_dir(zpy.o_inc)

    _user = pwd.getpwuid(os.getuid())
    _machine = platform.machine()
    _platform = distutils.util.get_platform()
    _triplet = (
        sysconfig.get_config_var('HOST_GNU_TYPE') or
        sysconfig.get_config_var('host') or
        cnf.cmd_and_log(
            ['gcc', '-dumpmachine'],
            output=Context.STDOUT,
            quiet=Context.BOTH,
            ) or
        '%s-%s-%s' % (
            _machine,
            platform.system().lower(),
            'gnu',
            )
        ).strip()
    zpy.machine = _machine
    zpy.platform = _platform
    zpy.triplet = _triplet

    _xdg_cache = pth.abspath(
            environ.get('XDG_CACHE_HOME') or
            pth.join(_user.pw_dir, '.cache')
            )
    _cache = cnf.root.make_node(pth.join(_xdg_cache, 'zippy'))
    zpy.cache = _cache.abspath()

    for ent in ('bin', 'out', 'tmp', 'wheel'):
        key = 'cache_%s' % ent
        zpy[key] = _cache.make_node(ent).abspath()
        Utils.check_dir(zpy[key])

    #...used by exec_command() for subprocesses
    env.env = dict()
    _path = os.pathsep.join(filter(None, (
        zpy.cache_bin, environ.get('PATH')
        )))
    _path = env.PATH = env.env['PATH'] = os.environ['PATH'] = _path

    _cflags = [
        '-march=%s' % _machine.replace('_','-'),
        '-mtune=generic',
        '--param=ssp-buffer-size=4',
        '-pipe',
        '-O2',
        '-fPIC',
        #FIXME: wheezy can do this, DISABLE FOR DEBUG
        #'-flto=%s' % opt.jobs,
        #'-fno-fat-lto-objects',
        #FIXME: this needs gold or ld 2.21
        #'-fuse-linker-plugin',
        #'-fuse-ld=gold',
        #FIXME: this should be with other profile opts, not here!
        #'-fprofile-correction',
        '-fstack-protector',
        '-fvisibility=hidden',
        '-Wcoverage-mismatch',
        ]
    _exports = {
        'ZIPPY_CONFIG': pth.abspath(zpy.buffer.name),
        'ZIPPY_BUILD': zpy.tstamp,
        'UWSGI_USE_DISTUTILS': 'x',
        'LANG': 'en_US.UTF-8',
        'USER': _user.pw_name,
        'HOME': _user.pw_dir,
        'CARCH': _machine,
        'CHOST': _triplet,
        'TMPDIR': tempfile.gettempdir(),
        'MAKEFLAGS': '-j%s' % opt.jobs,
        'CCACHE_DIR': zpy.cache_out,
        'CCACHE_BASEDIR': cnf.bldnode.abspath(),
        'CCACHE_COMPRESS': '1',
        'CFLAGS': _cflags,
        'CXXFLAGS': _cflags,
        'CPPFLAGS': ['-D_FORTIFY_SOURCE=2'],
        'LDFLAGS': ['-Wl,-O1,--sort-common,--as-needed,-z,relro'],
        'UWSGI_PROFILE' : '_zippy_%s.ini' % _ident,
        }
    if zpy.opt.get('debug'):
        _exports['PYTHONVERBOSE'] = 'x'
    for k, v in _exports.iteritems():
        if v is not None:
            env.append_value(k, v)
        cnf.add_os_flags(k)
        if isinstance(v, str):
            env[k][:-1] = []
            env[k] = env[k] and env[k].pop() or str()
        env.env.setdefault(k, env.get_flat(k))

    progs = set((
        'make',
        'tar',
        'unzip',
        'nm',
        'objcopy',
        'git',
        'ld',
        'patch',
        'strip',
        ))
    map(cnf.find_program, sorted(progs))

    if 'uconf' not in zpy:
        zpy.uconf = dict()

    for default in (
        ('json', 1),
        ('pcre', 1),
        ('routing', 1),
        ('ssl', 1),
        ('xml', 1),
        ('yaml', 1),
        ('zeromq', 1),

        ('append_version', _ident),
        ('plugin_dir', 'lib-dynload-uwsgi'),

        ('locking', 'auto'),
        ('event', 'auto'),
        ('timer', 'auto'),
        ('filemonitor', 'auto'),
        ('xml_implementation', 'libxml2'),
        ('yaml_implementation', 'libyaml'),
        ('malloc_implementation', 'libc'),

        ('plugins', ''),
        ('embed_files', ''),
        ('embed_config', ''),
        ('embedded_plugins', [
            'cache', 'carbon', 'cheaper_busyness', 'corerouter', 'dumbloop',
            'fastrouter', 'gevent', 'http', 'logfile', 'logsocket',
            'mongodblog', 'nagios', 'ping', 'python', 'rawrouter', 'redislog',
            'router_basicauth', 'router_cache', 'router_http',
            'router_redirect', 'router_rewrite', 'router_static',
            'router_uwsgi', 'rpc', 'rrdtool', 'rsyslog', 'signal', 'spooler',
            'sslrouter', 'symcall', 'syslog', 'transformation_gzip',
            'transformation_tofile', 'ugreen', 'zergpool',
            ]),
        ):
        zpy.uconf.setdefault(*default)

    if not _cache.find_node('bin/ccache'):
        import shutil
        shutil.rmtree(zpy.cache, ignore_errors=True)
        shutil.copytree(zpy.top_cache, zpy.cache, symlinks=True)
        _bin = pth.join(zpy.cache_bin, '')
        _slink = _bin + 'ccache.%s' % _machine
        _dlink = _bin + 'ccache'
        if pth.exists(_dlink) and not pth.samefile(_slink, _dlink):
            os.remove(_dlink)
        if not pth.exists(_dlink):
            os.link(_slink, _dlink)
        for lnk in (
                '%s%s' % (pfx, sfx)
                for pfx in ('', _triplet + '-')
                for sfx in ('g++', 'gcc', 'cpp', 'c++', 'cc')
                ):
            _dlink = _bin + lnk
            if not pth.exists(_dlink):
                os.symlink('ccache', _dlink)
