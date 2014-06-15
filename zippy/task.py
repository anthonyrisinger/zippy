# encoding: utf-8

from __future__ import division
from __future__ import absolute_import
from __future__ import print_function

import pprint
pp = pprint.pprint

import sys, os, logging
import time, re, shutil, glob

import urlparse, urllib, zipfile, json
from collections import defaultdict
from os import path as pth
import distutils
import codecs

import waflib
from waflib import Utils, Logs
from waflib import Build
from waflib import Task

from .const import PYTHON_MODULES_SETUP
from .util import normalize_pydist
from .util import get_module

distlib = get_module('distlib')
wheel = get_module('distlib.wheel')
metadata = get_module('distlib.metadata')
database = get_module('distlib.database')


class ZPyTaskBase(Task.Task):

    def __str__(self):
        """log to term... mostly copied from waflib.Task.Task
        """
        return self.__class__.__name__.split(
                '_', 1)[-1].replace('_', ' ').lower()

    def display(self):
        """log to term... mostly copied from waflib.Task.Task
        """
        norm = Logs.colors.NORMAL
        bold = Logs.colors.BOLD
        dark = Logs.colors.BLACK
        col1 = Logs.colors(self.color)
        col2 = bold + col1
        master = self.master

        def cur():
            # the current task position, computed as late as possible
            tmp = -1
            if hasattr(master, 'ready'):
                tmp -= master.ready.qsize()
            return master.processed + tmp

        if self.generator.bld.progress_bar == 1:
            return self.generator.bld.progress_line(
                    cur(), master.total,
                    col1, col2,
                    )

        if self.generator.bld.progress_bar == 2:
            ela = str(self.generator.bld.timer)
            try:
                ins  = ','.join([n.name for n in self.inputs])
            except AttributeError:
                ins = ''
            try:
                outs = ','.join([n.name for n in self.outputs])
            except AttributeError:
                outs = ''
            return '|Total %s|Current %s|Inputs %s|Outputs %s|Time %s|\n' % (
                    master.total, cur(), ins, outs, ela,
                    )

        total = master.total
        n = len(str(total))
        n_min = (n * 2) + 2
        n_mod = n_min % 4
        n_buf = n_min + n_mod

        pfx = ' '*n_buf
        sp = ' '*2

        env = self.env
        src_str = ('\n'+pfx).join([a.nice_path() for a in self.inputs])
        tgt_str = ('\n'+pfx+sp).join([a.nice_path() for a in self.outputs])
        sep0 = sep1 = ''
        if self.inputs:
            sep0 = '\n'+norm+col1+pfx
        if self.outputs:
            sep1 = '\n'+norm+col1+pfx+sp

        name = str(self)
        dist = getattr(self, 'dist', None)
        if dist:
            name = '%s%s %s%s' % (
                name, dark, norm, dist.name_and_version
                )
        s = '%s%s%s%s%s\n' % (name, sep0, src_str, sep1, tgt_str)
        fs = '%s%%%dd/%%%dd%s%s %%s%%s%%s' % (' '*n_mod, n, n, bold, dark)
        out = fs % (cur(), total, col2, s, norm)

        sys.stderr.write(out)
        return ''


#FIXME: this either needs to go away, or be capable of handling all ZPyTasks
class _ZPyTask(ZPyTaskBase):

    color = 'BOLD'
    before = []
    after = []
    vars = [
        'LDFLAGS',
        'CFLAGS',
        'CPPFLAGS',
        'CXXFLAGS',
        'PATH',
        ]

    xtra = []
    app = []

    def scan(self):
        py = self.generator.bld.py
        xfiles, xany = list(), list()
        for pat in Utils.to_list(self.xtra):
            xfiles.extend(py.ant_glob(pat, remove=False))
        for x in xfiles:
            x.sig = Utils.h_file(x.abspath())
        return xfiles, xany

    def run(self):
        tsk = self
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        if getattr(self, 'cwd', None) is None:
            self.cwd = pth.join(bld.bldnode.abspath(), self.dist.key)

        python = bld.zippy_dist_get('python')
        self._key = '%s-%s-%s' % (
                python.key,
                python.version,
                Utils.to_hex(self.signature())
                )
        self._cache_conf = pth.join(zpy.cache_tmp, 'conf-%s' % self._key)
        self._cache_prof = pth.join(zpy.cache_tmp, 'prof-%s' % self._key)

        ret = 0
        for app in Utils.to_list(self.app):
            if not isinstance(app, basestring):
                ret |= app(self)
                continue

            app = app.format(**locals())
            ret |= self.exec_command(
                    app.strip('\0').split('\0'),
                    cwd=self.cwd,
                    env=env.env or None,
                    )

        return ret


class ZPyTask_Requirements(ZPyTaskBase):

    color = 'CYAN'
    before = []
    after = []
    vars = ['TAR']

    def display(self):
        return ''

    def scan(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        out = self.outputs[0].parent
        sig = Utils.to_hex(
            (self.inputs and getattr(self.inputs[0], 'sig', None))
            or getattr(out, 'sig', None)
            or Utils.md5(self.dist.name_and_version).digest()
            )

        deps = ([], [])

        #self.signode = out.make_node(sig)
        self.signode = bld.bldnode.make_node(
            str('.%s.%s' % (out.name, sig)),
            )
        self.signode.mkdir()
        #deps[0].append(self.signode)

        return deps

    def run(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        out = self.outputs[0].parent

        dist = self.dist
        signode = self.signode

        out_path = out.abspath()
        bld_path = bld.bldnode.abspath()
        source_url = dist.source_url or ''
        url = urlparse.urlsplit(source_url)
        # normalize initially to dist.key
        name = pth.basename(url.path).lower() or dist.key
        # ensure sdist filename matches dist.name!
        # otherwise dist.name != dist.metadata.name if the object was created
        # from a filename, even if metadata is loaded later!
        #FIXME: upstream fix to above...
        name = name.replace(dist.key, dist.name, 1)
        if dist.name not in name:
            # probably a hash
            ext = name[name.find('.'):]
            if len(ext) > 1:
                name = dist.metadata.name_and_version + ext
        # no raison other than consistency
        if name.endswith('.tgz'):
            name = name[:-4] + '.tar.gz'
        path = pth.join(zpy.top_xsrc, name)
        meta = path + '.' + metadata.METADATA_FILENAME

        if url.scheme and url.path and url.path != path:
            path, message = urllib.urlretrieve(url.geturl(), path)

        if pth.isfile(path):
            _zip = ('.zip',)
            _whl = ('.whl',)
            _tar = tuple(
                set(distlib.util.ARCHIVE_EXTENSIONS) - set(_zip + _whl)
                )
            if path.endswith(_whl):
                dist.metadata = wheel.Wheel(path).metadata
                dist_dir = pth.join(out_path, 'dist')
                Utils.check_dir(dist_dir)
                self.outputs[0].write(
                    json.dumps(
                        dist.metadata.dictionary,
                        ensure_ascii=True,
                        sort_keys=True,
                        indent=2,
                        ))
                whl_dst = pth.join(dist_dir, pth.basename(path))
                whl_sym = pth.relpath(path, dist_dir)
                if not pth.exists(whl_dst):
                    os.symlink(whl_sym, whl_dst)
            else:
                if pth.isfile(meta):
                    #TODO: needs to use zpy.dist
                    dist.metadata = metadata.Metadata(path=meta)
                else:
                    pydist = normalize_pydist(dist.metadata.dictionary)
                    pydist.update(source_url=pth.relpath(path, zpy.top))

                    with codecs.open(meta, 'w', 'utf-8') as fp:
                        json.dump(
                            pydist,
                            fp=fp,
                            ensure_ascii=True,
                            sort_keys=True,
                            indent=2,
                            )

                    dist.metadata._legacy = None
                    dist.metadata._data = pydist

                sig_path = signode.abspath()
                for sfx, cmd in (
                    (_tar, '{env.TAR}\0-C\0{sig_path}\0-xf\0{path}\0'),
                    (_zip, '{env.UNZIP}\0-q\0-o\0-d\0{sig_path}\0{path}\0'),
                    (None, None),
                    ):
                    if sfx is None:
                        distlib.util.unarchive(path, bld_path)
                        break

                    try:
                        cmd = cmd.format(**locals())
                        cmd = cmd.strip('\0').split('\0')
                    except AttributeError:
                        continue

                    rc = self.exec_command(cmd, env=env.env)
                    if rc == 0:
                        if not pth.exists(out_path):
                            tmp = signode.make_node(
                                Utils.listdir(signode.abspath())
                                )
                            os.rename(tmp.abspath(), out_path)
                        break
                shutil.copy2(meta, pth.join(out_path, metadata.METADATA_FILENAME))

        if dist.key == 'python':
            lib = pth.join(out_path, 'Lib')
            zippy_src = pth.join(zpy.top, 'zippy')
            zippy_dst = pth.join(lib, 'zippy')
            zippy_sym = pth.relpath(zippy_src, lib)
            if not pth.lexists(zippy_dst):
                os.symlink(zippy_sym, zippy_dst)
            incl_src = pth.join(out_path, 'Include')
            incl_dst = pth.join(zpy.o_inc, 'python'+dist.version[0:3])
            incl_sym = pth.relpath(incl_src, zpy.o_inc)
            if not pth.lexists(incl_dst):
                os.symlink(incl_sym, incl_dst)
            pyconfig = pth.join(out_path, 'Include', 'pyconfig.h')
            if not pth.lexists(pyconfig):
                os.symlink('../pyconfig.h', pyconfig)
        if dist.key == 'zippy':
            if not pth.lexists(out_path):
                os.symlink('..', out_path)

        return 0


class ZPyTask_Patch(ZPyTaskBase):

    color = 'CYAN'
    before = []
    after = []

    x, vars = Task.compile_fun(' '.join([
        '${PATCH}',
        '--reject-file=-',
        '-Np1',
        '-i',
        '${SRC[0].abspath()}',
        ]))

    def run(self):
        return self.x()


class ZPyTask_Update(ZPyTaskBase):

    color = 'PINK'
    before = []
    after = []

    x = defaultdict(dict)
    #...closure-decorator, stores `fn` and returns ITSELF, not `fn`
    def run(x=x):
        def f(key, path, **kwds):
            def g(fn):
                x[key][path] = (fn, kwds)
                return f
            return g
        return f
    run = run()

    #>>> CUSTOMIZATIONS <<<#

    @run('python (>= 2)', 'setup.py')
    def run(self, buf):
        """disable unused/broken C modules; allow sqlite3 to load extensions
        """
        #TODO: needs upstreaming!
        dis = ['_bsddb', '_ctypes_test', '_hotshot', '_testcapi', '_tkinter',
                'audioop', 'linuxaudiodev', 'nis', 'ossaudiodev', 'xxsubtype']
        #FIXME: parser module built very early... disable for now
        dis += ['parser']
        patterns = [
            (r"(disabled_module_list *=).*$",            r"\g<1> %r" % dis),
            #NOTE: python3 has --enable-loadable-sqlite-extensions
            (r"^.*SQLITE_OMIT_LOAD_EXTENSION.*$\n?",    r""),
            #TODO: needs upstreaming!
            (r"(longest = max\()\[", r"\g<1>0,0,*["),
            ]
        for pat, sub in patterns:
            pat = re.compile(pat, flags=re.MULTILINE)
            buf = pat.sub(sub, buf)
        return buf

    @run('python (>= 2)', 'Python/pythonrun.c')
    def run(self, buf):
        """assign an fully qualified default should python be unable to
        determine its own name; change flag defaults
        """
        pfx = self.env.BINDIR.rstrip('/')
        bld = self.generator.bld
        zpy = bld.zpy
        ver = zpy.py_ver2
        patterns = [
            ('"python"',    '"%s/%s"' % (pfx, ver)),
            ('^(int Py_(DontWriteBytecode|Frozen)Flag)[^;]*', '\g<1> = 1'),
            ('^(int Py_NoUserSiteDirectory)[^;]*',        '\g<1> = 1'),
            #('^(int Py_HashRandomizationFlag)[^;]*',    '\g<1> = 1'),
            ]
        for pat, sub in patterns:
            pat = re.compile(pat, flags=re.MULTILINE)
            buf = pat.sub(sub, buf)
        return buf

    @run('python (>= 2)', 'Modules/main.c')
    def run(self, buf):
        """export Py_GetArgcArgv"""
        zpy = self.generator.bld.zpy
        patterns = [
            (r"void\nPy_GetArgcArgv", r"PyAPI_FUNC(void) Py_GetArgcArgv"),
            ]
        for pat, sub in patterns:
            pat = re.compile(pat, flags=re.MULTILINE)
            buf = pat.sub(sub, buf)
        return buf

    @run('python (>= 2)', 'Makefile.pre.in')
    def run(self, buf):
        """libpythonX.Y.a object glob; default PREFIX to sys.executable
        """
        zpy = self.generator.bld.zpy
        dlm = '-DLANDMARK=\'"zippy.%s.json"\'' % zpy.identifier
        l4sh = '../*/l4sh/*.o'.format(
            **locals()
            )
        patterns = [
            (r"_(MODOBJS)_", r"\g<0>\n\g<1>+=$(wildcard %s)" % l4sh),
            (r"(-D(EXEC_)?PREFIX)='[^']*'", r"\g<1>='progpath' %s" % dlm),
            (r"-fprofile-(generate|use)",   r"\g<0>=$(PR0F)"),
            (r"(@EXENAME@,)[^/]*",   r"\g<1>%s" % zpy.BINDIR),
            ]
        for pat, sub in patterns:
            pat = re.compile(pat, flags=re.MULTILINE)
            buf = pat.sub(sub, buf)
        return buf

    @run('python (>= 2)', 'Lib/site.py', raw=True)
    def run(self, buf):
        """misc services during/after build
        """
        bld = self.generator.bld
        zpy = bld.zpy

        alt = buf.change_ext('_' + zpy.identifier + '.py', '.py')
        site = buf.read().replace(
            'if 0:', "if sys.zippy.util.get_module('locale'):", 1,
            )
        alt.write(site)

        src = (
            "__import__('sys').modules.update({{\n"
            "    __name__: __import__('zippy.util').util.site(\n"
            "        module=__import__(__name__),\n"
            "        ident={zpy.identifier!r},\n"
            "        )}})\n"
            ).format(zpy=zpy)
        buf.write(src)

    @run('python (>= 2)', 'Modules', raw=True)
    def run(self, buf):
        """remove test dirs/etc
        """
        lib = buf.abspath()
        drop_any = set()
        drop_top = set(('zlib', 'expat')) | drop_any
        for ent in drop_top:
            shutil.rmtree(pth.join(lib, ent), ignore_errors=True)
        if not drop_any:
            return

        for root, dirs, files in os.walk(lib):
            sdirs = set(dirs)
            tests = sdirs & drop_any
            for ent in tests:
                shutil.rmtree(pth.join(root, ent), ignore_errors=True)
            if tests:
                dirs[:] = sorted(sdirs - tests)

    @run('python (>= 2)', 'Lib', raw=True)
    def run(self, buf):
        """remove test dirs/etc
        """
        lib = buf.abspath()
        drop_any = set()
        drop_top = set(('lib-tk', 'idlelib', 'bsddb')) | drop_any
        for ent in drop_top:
            shutil.rmtree(pth.join(lib, ent), ignore_errors=True)
        if not drop_any:
            return

        for root, dirs, files in os.walk(lib):
            sdirs = set(dirs)
            tests = sdirs & drop_any
            for ent in tests:
                shutil.rmtree(pth.join(root, ent), ignore_errors=True)
            if tests:
                dirs[:] = sorted(sdirs - tests)

    @run('python (>= 2)', 'Lib/distutils/distutils.cfg',
            raw=True, finder='make_node')
    def run(self, buf):
        """temp distutils.cfg to control easy_install and bdist
        """
        zpy = self.generator.bld.zpy
        distcfg = (
            '# ident: {zpy.identifier}'
            '\0[global]'
            '\0verbose=1'
            '\0[install]'
            '\0compile=0'
            '\0'.format(**locals())
            )
        buf.write(distcfg.replace('\0', '\n'))

    @run('python (>= 2)', 'Lib/%(landmark)s',
            raw=True, finder='make_node')
    def run(self, buf):
        """custom marker + metadata
        """
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy

        buf.write(json.dumps(dict(zpy)), flags='wb')

    @run('python (>= 2)', 'Modules/Setup', raw=True, finder='make_node')
    def run(self, buf):
        """write initial setup
        """
        buf.write(PYTHON_MODULES_SETUP)

    @run('uwsgi (>= 1.9)', 'buildconf/_zippy_%(identifier)s.ini',
            raw=True, finder='make_node')
    def run(self, buf):
        """uwsgi config
        """
        lines = ['[uwsgi]']
        for k, v in sorted(self.generator.bld.zpy.uconf.iteritems()):
            if isinstance(v, (list, set)):
                v = ','.join(sorted(v))
            lines.append('%s=%s' % (k, v))
        buf.write('\n'.join(lines))

    #...RUN RUN RUN! overwrite the decorator with the real impl, no cleanup ;)
    def run(self):
        bld = self.generator.bld
        rok = False
        try:
            if self.kwds.get('raw'):
                oput = self.fun(self, self.inputs[0])
            else:
                iput = self.inputs[0].path_from(bld.path)
                oput = iput + '.lock'
                orig = iput + '.orig'
                rok = pth.exists(orig)
                shutil.copy2(*(
                    rok and (orig, iput) or (iput, orig)
                    ))
                with open(orig, 'r') as fdi:
                    with open(oput, 'w') as fdo:
                        #TODO: pass fd and iter, eg `for line in fd`
                        buf = fdi.read()
                        fdo.write(self.fun(self, buf))
                shutil.move(oput, iput)
                if Logs.verbose:
                    color = Logs.colors_lst['USE']
                    cmd = ['git', 'diff', '--no-index']
                    if color:
                        cmd.append('--word-diff=color')
                        cmd.append('--color=always')
                    if Logs.verbose > 2:
                        cmd.append('--patch-with-stat')
                    if Logs.verbose > 1:
                        cmd.append('--patch')
                    else:
                        cmd.append('--stat')
                    cmd.extend((orig, iput))
                    bld.exec_command(cmd)
        except:
            if rok:
                os.unlink(orig)
            raise
        return 0


class ZPyTask_Profile(_ZPyTask):

    color = 'BOLD'
    before = []
    after = []

    xtra = ['configure', 'Modules/Setup']

    @property
    def app(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        #env.env['PYTHONVERBOSE'] = 'x'

        app = [(
            './configure'
            '\0--cache-file={tsk._cache_conf}'
            '\0--prefix=/@/{zpy.identifier}'
            '\0--enable-ipv6'
            '\0--enable-unicode=ucs4'
            '\0--enable-loadable-sqlite-extensions'
            '\0--with-dbmliborder=gdbm'
            '\0--with-threads'
            '\0--with-system-expat'
            )]

        app.append(
            'make\0PR0F={tsk._cache_prof}\0' + (
                'build_all_use_profile'
                if pth.exists(self._cache_prof)
                else 'profile-opt'
                ))

        def _sysconfigdata(tsk):
            from pprint import pformat
            class _auto_format(str):
                def __repr__(self):
                    v = '/@/' + zpy.identifier
                    s = super(_auto_format, self).__repr__()
                    if v in s:
                        s = s.replace(v, '{sys.prefix}') + '.format(**locals())'
                    return s
            _path = pth.join(zpy.pybuilddir, '_sysconfigdata.py')
            with open(_path, mode='r+') as fp:
                ns = dict()
                exec fp.read() in ns
                ns = ns.pop('build_time_vars')
                for k, v in ns.iteritems():
                    if isinstance(v, basestring):
                        ns[k] = _auto_format(v)
                fp.seek(0)
                fp.truncate(0)
                fp.write('import sys\n')
                fp.write('build_time_vars = ')
                fp.write(pformat(ns))
                return 0
            return 1
        app.append(_sysconfigdata)

        return app


class ZPyTask_Distribution(ZPyTaskBase):

    color = 'GREEN'
    before = []
    after = []

    vars = ['PYTHON', 'TAR']

    def run(self):
        def command(app, splat):
            app = app.format(**splat)
            return self.exec_command(
                app.strip('\0').split('\0'),
                cwd=self.cwd,
                env=env.env or None,
                )

        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py
        rv = 0

        env.env['_PYTHON_PROJECT_BASE'] = 'x'

        dist = self.dist
        if getattr(self, 'cwd', None) is None:
            self.cwd = pth.join(bld.bldnode.abspath(), dist.key)
        dist_path = pth.join(self.cwd, 'dist')
        if not pth.exists(pth.join(self.cwd, metadata.METADATA_FILENAME)):
            return rv

        rv |= command(
            '{zpy.PYTHON}'
            '\0-m'
            '\0zippy.apps'
            '\0create_wheel'
            '\0{zpy.cache_wheel}'
            '\0',
            locals(),
            )

        return rv


@Task.update_outputs
class ZPyTask_Rewind(ZPyTaskBase):

    color = 'BLUE'
    before = []
    after = []

    def scan(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        l4sh = '*/l4sh/*/Setup'
        self.inputs = bld.bldnode.ant_glob(l4sh, remove=False)
        for i in self.inputs:
            i.sig = Utils.h_file(i.abspath())

        return tuple(), tuple()

    def run(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        o = self.outputs[0]
        o.write(PYTHON_MODULES_SETUP)
        for i in self.inputs:
            o.write(i.read(), flags='ab')

        makefile = py.find_node('Makefile.pre')
        txt = makefile.read()
        lb = txt.find('\nLIBS=') + 1
        rb = txt.find('\n', lb)
        last = txt[lb:rb]
        lines = map(str.strip, o.read().split('\n'))
        for line in lines + [last]:
            if line.startswith('#'):
                continue
            zpy.append_unique('l4sh_libs', (
                lib for lib in map(str.strip, line.split())
                    if lib.startswith('-')
                    ))

        makefile.write(txt[:lb+5] + ' '.join(zpy.l4sh_libs) + txt[rb:])
        return 0


class ZPyTask_Replay(_ZPyTask):

    color = 'BOLD'
    before = []
    after = []

    xtra = 'Modules/Setup'

    @property
    def app(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        if pth.lexists(zpy.o_inc_py):
            os.unlink(zpy.o_inc_py)

        app = list()
        app.append('{zpy.MAKE}\0{zpy.o_stlib}')

        def _sysconfigdata(tsk):
            from pprint import pformat
            class _auto_format(str):
                def __repr__(self):
                    v = '/@/' + zpy.identifier
                    s = super(_auto_format, self).__repr__()
                    if v in s:
                        s = s.replace(v, '{sys.prefix}') + '.format(**locals())'
                    return s
            _path = pth.join(zpy.pybuilddir, '_sysconfigdata.py')
            with open(_path, mode='r+') as fp:
                ns = dict()
                exec fp.read() in ns
                ns = ns.pop('build_time_vars')
                for k, v in ns.iteritems():
                    if isinstance(v, basestring):
                        ns[k] = _auto_format(v)
                fp.seek(0)
                fp.truncate(0)
                fp.write('import sys\n')
                fp.write('build_time_vars = ')
                fp.write(pformat(ns))
                return 0
            return 1
        app.append(_sysconfigdata)

        app.append('{zpy.MAKE}\0DESTDIR=..\0install')
        return app


class ZPyTask_Final(ZPyTaskBase):

    color = 'YELLOW'
    before = []
    after = []

    vars = ['STRIP']

    def scan(self):
        bld = self.generator.bld
        zpy = bld.zpy
        ins = set()
        excl = [
            pth.join('bin', 'python'),
            pth.join('bin', zpy.py_ver1),
            ]
        nodes = bld.o.ant_glob('bin/**', excl=excl)
        for node in nodes:
            path = node.abspath()
            ins.add(node.path_from(bld.o))
            if not getattr(node, 'sig', None):
                node.sig = Utils.h_file(path)
        self.inputs = nodes
        #...save the config for `install`
        zpy.ins = sorted(ins)
        zpy_file = bld.variant + Build.CACHE_SUFFIX
        zpy.store(pth.join(bld.cache_dir, zpy_file))
        if bld.cmd.endswith('install'):
            self.more_tasks = get_module('zippy.install').install(bld, False)
        return tuple(), tuple()

    def run(self):
        env = self.env
        gen = self.generator
        bld = gen.bld
        zpy = bld.zpy
        py = bld.py

        if 0:#not self.env.opt['debug']:
            #FIXME: prevent from running twice on accident?
            app = [zpy.STRIP, '--strip-all', zpy.O_UWSGI]
            ret = self.exec_command(app, env=env.env or None)
            if ret > 0:
                return ret

        #...incl > excl
        incl = dict()
        excl = dict()
        incl[zpy.o] = set(('bin', 'lib'))
        incl[zpy.o_lib] = set((zpy.py_ver2,))
        excl[zpy.o_bin] = set(('python', zpy.py_ver1, zpy.py_ver2))
        excl[zpy.o_lib_py] = set(('config', 'lib-dynload'))
        #...used to filter stdlib
        drop_dir = set()
        drop_ext = set(('.a', '.o', '.in', '.pyo', '.pyc', '.exe'))

        offset = len(zpy.o) + 1
        with zipfile.ZipFile(zpy.O_PYTHON, 'a', zipfile.ZIP_DEFLATED) as zfd:
            # pack our meta first
            zfd.write(
                pth.join(zpy.pylibdir, zpy.landmark),
                pth.join(zpy.o_lib_py, zpy.landmark)[offset:],
                )
            for root, dirs, files in os.walk(zpy.o):
                _d = set(dirs)
                _f = set(files)
                msk = _d | _f
                wht = incl.get(root) or frozenset()
                blk = excl.get(root) or frozenset()
                if root.startswith(zpy.o_lib_py):
                    blk = set((
                        filename
                        for ext in drop_ext
                        for filename in _f
                            if filename.endswith(ext)
                            )) | drop_dir | blk

                if wht:
                    msk &= wht
                elif blk:
                    msk -= blk
                dirs[:] = sorted(_d & msk)
                files[:] = sorted(_f & msk)
                for f in files:
                    path = pth.join(root, f)
                    zfd.write(path, path[offset:])
